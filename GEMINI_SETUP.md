# Local Gemini setup for the documentation assistant MVP

The MVP is configured for local use with no user sign-in. It should search only documents marked `public` in `mock_data/manifest.json`. The Gemini API key belongs on the server side; users of the chat interface do not need individual keys.

## Set up on Windows PowerShell

From this folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Create an API key in [Google AI Studio](https://aistudio.google.com/app/apikey), then edit `.env` and replace `replace_with_your_gemini_api_key` with the key. Do not share the key or commit `.env`. The `.gitignore` file excludes it from normal Git commits. An environment variable named `GEMINI_API_KEY` can be used instead of `.env`.

Check the local configuration without making an API call:

```powershell
.venv\Scripts\python.exe check_gemini.py
```

After adding a key, test the configured generation and embedding models with two small live requests:

```powershell
.venv\Scripts\python.exe check_gemini.py --live
```

The live check may incur API usage. It reports whether the models work for your key without printing the key itself.

## Chosen defaults

| Setting | Default | Purpose |
| --- | --- | --- |
| `GEMINI_CHAT_MODEL` | `gemini-3.8-flash` | Generate answers from retrieved passages |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Embed documentation and questions |
| `APP_HOST` | `127.0.0.1` | Accept connections from this computer |
| `APP_PORT` | `8000` | Local server port |
| `APP_AUTH_REQUIRED` | `false` | No sign-in for the first MVP |
| `PUBLIC_DOCS_ONLY` | `true` | Exclude the mock internal runbook |

If people on other computers need to use the app, the host and network setup will need to change. Do not expose a sign-in-free local server to the internet. Keep the key in the server process rather than browser JavaScript.

## Run the app

Open PowerShell or Windows Terminal from the Windows Start menu, outside the Codex built-in terminal. The built-in terminal may run with network restrictions that prevent Gemini requests. Then start the local server:

```powershell
.venv\Scripts\python.exe app.py
```

If an answer reports that the app process cannot reach Gemini, the key may still be valid: the Python process may be running in a network-restricted environment. Run `.venv\Scripts\python.exe check_gemini.py --live` in the same PowerShell window to check generation and embeddings separately. Restart the server after editing `.env`.

Open `http://127.0.0.1:8000` in a browser. The app loads the seven public mock documents at startup. **Refresh documents** reloads edited Markdown files. With no key, it shows relevant sections in search mode; after adding a key and restarting the server, it uses Gemini embeddings and answer generation. The internal runbook is excluded in both modes.

For a quick offline check:

```powershell
.venv\Scripts\python.exe -m unittest test_app.py
.venv\Scripts\python.exe evaluate_retrieval.py
```

This MVP is designed for one local computer. It has no user accounts, and anyone who can open its local address can ask about the public documents. No conversation history is stored; feedback saves only a request ID, rating, and timestamp in `.rag_cache/feedback.jsonl`.

## References

- [Gemini API key setup](https://ai.google.dev/gemini-api/docs/api-key)
- [Gemini models](https://ai.google.dev/gemini-api/docs/models)
- [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
