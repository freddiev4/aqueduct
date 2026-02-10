# Reddit Workflow Setup Guide

This guide explains how to set up and use the Reddit backup workflow to archive your saved posts, comments, and upvoted content.

## Prerequisites

1. **Python dependencies**:
   ```bash
   pip install praw requests
   ```

2. **Reddit account** with content to backup

3. **Reddit API application** (instructions below)

## Creating a Reddit API Application

1. Go to https://www.reddit.com/prefs/apps

2. Scroll to the bottom and click **"create app"** or **"create another app"**

3. Fill in the application details:
   - **name**: Choose any name (e.g., "aqueduct-backup")
   - **App type**: Select **"script"**
   - **description**: Optional
   - **about url**: Optional
   - **redirect uri**: Enter `http://localhost:8080`

4. Click **"create app"**

5. Note your credentials:
   - **client_id**: The string under the app name (at least 14 characters)
   - **client_secret**: The string next to "secret" (at least 27 characters)

## Configuring Credentials

### Option 1: Using Prefect Blocks (Recommended)

1. Ensure the Prefect server is running:
   ```bash
   docker run -p 4200:4200 --rm prefecthq/prefect:3-latest -- prefect server start --host 0.0.0.0
   ```

2. Set environment variables:
   ```bash
   export REDDIT_CLIENT_ID="your_client_id_here"
   export REDDIT_CLIENT_SECRET="your_client_secret_here"
   export REDDIT_USERNAME="your_reddit_username"
   export REDDIT_PASSWORD="your_reddit_password"
   ```

3. Register the Reddit block:
   ```bash
   python -c "
   import os
   from blocks.reddit_block import RedditBlock

   block_id = RedditBlock(
       client_id=os.environ['REDDIT_CLIENT_ID'],
       client_secret=os.environ['REDDIT_CLIENT_SECRET'],
       username=os.environ['REDDIT_USERNAME'],
       password=os.environ['REDDIT_PASSWORD'],
       user_agent='aqueduct:backup:v1.0.0 (by /u/YOUR_USERNAME)',
   ).save('reddit-credentials', overwrite=True)

   print(f'Reddit block saved. ID: {block_id}')
   "
   ```

### Option 2: Using .env File

1. Create a `.env` file in the project root:
   ```bash
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   REDDIT_USERNAME=your_reddit_username
   REDDIT_PASSWORD=your_reddit_password
   ```

2. The workflow will load these automatically via `python-dotenv`

## Running the Workflow

### Basic Usage

```python
from datetime import datetime, timezone
from workflows.reddit import backup_reddit_content

# Backup all content types
results = backup_reddit_content(
    snapshot_date=datetime.now(timezone.utc),
    credentials_block_name="reddit-credentials",
    content_types=["saved", "comments", "upvoted"],
    limit=None,  # Fetch all available items
    download_media=True,
)

print(results)
```

### Command Line Usage

```bash
# Backup with default settings
python workflows/reddit.py

# Or run via Prefect CLI
prefect deployment run backup-reddit-content
```

### Content Types

The workflow supports three content types:

- **saved**: Your saved posts and comments
- **comments**: Your comment history
- **upvoted**: Posts and comments you've upvoted

You can backup all three or select specific types:

```python
# Only backup saved content
backup_reddit_content(
    snapshot_date=datetime.now(timezone.utc),
    content_types=["saved"],
)

# Backup saved and comments only
backup_reddit_content(
    snapshot_date=datetime.now(timezone.utc),
    content_types=["saved", "comments"],
)
```

### Testing with Limited Items

For testing, use the `limit` parameter:

```python
# Only fetch first 10 items of each type
backup_reddit_content(
    snapshot_date=datetime.now(timezone.utc),
    content_types=["saved", "comments", "upvoted"],
    limit=10,
    download_media=False,  # Skip media downloads for faster testing
)
```

## Backup Structure

Backups are stored in `./backups/local/reddit/{username}/` with the following structure:

```
./backups/local/reddit/
└── your_username/
    ├── saved/
    │   ├── 2026-02-05/
    │   │   ├── saved.json              # All saved items
    │   │   ├── t3_abc123.json          # Individual submission
    │   │   ├── t1_def456.json          # Individual comment
    │   │   └── media/
    │   │       ├── abc123.jpg          # Downloaded images
    │   │       └── def456.mp4          # Downloaded videos
    │   ├── backup_manifest_2026-02-05.json
    │   └── download_archive.txt        # Tracks downloaded media
    ├── comments/
    │   ├── 2026-02-05/
    │   │   ├── comments.json
    │   │   └── t1_xyz789.json
    │   └── backup_manifest_2026-02-05.json
    └── upvoted/
        ├── 2026-02-05/
        │   ├── upvoted.json
        │   ├── t3_uvw012.json
        │   └── media/
        └── backup_manifest_2026-02-05.json
```

## Idempotency Features

The workflow is designed to be idempotent, meaning you can safely re-run it multiple times:

1. **Snapshot dates**: Each backup is organized by snapshot date. Re-running with the same date skips existing backups.

2. **Download archive**: Media downloads are tracked in `download_archive.txt`. Already-downloaded items are skipped.

3. **Reddit IDs**: All files use Reddit's unique IDs (e.g., `t3_abc123` for submissions, `t1_def456` for comments) for consistent naming.

4. **Deterministic sorting**: API results are sorted by Reddit ID before processing to ensure consistent ordering.

## Metadata

Each backup includes metadata files:

### Per-content-type JSON (`saved.json`, `comments.json`, `upvoted.json`)
```json
{
  "snapshot_date": "2026-02-05T00:00:00+00:00",
  "snapshot_date_str": "2026-02-05",
  "backup_timestamp": "2026-02-05T12:34:56+00:00",
  "username": "your_username",
  "content_type": "saved",
  "item_count": 42,
  "items": [...]
}
```

### Per-item JSON (e.g., `t3_abc123.json`)
```json
{
  "reddit_id": "abc123",
  "fullname": "t3_abc123",
  "type": "submission",
  "title": "Interesting post title",
  "author": "post_author",
  "subreddit": "subreddit_name",
  "url": "https://example.com/content",
  "permalink": "https://www.reddit.com/r/subreddit/comments/abc123/...",
  "selftext": "Post content here...",
  "score": 1234,
  "created_utc": "2026-01-15T10:30:00+00:00",
  "media_type": "image",
  "media_url": "https://i.redd.it/..."
}
```

### Backup manifest (`backup_manifest_2026-02-05.json`)
```json
{
  "snapshot_date": "2026-02-05T00:00:00+00:00",
  "execution_timestamp": "2026-02-05T12:34:56+00:00",
  "workflow_version": "1.0.0",
  "username": "your_username",
  "content_type": "saved",
  "item_count": 42,
  "media_downloaded": 15,
  "processing_duration_seconds": 123.45
}
```

## Media Downloads

The workflow supports downloading:

- **Images**: JPG, PNG, GIF
- **Videos**: Reddit-hosted videos (MP4)
- **Galleries**: Multiple images from gallery posts

To skip media downloads (faster backups):

```python
backup_reddit_content(
    snapshot_date=datetime.now(timezone.utc),
    download_media=False,
)
```

## Rate Limits

Reddit's API has rate limits:

- **OAuth2 authenticated requests**: ~60 requests per minute
- **PRAW automatically handles rate limiting** with built-in delays

For large backups (1000+ items), the workflow may take several minutes.

## Troubleshooting

### Authentication Errors

**Error: "invalid_grant" or "incorrect username/password"**
- Verify your username and password are correct
- If using 2FA, append your 2FA token to the password: `password:123456`

**Error: "invalid_client"**
- Check your client_id and client_secret
- Ensure your app type is "script"

### No Items Found

**Error: "No saved items found"**
- Verify you have saved/upvoted content on Reddit
- Check if your Reddit account has access restrictions

### Media Download Failures

**Error: "Failed to download media"**
- Some media URLs may be expired or deleted
- The workflow continues with other downloads and logs errors

## Advanced Usage

### Incremental Backups

Run daily backups with different snapshot dates:

```python
from datetime import datetime, timezone

# Daily backup
backup_reddit_content(
    snapshot_date=datetime.now(timezone.utc),
    content_types=["saved", "comments"],
)
```

### Scheduled Backups with Prefect

Create a Prefect deployment for automated backups:

```bash
# Build deployment
prefect deployment build workflows/reddit.py:backup_reddit_content \
    --name reddit-daily-backup \
    --cron "0 2 * * *"  # Run at 2 AM daily

# Apply deployment
prefect deployment apply backup_reddit_content-deployment.yaml
```

## Privacy & Security

- **Credentials**: Never commit credentials to version control
- **Backup storage**: Keep backups secure, they contain your private Reddit history
- **Media content**: Respect copyright and content policies
- **Rate limits**: Follow Reddit's API terms of service

## References

- [PRAW Documentation](https://praw.readthedocs.io/en/stable/)
- [Reddit API Rules](https://www.reddit.com/wiki/api)
- [Reddit App Preferences](https://www.reddit.com/prefs/apps)

## Sources

- [PRAW Authentication Guide](https://praw.readthedocs.io/en/stable/getting_started/authentication.html)
- [PRAW Redditor Model](https://praw.readthedocs.io/en/stable/code_overview/models/redditor.html)
- [PRAW ListingGenerator](https://praw.readthedocs.io/en/stable/code_overview/other/listinggenerator.html)
