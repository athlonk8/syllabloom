# Syllabloom verification record

## Automated checks

Run from `backend/`:

```powershell
..\.venv\Scripts\pytest.exe -q
```

Current result: **19 passed**. Coverage includes watch-interval merging, true completion threshold, three distinct Stanford importer fixtures, protected-link treatment, Obsidian `Answer.md` preservation, grading schema parsing, OpenAI-compatible provider request construction, secret masking, API progress persistence, fresh-directory and legacy-schema Alembic migration, settings-route isolation, and real PDF construction/text extraction.

Run from `frontend/`:

```powershell
npm run build
npm test
```

Current result: TypeScript production build passes; Vitest **2 passed**.

## Database migration check

`alembic upgrade head` was executed against a fresh SQLite file and created all core tables, including `courses`, `lectures`, `videos`, `watch_segments`, `resources`, `assignments`, `submissions`, `grades`, `grading_runs`, `learning_notes`, `certificates`, and configuration tables.

## Public Stanford probes (2026-08-22)

All probes used `max_pages=4`, `max_depth=1`, same-host crawling, public HTTP only, and no credentials.

| URL | Result | Observed discovery |
| --- | --- | --- |
| `https://cs229.stanford.edu/` | Ready | 4 pages, 70 linked resources, 1 public assignment record. No embeddable YouTube lecture was found in the first bounded crawl. |
| `https://web.stanford.edu/class/cs224n/` | Protected | The returned page presented a Stanford authentication signal, so it was saved as `protected_resource=true` with `Requires Stanford authentication` and was not crawled further. |
| `https://cs336.stanford.edu/` | Ready | 4 pages, 1 YouTube lecture, 32 resources, 11 assignment records. |

For CS336, `Assignment 1 : Basics` was actually shallow-cloned from the public official course-page-linked repository. The local record retained commit `a158843b20107949f1a8d7df1b05cd33b9166712`.

## Obsidian and grading checks

- The CS336 temporary Obsidian test created `Assignment.md`, `Answer.md`, and `Feedback.md`. A user-style edit was then made to `Answer.md`; the service reread that same file successfully.
- `codex --version`, `codex --help`, and `codex exec --help` were inspected. This installed CLI supports `exec`, `--sandbox read-only`, `--output-schema`, and `--output-last-message`.
- No real course answer was sent to Codex or another provider during validation because sending it would require the user's explicit in-app acknowledgement. The deterministic parser, schema validation, read-only command construction, and mocked compatible-provider request construction are covered by automated tests.
