# Security and privacy boundaries

The application is intentionally local-first. Its only automatic writes are under the project data directory and a Vault path the user explicitly configures.

| Operation | Boundary |
| --- | --- |
| SQLite, downloads, snapshots, grading workspaces | `data/` / `LearningVault/` below the project or the explicitly configured `PALO_DATA_DIR`. |
| Obsidian output | `<configured Vault>/AI-Learning/` only. Existing notes are preserved. |
| Resource download | Only importer-recorded HTTP(S) URLs; 250 MB limit; checksum and provenance retained. |
| GitHub work | `git clone --depth 1 --no-tags` only; no checkout mutation in a user repo, no push. |
| Codex grading | User click and acknowledgement; copied workspace; `codex exec --sandbox read-only --ask-for-approval never`. |

The app never implements authentication bypass, cookie replay, login emulation, paywall circumvention, broad-domain crawling, public mirroring, automatic publishing, or Git push.
