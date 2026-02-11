# Development Guide

## Python Version Management

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

## Setup Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (after modifying pyproject.toml)
uv pip install -e .
```

## Running Prefect Server

Start the Prefect UI and server using Docker:

```bash
docker run -p 4200:4200 --rm prefecthq/prefect:3-latest -- prefect server start --host 0.0.0.0
```

Access the Prefect UI at http://localhost:4200

## Creating a New Backup Workflow

1. Create a new file in `workflows/` following the pattern: `workflows/platform_name.py`
2. **Create a Prefect Block** in `blocks/` if the platform doesn't already have one (e.g., `blocks/platform_block.py`). Every new service needs a credentials block that extends `prefect.blocks.core.Block` with `SecretStr` fields for tokens/keys. See `blocks/discord_block.py` or `blocks/reddit_block.py` for examples. Also add the corresponding env vars to `.env.example`.
3. Implement task functions for:
   - Authentication/credential loading
   - Fetching data from the platform API
   - Downloading media/attachments
   - Saving structured metadata
4. Create a main flow function that orchestrates these tasks
5. Follow the backup directory structure: `./backups/local/platform/username/content_type/`
6. Save a metadata summary JSON file with statistics about what was backed up

## Running a Workflow Manually

```bash
# Direct execution (if workflow has __main__ block)
python workflows/github.py

# Using Prefect CLI (requires deployment)
prefect deployment build workflows/example.py:main --name example --cron "0 8 * * *"
prefect deployment run example
```

## Registering Integration Blocks

For workflows that use Prefect integrations:

```bash
# GitHub
prefect block register -m prefect_github
```

Then configure the block through the Prefect UI at http://localhost:4200
