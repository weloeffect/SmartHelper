"""Run the local SmartHelper documentation assistant with `python app.py`."""

from datetime import datetime, timezone
import html
import json
import re
from pathlib import Path
from threading import Lock
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel, Field

from gemini_config import get_settings
from guardrails import MAX_TURNS_PER_WINDOW, moderate_text, rate_limiter
from rag_engine import CACHE_PATH, RagEngine
from qwen_realtime import MODEL as REALTIME_MODEL, bridge_realtime, realtime_config


ROOT = Path(__file__).resolve().parent
settings = get_settings(require_api_key=False)
engine = RagEngine(settings)
app = FastAPI(title="SmartHelper", version="0.1.0", docs_url="/api/reference")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
feedback_lock = Lock()


@app.middleware("http")
async def limit_api_requests(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith("/api/"):
        client = request.client.host if request.client else "unknown"
        retry_after = rate_limiter.check(client, "http", MAX_TURNS_PER_WINDOW)
        if retry_after:
            return JSONResponse(
                {"detail": "Too many requests. Please wait and try again."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class FeedbackRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    rating: str


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/status")
def status() -> dict:
    return {
        "documents": len(engine.documents),
        "sections": len(engine.chunks),
        "gemini_configured": engine.client is not None,
        "qwen_realtime_configured": realtime_config().ready,
        "realtime_model": REALTIME_MODEL,
        "chat_model": settings.chat_model,
        "embedding_model": settings.embedding_model,
        "public_docs_only": True,
        "local_url": f"http://{settings.app_host}:{settings.app_port}",
    }


@app.websocket("/api/realtime")
async def realtime_socket(websocket: WebSocket) -> None:
    await bridge_realtime(websocket, engine)


@app.post("/api/search")
def search(request: QuestionRequest) -> dict:
    if message := moderate_text(request.question):
        raise HTTPException(status_code=400, detail=message)
    try:
        results = engine.search(request.question, use_embeddings=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"results": [engine._public_citation(item) for item in results]}


@app.post("/api/chat")
def chat(request: QuestionRequest) -> dict:
    if message := moderate_text(request.question):
        raise HTTPException(status_code=400, detail=message)
    try:
        result = engine.answer(request.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise HTTPException(
            status_code=503,
            detail="This app process cannot reach Gemini. Start the app from a normal PowerShell window with internet access, then try again.",
        ) from exc
    except Exception as exc:
        # Provider messages may contain request content. Expose only class and status.
        name = type(exc).__name__
        status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        suffix = f", HTTP {status}" if isinstance(status, int) else ""
        raise HTTPException(
            status_code=503,
            detail=f"Gemini request failed ({name}{suffix}). Run check_gemini.py --live in the same PowerShell window for details.",
        ) from exc
    if message := moderate_text(result.get("answer", ""), user_input=False):
        result = {"answer": "I can't provide that answer. Please contact support.", "citations": [], "mode": "moderated"}
    return {"request_id": str(uuid4()), **result}


@app.post("/api/reindex")
def reindex() -> dict:
    try:
        return engine.reload()
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=500, detail="Could not refresh the documentation index.") from exc


@app.post("/api/feedback")
def feedback(request: FeedbackRequest) -> dict:
    if request.rating not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="Rating must be 'up' or 'down'.")
    CACHE_PATH.parent.mkdir(exist_ok=True)
    record = {
        "request_id": request.request_id,
        "rating": request.rating,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with feedback_lock:
        with (CACHE_PATH.parent / "feedback.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")
    return {"saved": True}


@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
def document_index() -> HTMLResponse:
    categories = (
        ("product_guide", "Product guides", "Learn the core SmartHelper workflow.", "01"),
        ("developer_guide", "Developer guides", "Build with the API and webhooks.", "02"),
        ("support_article", "Support articles", "Find practical answers and troubleshooting steps.", "03"),
        ("release_note", "Release notes", "See what changed in SmartHelper.", "04"),
    )
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Documentation · SmartHelper</title>',
        '<link rel="stylesheet" href="/static/docs.css?v=3"></head><body>',
        '<header class="docs-topbar"><a class="docs-brand" href="/" aria-label="SmartHelper home"><span class="docs-brand-mark">S</span><span>SmartHelper</span></a></header>',
        '<main class="docs-main"><section class="docs-hero">',
        '<div class="docs-eyebrow">SMARTHELPER HELP CENTER</div>',
        '<div class="docs-hero-row"><div><h1>Documentation</h1>',
        '<p>Clear, practical guides for using and building with SmartHelper. Browse by topic, then open a document to read every section.</p></div></div>',
        '</section><nav class="docs-jump" aria-label="Documentation categories">',
    ]
    for source_type, heading, _, _ in categories:
        if any(item["source_type"] == source_type for item in engine.documents.values()):
            parts.append(f'<a href="#{source_type}">{heading}</a>')
    parts.append('</nav><div class="docs-sections">')
    for source_type, heading, description, number in categories:
        documents = [(key, value) for key, value in engine.documents.items() if value["source_type"] == source_type]
        if not documents:
            continue
        parts.extend([
            f'<section id="{source_type}" class="docs-category">',
            '<div class="docs-category-heading">',
            f'<span class="docs-category-number">{number}</span><div><h2>{heading}</h2><p>{description}</p></div>',
            f'<span class="docs-category-count">{len(documents)} {"document" if len(documents) == 1 else "documents"}</span>',
            '</div><div class="docs-grid">',
        ])
        for document_id, document in documents:
            sections = [chunk for chunk in engine.chunks if chunk.document_id == document_id]
            raw_preview = sections[0].text.strip().split("\n\n", 1)[0] if sections else ""
            preview = re.sub(r"\s+", " ", re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", raw_preview))
            preview = preview.replace("**", "").replace("`", "")
            if len(preview) > 170:
                preview = preview[:167].rstrip() + "…"
            parts.extend([
                f'<a class="docs-card" href="/docs/{quote(document_id, safe="")}">',
                '<span class="docs-card-arrow" aria-hidden="true">↗</span>',
                f'<h3>{html.escape(document["title"])}</h3>',
                f'<p>{html.escape(preview)}</p>',
                f'<span class="docs-card-meta">{len(sections)} sections <span aria-hidden="true">·</span> Updated {html.escape(document["updated_at"])}</span>',
                '</a>',
            ])
        parts.append('</div></section>')
    parts.append('</div></main></body></html>')
    return HTMLResponse("".join(parts))


@app.get("/docs/{document_id}", response_class=HTMLResponse, include_in_schema=False)
def document_view(document_id: str) -> HTMLResponse:
    document = engine.documents.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    sections = [chunk for chunk in engine.chunks if chunk.document_id == document_id]
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<title>{html.escape(document["title"])}</title>',
        '<link rel="stylesheet" href="/static/style.css"></head><body class="doc-page">',
        '<main class="doc-shell"><nav class="doc-nav"><a class="back-link" href="/">← Back to assistant</a><a class="back-link" href="/docs">All documentation</a></nav>',
        f'<div class="eyebrow">{html.escape(document["source_type"].replace("_", " "))} · Updated {html.escape(document["updated_at"])}</div>',
        f'<h1>{html.escape(document["title"])}</h1>',
    ]
    for chunk in sections:
        parts.append(f'<section id="{html.escape(chunk.anchor)}" class="doc-section">')
        parts.append(f'<h2>{html.escape(chunk.heading)}</h2>')
        parts.append(f'<pre>{html.escape(chunk.text)}</pre></section>')
    parts.append('</main></body></html>')
    return HTMLResponse("".join(parts))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.app_port)
