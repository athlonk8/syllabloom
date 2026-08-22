# User Guide

## Import a YouTube course

Set a local API key in Settings, then paste a public playlist or video URL. Playlist data comes from YouTube Data API v3: title, channel, ordered videos, duration, thumbnail, description, and publication date. If there is no key, use **Manual fallback** and enter the course/video details yourself. The system does not scrape YouTube page HTML.

The embedded player is the YouTube IFrame Player API. While it plays, the UI reports short segments. Segments caused by a seek are not treated as watched coverage. The latest recorded point is used to resume a later session.

## Import a Stanford course

Paste a public `*.stanford.edu` course URL. The importer:

1. checks the course host's robots policy;
2. fetches only the supplied page and selected same-host schedule, lecture, material, and assignment links within a small configurable bound;
3. records PDFs, notebooks, GitHub, slides, notes, readings, assignments, and protected links with source-page provenance;
4. does not follow Canvas/SSO/Gradescope login gates.

An access-gated page is retained as a protected source with `Requires Stanford authentication`; it is not silently omitted and it is not accessed.

## Official assignments and notes

Use **Download original** only for an assignment marked official. The app stores its original files separately from `workspace/`. If an Obsidian vault is configured, **Create notes** creates an `AI-Learning/<course>/Assignments/...` folder. `Answer.md` is your shared source of truth: edit it in Obsidian or another editor, then submit it from the web app.

## Grading and revision

The submit control remains disabled until you affirm the AI-submission notice. This is intentional. On submission the system stages an immutable snapshot and first runs public pytest tests when present.

Choose the provider in Settings:

- Codex CLI receives a read-only staging workspace and is instructed to provide progressive feedback rather than a complete solution.
- An OpenAI-compatible provider receives only the staged Answer.md, public assignment context, course AI policy, and any official-test summary. It never receives a writable local path.
- Disabled leaves deterministic public tests available without making an AI request.

Every AI request still requires a separate, explicit confirmation in the assignment card. The application never silently submits an answer to any configured provider.

The app keeps v1, v2, and later submissions. Re-open your existing `Answer.md`, revise it, and submit again; no earlier snapshot is overwritten.

## Certificates

Completion requires configured video coverage and passed, publicly available required official assignments. Mastery additionally enforces per-assignment and average score thresholds. A certificate says that it is an independent learning credential and is not Stanford-issued, sponsored, endorsed, or accredited.
