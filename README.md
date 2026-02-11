# Aqueduct

A DAG-based backup system for archiving personal data from various platforms (GitHub, Twitter/X, Reddit, YouTube, Google Drive, Amazon, Discord, Crunchyroll) to local storage. It uses [Prefect](https://www.prefect.io/) as the workflow orchestration framework to schedule and manage backup tasks.

## How It Works

Each platform has a dedicated workflow built as a Prefect flow. Workflows handle authentication, API pagination, media downloads, and metadata preservation. All backups are stored locally in a consistent directory structure (`./backups/local/platform/username/content_type/`) with structured JSON metadata for future querying.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) for Python version and dependency management
- Python 3.10 - 3.13 (3.12 or 3.11 required for the Amazon workflow)

## Quick Start

```bash
# Create and activate virtual environment
uv venv --python 3.12
source .venv/bin/activate

# Install dependencies
uv pip install -e .

# Run a workflow directly
python workflows/github.py
```

## Running Prefect

Start the Prefect UI and server using Docker:

```bash
docker run -p 4200:4200 --rm prefecthq/prefect:3-latest -- prefect server start --host 0.0.0.0
```

Access the Prefect UI at http://localhost:4200

## Further Documentation

- **[workflows/README.md](workflows/README.md)** — Detailed setup, usage instructions, and configuration for every backup workflow.
- **[workflows/cannot-automate/README.md](workflows/cannot-automate/README.md)** — Workflows that cannot be fully automated due to API deprecations or platform restrictions (Google Photos, iCloud, LinkedIn).
- **[infra/README.md](infra/README.md)** — Bootstrap script for installing development and DevOps tools (Docker, kubectl, kind, ArgoCD) on new servers.
- **[infra/k8s/README.md](infra/k8s/README.md)** — Kubernetes and ArgoCD infrastructure for deploying Aqueduct workflows via GitOps on a local Kind cluster.
- **[docs/2026-02-05/google-drive/README.md](docs/2026-02-05/google-drive/README.md)** — In-depth Google Drive backup workflow documentation including OAuth setup, incremental backups, and troubleshooting.
