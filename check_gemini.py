"""Check local Gemini setup. Add --live for a small paid API smoke test."""

import argparse

from google import genai

from gemini_config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call Gemini generation and embedding APIs")
    args = parser.parse_args()

    settings = get_settings(require_api_key=args.live)
    key_ready = bool(settings.api_key and settings.api_key != "replace_with_your_gemini_api_key")
    print(f"Gemini SDK configuration: ready")
    print(f"API key configured: {'yes' if key_ready else 'no'}")
    print(f"Generation model: {settings.chat_model}")
    print(f"Embedding model: {settings.embedding_model}")
    print(f"Local app: http://{settings.app_host}:{settings.app_port}")
    print(f"Sign-in required: {settings.auth_required}")
    print(f"Public documents only: {settings.public_docs_only}")

    if not args.live:
        print("No API calls made. Run with --live after adding a key to test Gemini access.")
        return 0

    client = genai.Client(api_key=settings.api_key)
    checks = [
        ("Generation", lambda: client.models.generate_content(
            model=settings.chat_model,
            contents="Reply with exactly: Gemini connection OK",
        )),
        ("Embedding", lambda: client.models.embed_content(
            model=settings.embedding_model,
            contents="HarborDesk documentation search test",
        )),
    ]
    failed = False
    for label, check in checks:
        try:
            result = check()
            if label == "Generation":
                print(f"Generation response: {(result.text or '').strip()}")
            else:
                print(f"Embedding values returned: {len(result.embeddings[0].values)}")
        except Exception as exc:
            failed = True
            detail = str(exc).replace(settings.api_key, "[redacted]")[:500]
            print(f"{label} failed ({type(exc).__name__}): {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
