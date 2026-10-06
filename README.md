# SmartHelper voice support demo

A local voice support agent for the fictional HarborDesk documentation in `mock_data/`. One Qwen real-time model receives live microphone audio, searches the approved public documents through a server-side tool, and streams back speech and answer text with source links.

## Start

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

In `.env`, set `DASHSCOPE_API_KEY` to a QwenCloud pay-as-you-go API key from [QwenCloud API Keys](https://home.qwencloud.com/api-keys). A workspace ID is not needed for QwenCloud's shared real-time endpoint. Then run:

```powershell
.venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Tap the microphone to speak and tap it again to finish. You can also type a question. The app requires browser microphone permission and a local or secure browser context.

To check the key and realtime session without sending audio, run `.venv\Scripts\python.exe check_qwen_realtime.py`.

The model is `qwen3.8-omni-flash-realtime`, with the `Tina` voice by default. It uses one persistent session with QwenCloud's `maas.qwencloudapi.com` endpoint for speech input, grounded answer generation, and speech output. The browser sends 16 kHz PCM audio to the local server; the QwenCloud API key stays on the server. The model must call `search_public_docs` before a response is shown or played. Search results include only public documents.

This is a local demo without sign-in, live ticketing, or telephone integration. Audio is not stored by this app. The older Gemini text-answer API remains available for the original documentation demo, but it is not used by the real-time voice interface.

## Files

- `app.py`: local web server, status, document viewer, and real-time WebSocket endpoint.
- `qwen_realtime.py`: Qwen session bridge and public-document search tool.
- `rag_engine.py`: document loading and public-document retrieval.
- `static/`: browser interface, microphone streaming, and audio playback.
- `mock_data/`: fictional documents and sample questions.
- `test_realtime.py`: local protocol checks that do not require a Qwen key.
- `check_qwen_realtime.py`: live connection check that does not send audio.
