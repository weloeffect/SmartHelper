"""Offline checks for the single-model Qwen realtime protocol bridge."""

import asyncio
import base64
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app, engine
from qwen_realtime import MODEL, RealtimeBridge, RealtimeConfig, session_update
from guardrails import PROVIDER_MODERATION_MESSAGE


class FakeBrowser:
    def __init__(self):
        self.events = []

    async def send_json(self, event):
        self.events.append(event)


class FakeProvider:
    def __init__(self):
        self.events = []

    async def send(self, payload):
        self.events.append(json.loads(payload))


class RealtimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.browser = FakeBrowser()
        self.provider = FakeProvider()
        self.bridge = RealtimeBridge(self.browser, self.provider, engine)

    async def test_single_model_qwencloud_session(self):
        config = RealtimeConfig("test-key", "Tina")
        self.assertTrue(config.ready)
        self.assertIn(f"model={MODEL}", config.url)
        self.assertIn("maas.qwencloudapi.com", config.url)
        event = session_update(config)
        self.assertEqual(event["session"]["modalities"], ["text", "audio"])
        self.assertEqual(event["session"]["tools"][0]["function"]["name"], "search_public_docs")
        self.assertEqual(event["session"]["input_audio_transcription"]["model"], "qwen3-asr-flash-realtime")

    async def test_input_transcript_is_forwarded_to_browser(self):
        await self.bridge.from_provider({
            "type": "conversation.item.input_audio_transcription.delta",
            "text": "How do I", "stash": " create a task?",
        })
        await self.bridge.from_provider({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "How do I create a task?",
        })
        self.assertEqual(self.browser.events, [
            {"type": "user_transcript", "text": "How do I create a task?", "final": False},
            {"type": "user_transcript", "text": "How do I create a task?", "final": True},
        ])

    async def test_audio_commit_triggers_one_model_response(self):
        frame = base64.b64encode(b"\x00\x00" * 100).decode()
        await self.bridge.from_browser({"type": "audio", "audio": frame})
        await self.bridge.from_browser({"type": "commit"})
        self.assertEqual([item["type"] for item in self.provider.events], ["input_audio_buffer.append", "input_audio_buffer.commit"])
        await self.bridge.from_provider({"type": "input_audio_buffer.committed"})
        self.assertEqual(self.provider.events[-1]["type"], "response.create")

    async def test_abandoned_recording_clears_audio_without_answer(self):
        frame = base64.b64encode(b"\x00\x00" * 100).decode()
        await self.bridge.from_browser({"type": "audio", "audio": frame})
        await self.bridge.from_browser({"type": "clear_audio"})
        self.assertEqual(self.bridge.audio_bytes, 0)
        self.assertEqual([item["type"] for item in self.provider.events], [
            "input_audio_buffer.append", "input_audio_buffer.clear",
        ])

    async def test_document_tool_returns_only_public_sources(self):
        await self.bridge.from_provider({
            "type": "response.function_call_arguments.done", "name": "search_public_docs",
            "call_id": "call-1", "arguments": json.dumps({"query": "Can a Viewer edit a task?"}),
        })
        output = json.loads(self.provider.events[-1]["item"]["output"])
        self.assertTrue(output["matches"])
        self.assertEqual(output["matches"][0]["source_id"].split("::")[0], "HD-PROD-002")
        self.assertTrue(all("HD-INT-001" not in item["source_id"] for item in output["matches"]))
        self.assertEqual(self.browser.events[-1]["type"], "sources")
        await self.bridge.from_provider({"type": "response.done"})
        self.assertEqual(self.provider.events[-1]["type"], "response.create")

    async def test_ungrounded_audio_is_not_forwarded(self):
        await self.bridge.from_provider({"type": "response.audio.delta", "delta": "AAAA"})
        await self.bridge.from_provider({"type": "response.audio_transcript.delta", "delta": "Invented answer"})
        self.assertFalse(self.browser.events)
        await self.bridge.from_provider({"type": "response.done"})
        self.assertEqual(self.browser.events[-1]["type"], "error")

    async def test_grounded_audio_and_text_are_forwarded(self):
        await self.bridge.from_provider({
            "type": "response.function_call_arguments.done", "name": "search_public_docs",
            "call_id": "call-2", "arguments": '{"query":"What is SmartHelper?"}',
        })
        await self.bridge.from_provider({"type": "response.done"})
        await self.bridge.from_provider({"type": "response.audio_transcript.delta", "delta": "Hello."})
        await self.bridge.from_provider({"type": "response.audio.delta", "delta": "AAAA"})
        await self.bridge.from_provider({"type": "response.done"})
        self.assertEqual([item["type"] for item in self.browser.events[-3:]], ["answer_delta", "audio", "turn_done"])
        self.assertTrue(self.browser.events[-1]["request_id"])

    async def test_typed_turn_is_text_only_and_voice_turn_restores_audio(self):
        await self.bridge.from_provider({"type": "session.updated"})
        await self.bridge.from_browser({"type": "text", "text": "What is SmartHelper?"})
        self.assertEqual(self.provider.events[0], {
            "type": "session.update", "session": {"modalities": ["text"]},
        })
        await self.bridge.from_provider({"type": "session.updated"})
        self.assertEqual([event["type"] for event in self.browser.events], ["ready"])
        await self.bridge.from_provider({
            "type": "response.function_call_arguments.done", "name": "search_public_docs",
            "call_id": "call-text", "arguments": '{"query":"What is SmartHelper?"}',
        })
        await self.bridge.from_provider({"type": "response.done"})
        await self.bridge.from_provider({"type": "response.text.delta", "delta": "A support assistant."})
        await self.bridge.from_provider({"type": "response.audio.delta", "delta": "AAAA"})
        await self.bridge.from_provider({"type": "response.done"})
        self.assertEqual([event["type"] for event in self.browser.events[-2:]], ["answer_delta", "turn_done"])

        frame = base64.b64encode(b"\x00\x00" * 100).decode()
        await self.bridge.from_browser({"type": "audio", "audio": frame})
        self.assertEqual(self.provider.events[-2], {
            "type": "session.update", "session": {"modalities": ["text", "audio"]},
        })

    async def test_history_restore_replays_user_and_assistant_without_generating_answer(self):
        await self.bridge.from_browser({"type": "restore", "turns": [{
            "question": "Can a Viewer edit a task?", "answer": "No. Viewers cannot edit tasks."
        }]})
        self.assertEqual([event["item"]["role"] for event in self.provider.events], ["user", "assistant"])
        self.assertEqual(self.provider.events[1]["item"]["content"][0]["type"], "output_text")
        self.assertFalse(self.browser.events)

    async def test_invalid_history_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid conversation history"):
            await self.bridge.from_browser({"type": "restore", "turns": [{"question": "Hello", "answer": ""}]})
        self.assertFalse(self.provider.events)

    async def test_sensitive_text_is_rejected_before_provider(self):
        with self.assertRaisesRegex(ValueError, "API keys"):
            await self.bridge.from_browser({"type": "text", "text": "My api_key=abcdefghijklmnop123456; help"})
        self.assertEqual(self.provider.events, [])

    async def test_voice_transcript_can_cancel_a_turn(self):
        await self.bridge.from_provider({
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "My password: supersecret123",
        })
        self.assertEqual(self.browser.events[-1]["type"], "error")
        self.assertEqual(self.provider.events[-1]["type"], "response.cancel")
        await self.bridge.from_provider({"type": "response.audio.delta", "delta": "AAAA"})
        self.assertFalse(any(event["type"] == "audio" for event in self.browser.events))

    async def test_provider_moderation_error_has_safe_message(self):
        await self.bridge.from_provider({
            "type": "error", "error": {"code": "data_inspection_failed", "message": "private content"},
        })
        self.assertEqual(self.browser.events[-1]["message"], PROVIDER_MODERATION_MESSAGE)

    async def test_answer_is_checked_before_text_or_audio_is_released(self):
        await self.bridge.from_provider({
            "type": "response.function_call_arguments.done", "name": "search_public_docs",
            "call_id": "call-3", "arguments": '{"query":"What is SmartHelper?"}',
        })
        await self.bridge.from_provider({"type": "response.done"})
        await self.bridge.from_provider({"type": "response.audio.delta", "delta": "AAAA"})
        await self.bridge.from_provider({"type": "response.audio_transcript.delta", "delta": "Your API key: abcdefghijklmnop123456"})
        self.assertEqual(self.browser.events[-1]["type"], "error")
        self.assertFalse(any(event["type"] == "audio" for event in self.browser.events))

    async def test_turn_rate_limit_rejects_before_provider(self):
        with patch("qwen_realtime.rate_limiter.check", return_value=12):
            with self.assertRaisesRegex(ValueError, "12 seconds"):
                await self.bridge.from_browser({"type": "text", "text": "How do I create a task?"})
        self.assertEqual(self.provider.events, [])


class RealtimeEndpointTests(unittest.TestCase):
    def test_missing_credentials_reported_without_exposing_secret(self):
        with patch("qwen_realtime.realtime_config", return_value=RealtimeConfig("", "Tina")):
            with TestClient(app) as client:
                with client.websocket_connect("/api/realtime") as socket:
                    event = socket.receive_json()
        self.assertEqual(event["type"], "error")
        self.assertIn("DASHSCOPE_API_KEY", event["message"])
        self.assertNotIn("test-key", event["message"])


if __name__ == "__main__":
    unittest.main()
