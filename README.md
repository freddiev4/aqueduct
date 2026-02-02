# aqueduct
A repository for DAG-based backup to NAS

## Prerequisites

Ensure [`uv`](https://docs.astral.sh/uv/) is installed following their [official documentation](https://docs.astral.sh/uv/getting-started/installation/).

For the **Gmail workflow**, you'll also need [msgvault](https://msgvault.io):
```bash
curl -fsSL https://msgvault.io/install.sh | bash
```

## Setup Steps

1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. Install dependencies:

```bash
uv pip install -e .
```



## Running Prefect

Start the Prefect UI & server using docker:

```bash
docker run -p 4200:4200 --rm prefecthq/prefect:3-latest -- prefect server start --host 0.0.0.0
```

## Available Workflows

### Working Workflows

- **GitHub** (`workflows/github.py`) - Clones repositories and extracts commit history using GitHub GraphQL API
- **YouTube** (`workflows/youtube.py`) - Downloads videos via yt-dlp
- **Crunchyroll** (`workflows/crunchyroll.py`) - Downloads anime via multi-downloader-nx
- **Gmail** (`workflows/gmail.py`) - Archives Gmail emails using msgvault with SQLite storage and full-text search
- **Example** (`workflows/example.py`) - Template showing basic Prefect flow structure

### Workflows Needing Fixes

- **Twitter/X** (`workflows/to-fix/twitter.py`) - Downloads tweets, bookmarks, and likes with media files
- **Instagram** (`workflows/to-fix/instagram.py`) - Downloads user posts and saved posts
- **Notion** (`workflows/to-fix/notion.py`) - Exports pages as markdown with embedded media

### Cannot Be Automated

- **Google Photos** (`workflows/cannot-automate/google_photos.py`) - Google deprecated Library API scopes on April 1, 2025

## Running Workflows

There are two ways to run a workflow:

1. Directly run the workflow with Python, based on the `__main__` block:

```bash
# Example workflow
python workflows/example.py

# Gmail workflow (with test limit)
python workflows/gmail.py --credentials gmail-credentials --max-messages 10

# GitHub workflow
python workflows/github.py
```

2. Deploy the workflow as a Prefect deployment, and run it:

```bash
prefect deployment build workflows/example.py:main --name example --cron "0 8 * * *"
prefect deployment run example
```

> ![NOTE]
> The `cron` parameter is used to schedule the deployment.
> You need to set the entrypoint to the `main` function of the workflow using the `@flow` decorator, and the function name in the path to the workflow file e.g. `workflows/example.py:main` or `workflows/github.py:backup_github_repositories`

## Registering Integration Blocks

Some workflows require Prefect blocks to be registered before use:

### GitHub

```bash
prefect block register -m prefect_github
```

Then configure the block through the Prefect UI at http://localhost:4200

### Gmail

The Gmail workflow uses a custom `GmailCredentialsBlock` for OAuth credentials. Setup is automated:

```bash
python scripts/setup_gmail.py
```

This script will:
1. Register the custom Gmail block
2. Prompt for your Gmail address and msgvault config directory
3. Create the credentials block in Prefect

For detailed Gmail setup instructions, see [`workflows/GMAIL_README.md`](workflows/GMAIL_README.md)

---

Go to http://localhost:4200 in your browser to see the Prefect UI and manage your workflows.