# Mock documentation for the RAG assistant MVP

This is a fictional documentation set for **SmartHelper**, a team task-management product. All names, limits, prices, dates, and procedures are invented for testing. No accounts or external services are needed.

## Contents

- `manifest.json` lists each document's stable ID, source category, local path, and visibility.
- `docs/product/` contains product guides.
- `docs/support/` contains support articles.
- `docs/releases/` contains a release note.
- `docs/internal/` contains one restricted document for an access-control test. Do not include it in a public-only index.
- `sample_questions.jsonl` contains answerable, unanswerable, and restricted-information questions.

Use the Markdown heading hierarchy and relative file path as citation locations. The `source_uri` values in the manifest are local relative paths and can be replaced with canonical URLs when real sources are connected. Documents can be indexed independently; the `updated_at` field and file checksum can drive incremental reindexing.

For the simplest MVP, index only entries with `visibility: "public"`, retrieve relevant sections, and require answer citations to those sections. The internal document is provided only to exercise permission filtering.
