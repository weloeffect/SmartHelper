"""Check whether the right mock document appears in keyword search results."""

import json
from pathlib import Path

from gemini_config import get_settings
from rag_engine import RagEngine


def main() -> int:
    engine = RagEngine(get_settings(require_api_key=False))
    questions = [json.loads(line) for line in (Path(__file__).parent / "mock_data" / "sample_questions.jsonl").read_text(encoding="utf-8").splitlines()]
    evaluated = 0
    hits = 0
    for item in questions:
        if not item["answerable_for_public"]:
            continue
        evaluated += 1
        found = {result["document_id"] for result in engine.search(item["question"], limit=5, use_embeddings=False)}
        expected = set(item["expected_document_ids"])
        success = bool(found & expected)
        hits += success
        print(f"{'PASS' if success else 'MISS'} {item['id']}: {item['question']}")
    print(f"Relevant document in top 5: {hits}/{evaluated}")
    return 0 if hits == evaluated else 1


if __name__ == "__main__":
    raise SystemExit(main())
