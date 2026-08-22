# Syllabloom verification record

## Automated checks

Run from `backend/`:

```powershell
..\.venv\Scripts\pytest.exe -q
```

Current result: **26 passed**. Coverage includes watch-interval merging, true completion threshold, three distinct Stanford importer fixtures, protected-link treatment, Obsidian `Answer.md` preservation, local draft/version API workflow, grading schema parsing, OpenAI-compatible provider request construction, secret masking, API progress persistence, fresh-directory and legacy-schema Alembic migration, settings-route isolation, and real PDF construction/text extraction.

Run from `frontend/`:

```powershell
npm run build
npm test
```

Current result: TypeScript production build passes; Vitest **4 passed**.

## Local UI and Bilibili return check

The local UI was exercised at `http://127.0.0.1:8000` with the imported CS336 Bilibili source.

- The Bilibili iframe remained inside the course page.
- A simulated post-login return URL selected the same course and lecture, removed the one-time `bilibili_login` and `bilibili_lecture` parameters, scrolled to the embedded player, and re-mounted the iframe.
- The language links retained the selected course but did not retain the one-time sign-in parameters.
- The official Bilibili iframe is rendered with a sandbox that excludes popup and top-navigation permission, but permits a user-activated storage-access request for the signed-in Bilibili session; the UI exposes no app-owned external-playback button.
- The in-page fullscreen control was exercised. The validation browser declined its Fullscreen API request, and the UI correctly reported that browser limitation without treating the embed itself as unavailable.
- Eight credential-free local UI captures are committed in [the feature tour](FEATURE_TOUR.md).

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
