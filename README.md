# Syllabloom

English · [中文](README.zh-CN.md)

Syllabloom is a local-first learning workspace for turning public courses into a durable, personal study practice. It combines public-course imports, genuine video-watch coverage, Obsidian notes, versioned assignment snapshots, optional AI feedback, and independent completion records in one self-hosted web app.

It is intended to be installed and run by the learner. No hosted Syllabloom account is required.

## Why Syllabloom

The name combines syllabus and bloom: a course plan becomes something you actively practice, annotate, revisit, and grow from. It is deliberately a product name rather than an operating-system label.

## What it does

- Imports public YouTube videos and playlists through the official YouTube Data API.
- Lets a learner attach a direct Bilibili BV video URL to any lecture and play it through Bilibili's own iframe player. Such sources are explicitly marked learner-selected and third-party; they are never presented as official course material.
- Imports bounded, robots-aware public Stanford course pages without bypassing access controls.
- Tracks unique watched video intervals through the YouTube IFrame Player API. Seeking does not count as watching.
- Keeps course records, downloads, submission snapshots, and certificates local in SQLite and the local data directory.
- Exports a predictable AI-Learning subtree into an existing Obsidian vault. Answer.md remains the learner's source of truth.
- Runs public official tests when they are available, then optionally requests feedback from Codex CLI or an OpenAI-compatible endpoint.
- Generates a local independent-learning certificate only when its completion rules are met.
- Starts with English by default. Use the English · 中文 link in the lower-left sidebar to switch the UI; the choice is retained in the browser.
- Follows the system color preference on first use, with a persistent Light/Dark switch in the sidebar footer.

## What it does not do

- It does not bypass Canvas, SSO, Gradescope, paywalls, authentication, or any other access control.
- It does not scrape YouTube page HTML as an alternative to the official API.
- It does not present AI-invented work as an official assignment.
- It does not silently upload notes, answers, or course materials to a cloud service.
- It does not issue a university credential or claim a relationship with Stanford or another course provider.

## Quick start

### Docker Desktop

This is the simplest option for most users. Install and start Docker Desktop, then run the following from a terminal:

    git clone https://github.com/athlonk8/syllabloom.git
    cd syllabloom
    docker compose up --build

Open http://localhost:8080. The first build downloads dependencies and takes longer; later starts normally need only:

    docker compose up

Stop the service while retaining learning data:

    docker compose down

Do not use docker compose down --volumes unless you deliberately want to remove the Docker-managed database, downloaded materials, submissions, and certificates.

### Native one-command launch

Choose native launch when you want Syllabloom to use a locally installed Codex CLI. Install Python 3.11 or newer and a compatible Node.js version: 22.22.2 or newer in the 22 line, 24.15.0 or newer in the 24 line, or a newer compatible release.

    git clone https://github.com/athlonk8/syllabloom.git
    cd syllabloom
    python scripts/run_local.py

On Windows PowerShell, this wrapper is also available:

    .\scripts\start-local.ps1

The launcher creates a virtual environment, installs dependencies when they change, builds the frontend, applies safe database migrations, starts the app, and opens http://127.0.0.1:8000. Press Ctrl+C in that terminal to stop it.

For ports, reload mode, offline browser launching, Docker vault mounts, and upgrades, read the detailed [installation guide](docs/INSTALLATION.md).

## First ten minutes

1. Start Syllabloom and open Settings.
2. Add a YouTube Data API key if you want automatic YouTube playlist metadata. Without it, use Manual fallback to create a course from a public video URL.
3. Optionally set an existing Obsidian vault path. Syllabloom writes only below that vault's AI-Learning directory and never replaces an existing Answer.md.
4. Import a public YouTube video, playlist, or public Stanford course URL. You can also expand **Use a Bilibili source** beneath any lecture and paste a direct BV video URL.
5. Watch an embeddable video in the app. Progress is based on unique covered intervals, not a manual completed toggle.
6. For an official public assignment, download the original, create your notes, edit Answer.md, and explicitly confirm an AI-feedback submission only when you want one.

## AI providers and privacy

AI feedback is optional and off from the perspective of external network use until you configure a provider and confirm a submission.

| Provider | Best for | What it receives |
| --- | --- | --- |
| Codex CLI | Native launch with Codex installed and signed in on the same machine | A read-only staged assignment workspace. |
| OpenAI-compatible endpoint | Ollama, LM Studio, vLLM, OpenAI, or another compatible Chat Completions server | Only the staged Answer.md plus bounded public assignment context and any official-test summary. |
| Disabled | Learners who only want deterministic public tests | No AI request is made. |

Every AI request requires a separate acknowledgement in the assignment card. A remote compatible endpoint can have its own retention policy and pricing, so review that provider's policy before enabling it. API keys are stored locally and are never returned by the settings API.

Codex CLI runs naturally in native mode. The standard Docker image does not bundle or authenticate the Codex CLI; Docker users can use an OpenAI-compatible endpoint such as a local Ollama or LM Studio server instead.

## Data, backups, and upgrades

Native launch stores application data below the repository's data directory by default. Set SYLLABLOOM_DATA_DIR before starting if you prefer a different local location. Docker uses the named Syllabloom data volume. Neither location is committed to Git.

Back up your native data directory or Docker volume before upgrading a long-running installation. To update:

    git pull
    docker compose up --build

Or, for native launch:

    git pull
    python scripts/run_local.py

Database migrations run at startup. Existing legacy local databases are recognized safely; a partial or inconsistent database is not silently stamped as current.

## Public-source policy

Syllabloom makes a clear distinction between public official work, protected resources, and personal work:

- Stanford imports start from the supplied public URL, obey robots rules, and crawl only a small same-host set of relevant links.
- A login-gated resource is recorded as protected with provenance; it is not fetched through the gate.
- An assignment is treated as official only when a public official course page directly links to it.
- A Bilibili link added by a learner is stored as a third-party source with its provenance. Syllabloom does not copy it, infer authorization, or bypass any Bilibili access rule.
- Original downloads, the editable workspace, and each submission snapshot are separated so later revisions do not overwrite the historical record.

## Documentation

| Guide | Purpose |
| --- | --- |
| [Installation guide](docs/INSTALLATION.md) | Docker and native setup, ports, Obsidian mounts, local AI endpoints, updates, and troubleshooting. |
| [安装指南（中文）](docs/INSTALLATION.zh-CN.md) | 中文安装、配置和排错说明。 |
| [User guide](docs/USER_GUIDE.md) | Course importing, notes, feedback, certificates, and study workflow. |
| [用户指南（中文）](docs/USER_GUIDE.zh-CN.md) | 中文使用流程和数据边界说明。 |
| [Architecture](docs/ARCHITECTURE.md) | Service boundaries, provenance, and trust model. |
| [Testing record](docs/TESTING.md) | Current automated and manual verification record. |
| [Contributing](CONTRIBUTING.md) | Development and pull-request expectations. |
| [Security policy](SECURITY.md) | Reporting path and security boundaries. |

## Development

The repository uses React, TypeScript, Vite, FastAPI, SQLAlchemy, Alembic, and SQLite. Run all checks before submitting a change:

    cd backend
    ../.venv/Scripts/python -m pytest -q

    cd ../frontend
    npm test
    npm run build

On macOS or Linux, use the platform-appropriate Python path inside .venv.

## License

Syllabloom is released under the [MIT License](LICENSE).
