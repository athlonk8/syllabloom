# Installation and operations guide

[中文](INSTALLATION.zh-CN.md)

This guide covers local installation, persistent data, optional AI providers, Obsidian, updates, backups, and recovery. For the shortest route, use the Docker commands in the [README](../README.md).

## Choose a runtime

| Option | Choose it when | Address |
| --- | --- | --- |
| Docker Desktop | You want one service and do not need to run Codex CLI inside the container. | http://localhost:8080 |
| Native launcher | You want the application to use a Codex CLI installed on your machine, or prefer direct local files. | http://127.0.0.1:8000 |

Both modes serve the frontend and FastAPI application together. A separate Vite server is not needed for normal use.

## Docker Desktop setup

1. Install Docker Desktop and verify that its engine is running.
2. Clone the repository:

       git clone https://github.com/athlonk8/syllabloom.git
       cd syllabloom

3. Start the application:

       docker compose up --build

4. Open http://localhost:8080.

The command remains attached to the terminal and prints logs. To run in the background:

    docker compose up --build -d

Useful commands:

    docker compose logs -f
    docker compose down
    docker compose up

Docker keeps runtime data in a named Syllabloom volume. The following command is destructive:

    docker compose down --volumes

It deletes the SQLite database, downloaded materials, submission snapshots, and generated certificates. Back up important data before using it.

### Docker and Obsidian

A container cannot see host folders unless you mount them. Add a bind mount under the app service in compose.yaml, alongside the existing data volume:

    volumes:
      - syllabloom-data:/data
      - "C:/Users/you/Documents/MyVault:/vault"

Use an absolute host path appropriate for your computer. Restart the compose service, then set Obsidian Vault Path to /vault in Settings. Syllabloom writes only inside /vault/AI-Learning.

### Docker and a local AI server

From a Docker container, localhost refers to the container itself. When Ollama or LM Studio runs on the host, Docker Desktop normally exposes it at:

    http://host.docker.internal:11434/v1

Set that address as the compatible API base URL and use the model name the server exposes. Do not use http://localhost:11434/v1 in this Docker configuration.

The standard image does not bundle or authenticate Codex CLI. Use an OpenAI-compatible endpoint in Docker, or choose native launch when you need Codex CLI.

## Native setup

### Prerequisites

- Python 3.11 or newer.
- Node.js 22.22.2 or newer in the 22 major line, Node.js 24.15.0 or newer in the 24 major line, or a newer compatible release.
- Git if you want to clone the project or download a public GitHub assignment resource.
- Codex CLI only if you choose Codex CLI feedback.

Clone and launch:

    git clone https://github.com/athlonk8/syllabloom.git
    cd syllabloom
    python scripts/run_local.py

On Windows PowerShell:

    .\scripts\start-local.ps1

The launcher creates .venv, installs Python dependencies when requirements change, runs npm ci when the package lock changes, builds the production frontend, executes database migrations, and starts FastAPI.

Available options:

    python scripts/run_local.py --no-browser
    python scripts/run_local.py --port 8090
    python scripts/run_local.py --reload
    python scripts/run_local.py --skip-install

Use --skip-install only after a successful normal installation. Reload mode is for contributors. Press Ctrl+C to stop the native server.

## Configuration

Most users should configure Syllabloom through Settings. Secrets are stored locally in SQLite and the settings response masks them.

For repeatable local setup, copy .env.example to .env in the repository root:

    Copy-Item .env.example .env

On macOS or Linux:

    cp .env.example .env

The .env file is ignored by Git. Never commit a real API key.

| Variable | Purpose | Typical value |
| --- | --- | --- |
| SYLLABLOOM_DATA_DIR | Native data location. | D:/SyllabloomData |
| SYLLABLOOM_DATABASE_URL | Advanced SQLAlchemy URL override. | Leave blank for the local default. |
| SYLLABLOOM_YOUTUBE_API_KEY | Official YouTube Data API key. | Optional. |
| SYLLABLOOM_WATCH_COMPLETION_THRESHOLD | Unique video coverage required for completion. | 0.85 |
| SYLLABLOOM_CRAWL_MAX_PAGES | Maximum public source pages examined per import. | 18 |
| SYLLABLOOM_CRAWL_MAX_DEPTH | Maximum same-host link depth from the supplied URL. | 1 |
| SYLLABLOOM_AI_PROVIDER | codex_cli, openai_compatible, or disabled. | codex_cli |
| SYLLABLOOM_AI_BASE_URL | Compatible Chat Completions API base URL. | http://localhost:11434/v1 |
| SYLLABLOOM_AI_MODEL | Model name for a compatible provider. | Provider-specific |
| SYLLABLOOM_AI_API_KEY | Optional compatible-provider key. | Blank for many local servers |

Docker Compose reads the same SYLLABLOOM variables from the environment or a root .env file. Settings can later store values for the running installation.

## Configure providers in Settings

### Bilibili

Bilibili import works out of the box — no key required. **Add a course** pastes a `BV...` video link by default and splits multi-part videos automatically; playback uses the built-in HTML5 player whose quality menu follows your account entitlements. QR sign-in credentials stay in the local database (settings responses only show "configured"), and media bytes are relayed in memory without touching disk. When an import detects a course code (for example CS336) and a matching official course page already exists locally, its assignments are matched into the new course automatically.

### YouTube

Automatic playlist and video metadata comes only from the official YouTube Data API. Create and appropriately restrict an API key in your own Google Cloud project, then paste it in Settings. Manual fallback works for a known public video without a key.

### Obsidian

Choose an existing vault. The application creates a path similar to AI-Learning/course-name/Assignments/assignment-key and uses Answer.md as the shared editable answer. It never overwrites an existing Answer.md and never writes outside the configured vault.

### Codex CLI

Native mode can use a Codex CLI installed and authenticated on the host. Check it in the same terminal environment:

    codex --version

Settings reports whether the executable is discoverable. After an explicit submission confirmation, Syllabloom creates a staged copy and asks Codex for feedback using a read-only sandbox. Codex cannot mutate the working assignment directory.

### OpenAI-compatible endpoint

This supports Ollama, LM Studio, vLLM, OpenAI, and other servers that expose Chat Completions-compatible endpoints. Enter the base URL, model name, and key when needed.

A common native local-server address is:

    http://localhost:11434/v1

For Docker-to-host traffic, use the address shown in the Docker section. A remote endpoint is an external service and may charge for usage or retain staged answer data under its own policy. Syllabloom asks for a fresh checkbox acknowledgement before every request.

### Disabled

Disabled prevents AI review. Public official tests can still run when an imported assignment provides them.

## Language

The first-run UI language is English. Use English or 中文 in the sidebar footer to switch. The link writes a lang query parameter so it works as a normal hyperlink; when browser storage is available, the selection is remembered.

## Data, backups, and updates

Native mode keeps its database and LearningVault below the configured data directory. It includes source downloads, workspaces, snapshots, feedback, and certificates. Stop Syllabloom and copy the complete data directory for the simplest backup.

Docker mode keeps equivalent data in the named volume. Use your normal Docker volume backup process and verify a backup before an upgrade. A Git clone is not a backup: runtime data and secrets are intentionally ignored by Git.

To move a native installation:

1. Stop Syllabloom.
2. Copy the entire data directory.
3. Set SYLLABLOOM_DATA_DIR to the copied location before starting on the new machine.
4. Start Syllabloom and verify the dashboard and assignment history.

Update Docker:

    git pull
    docker compose up --build

Update native:

    git pull
    python scripts/run_local.py

Database migrations run at startup. A database with a complete legacy schema but no Alembic revision is verified and safely stamped. A partial database is not silently treated as current.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Port is already in use | Use native --port 8090, or change 8080:8000 in compose.yaml to an available host port. |
| Docker page does not load | Run docker compose logs -f and confirm Docker Desktop is running. |
| Codex CLI is unavailable | Use native mode, run codex --version in the same shell, then restart after installing or signing in. |
| Docker cannot reach Ollama | Use host.docker.internal instead of localhost and ensure the host server accepts container traffic. |
| Playlist import asks for an API key | Add a YouTube Data API key or use Manual fallback for a public video. |
| Stanford source is protected | This is expected for a login-gated resource. Syllabloom records provenance but will not bypass the gate. |
| Obsidian export fails in Docker | Confirm the host folder is mounted, Settings uses the container path, and the folder is writable. |
| A migration fails | Back up the data directory, inspect the error, and report it without private data. Do not delete the database as the first response. |

## Uninstall

Native mode: stop the server, then remove the repository and only remove the data directory when you deliberately want to erase learning records.

Docker mode: docker compose down removes the service but retains data. Delete the named volume only after deciding to erase everything.
