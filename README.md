# SmartHelper

SmartHelper is a local customer support demo for the fictional HarborDesk product. Ask a question by voice or text and receive a spoken and written answer with links to the relevant public documentation. The browser interface uses a QwenCloud real-time conversation session; the API key stays on the local server.

The included `mock_data/` directory contains seven public sample documents and one internal sample document. Only documents marked `public` in `mock_data/manifest.json` are loaded or returned as sources.

## What the app does

- Streams microphone audio to the local server, which relays it to `qwen3.8-omni-flash-realtime` on QwenCloud. Tap the microphone again to finish a question.
- Displays QwenCloud's input speech transcript in the conversation and streams the answer as text and audio.
- Accepts typed questions through the same QwenCloud real-time session.
- Requires the model to call the server-side `search_public_docs` tool before an answer is shown or played. This tool searches only the approved public documents and returns source links.
- Lets you open a source at the cited document section and refresh the document index after changing the local Markdown files.

QwenCloud's input transcription feature is enabled within the real-time session. Its configuration names `qwen3-asr-flash-realtime` for the transcript shown in the UI; SmartHelper does not run a separate local transcription service or a three-step voice pipeline.

## Requirements

- Windows PowerShell and Python 3.10 or newer (the project was checked with Python 3.12).
- Internet access from the Python process to QwenCloud.
- A QwenCloud pay-as-you-go API key from [QwenCloud API Keys](https://home.qwencloud.com/api-keys).
- A browser with microphone access for voice questions. `http://127.0.0.1` is a suitable local browser address.

## Set up and run

From this project folder, create a virtual environment and install the dependencies:

```powershell
python -m venv .venv
& '.venv\Scripts\python.exe' -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Run `Copy-Item` only for a new setup so you do not overwrite an existing `.env`. Edit `.env` and replace `replace_with_your_qwen_api_key` with your QwenCloud key:

```dotenv
DASHSCOPE_API_KEY=your_qwencloud_api_key
QWEN_REALTIME_VOICE=Tina
```

QwenCloud's shared real-time endpoint does not need a workspace ID. A Gemini key is **not required** for the browser's voice or typed-question interface; the Gemini settings in `.env.example` support the optional legacy `/api/chat` endpoint described below. Keep `.env` private; it is listed in `.gitignore`.

Check the QwenCloud connection without sending audio:

```powershell
& '.venv\Scripts\python.exe' check_qwen_realtime.py
```

Start the server:

```powershell
& '.venv\Scripts\python.exe' app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000/). Keep the PowerShell window open while using SmartHelper; press **Ctrl+C** there to stop it. Restart the server after editing `.env`.

If you start the app from a network-restricted terminal, the page can load while its QwenCloud connection fails. Run the connection check and app from a normal PowerShell window with internet access.

## Use the interface

1. Select a suggested question or type one in the box and press Enter or the send button.
2. For voice, allow microphone access, tap the microphone, speak, then tap it again. Recording also stops after 30 seconds.
3. Read the answer, listen to the audio, or select **Stop audio**. Open a source card to view the cited documentation section.
4. After editing documents under `mock_data/`, select **Refresh documents** in the sidebar to reload the public index.

The voice question bubble first says **Transcribing…** and updates when QwenCloud sends a transcript. If no transcript arrives, the app labels it as unavailable rather than inventing text.

## Configuration

| Setting | Purpose | Default |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | QwenCloud key used by the server for real-time sessions | Required for the browser interface |
| `QWEN_REALTIME_VOICE` | Qwen voice for spoken answers | `Tina` |
| `APP_HOST` | Local interface on which the server listens | `127.0.0.1` |
| `APP_PORT` | Local server port | `8000` |
| `PUBLIC_DOCS_ONLY` | Must stay `true`; internal documents are excluded | `true` |
| `APP_AUTH_REQUIRED` | Must stay `false`; sign-in is not implemented | `false` |
| `GEMINI_API_KEY` | Optional key for the legacy `/api/chat` API | Unset or placeholder |
| `GEMINI_CHAT_MODEL` | Model for the optional Gemini answer API | `gemini-3.8-flash` |
| `GEMINI_EMBEDDING_MODEL` | Embeddings for the optional Gemini answer API | `gemini-embedding-001` |

The voice session uses `wss://maas.qwencloudapi.com/api-ws/v1/realtime` with the `qwen3.8-omni-flash-realtime` model. Browser audio is sent as 16 kHz mono PCM; spoken answers are returned as 24 kHz PCM. The browser never receives the API key.

## Local API

| Route | Use |
| --- | --- |
| `GET /` | SmartHelper interface |
| `WS /api/realtime` | Browser-to-server QwenCloud real-time bridge for voice and text |
| `GET /api/status` | Document counts and configuration status |
| `POST /api/search` | Keyword search over public documents; body: `{"question":"..."}` |
| `POST /api/reindex` | Reload public documents from `mock_data/` |
| `GET /docs/{document_id}` | View a public document and its linked sections |
| `POST /api/chat` | Optional original Gemini documentation-answer API; body: `{"question":"..."}` |
| `POST /api/feedback` | Save a rating for a request ID; not used by the current browser UI |

The browser uses keyword retrieval through `search_public_docs`; no Gemini key or embedding call is needed for that flow. The optional `/api/chat` API uses Gemini when configured and can fall back to source links when it is not. See [GEMINI_SETUP.md](GEMINI_SETUP.md) if you need that older API.

## Check the project

Run the offline tests, which do not require an API key or a QwenCloud connection:

```powershell
& '.venv\Scripts\python.exe' -m unittest test_app.py test_realtime.py
```

`check_qwen_realtime.py` performs a live connection and session configuration check. It does not record or send microphone audio. `evaluate_retrieval.py` checks the local document search.

## Project files

- `app.py` — FastAPI server, public-document viewer, status, and API routes.
- `qwen_realtime.py` — QwenCloud WebSocket bridge, transcript handling, and documentation search tool.
- `rag_engine.py` and `gemini_config.py` — public-document loading, keyword retrieval, and optional Gemini answer API.
- `static/` — SmartHelper interface, microphone capture, transcript display, and audio playback.
- `mock_data/` — fictional HarborDesk documents and visibility manifest.
- `check_qwen_realtime.py`, `test_app.py`, and `test_realtime.py` — connection check and offline tests.

## Demo limits

SmartHelper is designed for one local computer. It has no sign-in, live customer records, ticket creation, or telephone integration. The app does not save audio or conversation history. If `/api/feedback` is used, it saves only a request ID, rating, and timestamp under `.rag_cache/`. The documentation and answers are for the fictional HarborDesk demo; verify important details against the linked sources.
