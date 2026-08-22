# Changelog

## Unreleased

- Added an in-browser assignment workbench with local Markdown drafts, immutable submission versions, full feedback history, and detailed structured results from the learner-configured Codex/AI provider.
- Replaced the embedded Bilibili external-player iframe with an owned HTML5 player: official QR-code sign-in inside the page, real quality switching that preserves playback position, and watch progress that counts toward course completion.
- Made Bilibili the default import source: pasting a video link parses the BV id and public part metadata, and multi-P videos split into one lecture per part; a CS336 preset was added to the import dialog.
- Added local-only Bilibili session storage (masked in settings responses), WBI-signed playurl requests, and a range-preserving in-memory media relay restricted to Bilibili CDN hosts.
- Verified that Bilibili's official external player can decline a 720p choice for the CS336 source even when the full Bilibili page plays 720p; Syllabloom preserves in-page playback and does not attempt to bypass that provider limitation.
- Added an annotated English/Chinese screenshot tour for the core local learning, Bilibili, assignment, and configuration workflows.
- Added a persistent, system-aware Light/Dark theme switcher and compact expandable imported-policy/source panels.
- Renamed the project to Syllabloom and added an English-first interface with a Chinese language link.
- Added a one-command native launcher and a single-container Docker deployment.
- Added configurable Codex CLI, disabled, and OpenAI-compatible AI feedback modes.
- Added GitHub Actions CI and open-source contribution files.

## 0.1.0

- Initial local-first learning workspace MVP.
