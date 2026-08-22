# Contributing

Thanks for helping make local-first learning tools more useful and trustworthy.

## Local development

Install Python 3.11+ and Node.js 22.22.2+ (LTS), 24.15+, or a newer compatible release, then run:

    python scripts/run_local.py --reload

The command creates the local environment, builds the frontend, applies migrations, and starts one web server.

Before opening a pull request, run:

    cd backend
    ../.venv/Scripts/python -m pytest -q

    cd ../frontend
    npm test
    npm run build

Use the platform-appropriate .venv Python path on macOS or Linux.

## Pull requests

- Keep each change scoped and include tests for behavior changes.
- Do not commit data, certificate PDFs, Obsidian vaults, API keys, local databases, or downloaded course materials.
- Update user-facing documentation when installation, privacy boundaries, or configuration changes.
- Preserve the public-source and authentication-boundary rules. Features must not bypass login gates, scrape protected material, or represent AI-generated work as official coursework.
- Do not add an automatic cloud upload path. Any AI provider request must remain user-configured and require an explicit, per-submission acknowledgement.

## Reporting bugs

Use the bug report template for reproducible defects. For a potential security issue, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
