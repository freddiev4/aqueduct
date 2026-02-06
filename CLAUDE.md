# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**See [TODO.md](./TODO.md) for current implementation status and planned work.**

## Project Overview

Aqueduct is a DAG-based backup system for archiving personal data from various platforms (GitHub, Twitter/X, Instagram, Notion) to local storage (and eventually NAS). It uses Prefect as the workflow orchestration framework to schedule and manage backup tasks.

## Creating New Workflows
When creating a new workflow, first do research around the available APIs and ensure the following:

1. The APIs are not deprecated. The Google Photos workflow for example cannot be made because of the deprecated API.
2. The workflows are able to be automated. If the workflows require a human hand to do authentication for example like the Crunchyroll workflow, the workflow should go in to the `cannot-automate/` directory.

## Subagents
When making new workflows, use the [workflow-builder](.claude/agents/workflow-builder.md) subagent to create the workflow.

Then use the idempotency agent to ensure the workflow is idempotent.

Then use the workflow-testing-agent to test the workflow.

## Development Environment

### Python Version Management

Use `uv` to manage Python versions:

```bash
# Install a specific Python version
uv python install 3.12

# Create venv with specific Python version
uv venv --python 3.12

# List installed Python versions
uv python list
```

**Note**: The Amazon Orders workflow requires Python 3.12 or 3.11 due to dependency constraints (amazon-orders → amazoncaptcha → pillow<9.6.0 cannot build on Python 3.13).

### Setup Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (after modifying pyproject.toml)
uv pip install -e .
```

### Running Prefect Server

Start the Prefect UI and server using Docker:

```bash
docker run -p 4200:4200 --rm prefecthq/prefect:3-latest -- prefect server start --host 0.0.0.0
```

Access the Prefect UI at http://localhost:4200


## Architecture

### Workflow Structure

All backup workflows follow a consistent pattern:

1. **Task-based design**: Each workflow is composed of Prefect `@task` decorated functions for granular operations (authentication, API calls, file downloads, data processing)
2. **Flow orchestration**: A main `@flow` decorated function coordinates tasks and manages the overall backup process
3. **Local-first**: All backups are stored in `./backups/local/` with a hierarchical structure: `platform/username/content-type/`
4. **Metadata preservation**: Each workflow saves both the original content and structured metadata (JSON) for future querying

### Workflow Files

**Working workflows:**
- `workflows/github.py` - Clones repositories and extracts commit history using GitHub GraphQL API
- `workflows/youtube.py` - Downloads videos via yt-dlp
- `workflows/crunchyroll.py` - Downloads anime via multi-downloader-nx
- `workflows/reddit.py` - Downloads saved posts, comments, and upvoted content using PRAW
- `workflows/google_drive.py` - Downloads files and folders with Google Workspace exports using Drive API
- `workflows/amazon.py` - Downloads order history (requires Python 3.12 or 3.11)
- `workflows/example.py` - Template showing basic Prefect flow structure

**Cannot be automated** (in `workflows/cannot-automate/`):
- `workflows/cannot-automate/google_photos.py` - Google deprecated Library API scopes on April 1, 2025. See README in that directory.

**Workflows needing fixes** (in `workflows/to-fix/`):
- `workflows/to-fix/twitter.py` - Downloads tweets, bookmarks, and likes with media files
- `workflows/to-fix/instagram.py` - Downloads user posts and saved posts
- `workflows/to-fix/notion.py` - Exports pages as markdown with embedded media

### Key Patterns

**Credentials Management**: Workflows expect credentials to be:
- Loaded from Prefect Blocks (e.g., `GitHubCredentials.load("github-freddiev4")`)
- Passed as parameters to the main flow function
- Stored in `.env` file (structure defined in `.env.example`, though currently empty)

**Caching**: Most tasks use `cache_policy=NO_CACHE` to ensure fresh data on each run, avoiding stale backups

**Error Handling**: Workflows implement:
- Retry logic for transient API errors (see `get_all_repositories()` in github.py)
- Graceful degradation (continue on individual item failures)
- Detailed logging to stdout

**Date Filtering**: GitHub workflow supports `until_date` parameter to enable incremental backups (only fetch data up to a specific date)

## Common Tasks

### Creating a New Backup Workflow

1. Create a new file in `workflows/` following the pattern: `workflows/platform_name.py`
2. Implement task functions for:
   - Authentication/credential loading
   - Fetching data from the platform API
   - Downloading media/attachments
   - Saving structured metadata
3. Create a main flow function that orchestrates these tasks
4. Follow the backup directory structure: `./backups/local/platform/username/content_type/`
5. Save a metadata summary JSON file with statistics about what was backed up

### Running a Workflow Manually

```bash
# Direct execution (if workflow has __main__ block)
python workflows/github.py

# Using Prefect CLI (requires deployment)
prefect deployment build workflows/example.py:main --name example --cron "0 8 * * *"
prefect deployment run example
```

### Registering Integration Blocks

For workflows that use Prefect integrations:

```bash
# GitHub
prefect block register -m prefect_github
```

Then configure the block through the Prefect UI at http://localhost:4200

## Important Notes

- **No Remote Backup Yet**: Remote NAS backup functionality is commented out in workflows (see `backup_to_remote_filesystem()` in github.py)
- **API Rate Limits**: All workflows use `wait_on_rate_limit=True` or implement retry logic for rate limiting
- **Large Datasets**: Workflows support `max_*` parameters to limit download size during development/testing
- **Authentication**: Most workflows support multiple auth methods (OAuth tokens, API keys, session files) to handle different platform requirements
