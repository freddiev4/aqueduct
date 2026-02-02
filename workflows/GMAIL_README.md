# Gmail Backup Workflow

Automated Gmail backup workflow using [msgvault](https://msgvault.io) - a Go-based tool that downloads and archives Gmail emails locally with SQLite, Parquet analytics, and content-addressed attachment storage.

## Overview

This workflow provides:
- Full and incremental Gmail backup
- Local SQLite storage with full-text search (FTS5)
- Parquet files for fast analytics via DuckDB
- Content-addressed attachment deduplication
- OAuth authentication via msgvault
- Idempotent syncs using Gmail History API
- Comprehensive metadata and statistics

## Storage Structure

```
./backups/local/gmail/
  {email_address}/
    {date}/
      msgvault.db           # SQLite database with emails
      cache/                # Parquet files for analytics
      attachments/          # Content-addressed attachments
      backup_metadata.json  # Workflow execution metadata
```

## Prerequisites

### 1. Install msgvault

The workflow will attempt to auto-install msgvault, but you can install it manually:

```bash
curl -fsSL https://msgvault.io/install.sh | bash
```

Verify installation:
```bash
msgvault --help
```

### 2. Setup Gmail OAuth Credentials

Follow msgvault's OAuth setup guide: https://msgvault.io/guides/oauth-setup/

You'll need to:
1. Create a Google Cloud Project
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Configure consent screen
5. Download credentials JSON

### 3. Register Prefect Block

Create a GmailCredentialsBlock for your Gmail account:

```python
from blocks.gmail_block import GmailCredentialsBlock

block = GmailCredentialsBlock(
    email="your.email@gmail.com"
)
block.save("gmail-credentials", overwrite=True)
```

Or use environment variables:

```bash
export GMAIL_ADDRESS="your.email@gmail.com"
python blocks/gmail_block.py
```

## Usage

### Command Line

**Full backup (initial sync) - recommended for servers:**
```bash
python workflows/gmail.py --credentials gmail-credentials --headless
```

**Incremental backup (fast, after initial sync):**
```bash
python workflows/gmail.py --credentials gmail-credentials --incremental --headless
```

**Test with limited messages:**
```bash
python workflows/gmail.py --credentials gmail-credentials --max-messages 100 --headless
```

**Date range filtering:**
```bash
python workflows/gmail.py \
  --credentials gmail-credentials \
  --after 2024-01-01 \
  --before 2024-12-31 \
  --headless
```

**Interactive mode (local development with browser):**
```bash
python workflows/gmail.py --credentials gmail-credentials
```

### Python API

```python
from datetime import datetime, timezone
from workflows.gmail import backup_gmail

result = backup_gmail(
    credentials_block_name="gmail-credentials",
    snapshot_date=datetime.now(timezone.utc),
    incremental=False,  # Use True for incremental sync
    max_messages=None,  # None for unlimited
    after_date="2024-01-01",  # Optional date filter
    before_date="2024-12-31",  # Optional date filter
    headless=True,  # Recommended for servers/automation
)

print(f"Backed up to: {result['backup_dir']}")
print(f"Email count: {result['statistics']}")
```

### Prefect Deployment

Schedule regular incremental backups:

```python
from workflows.gmail import backup_gmail

if __name__ == "__main__":
    backup_gmail.serve(
        name="gmail-backup-daily",
        parameters={
            "credentials_block_name": "gmail-credentials",
            "incremental": True,
            "headless": True,  # Required for server deployments
        },
        cron="0 2 * * *",  # Daily at 2 AM
    )
```

## Workflow Tasks

### Core Tasks

1. **ensure_msgvault()** - Verify msgvault binary is installed, attempt installation if missing
2. **initialize_database()** - Create SQLite database if it doesn't exist
3. **add_gmail_account()** - Register Gmail account via OAuth (interactive or headless)
4. **sync_gmail_full()** - Download complete email history (with optional filters)
5. **sync_gmail_incremental()** - Fast sync using Gmail History API (only new/changed emails)
6. **get_email_statistics()** - Extract counts and metrics from database
7. **build_parquet_cache()** - Generate Parquet files for analytics
8. **save_backup_metadata()** - Save workflow execution metadata

### Task Characteristics

- **Idempotency**: Database initialization and account registration are idempotent
- **Retries**: Sync tasks retry 3x with 30-60s delays for transient failures
- **Timeouts**: Full sync: 2 hours, Incremental: 10 minutes
- **Caching**: Uses `NO_CACHE` policy for fresh data on each run

## OAuth Authentication

msgvault supports two OAuth flows:

### Headless (Recommended for Servers/Automation)
Uses device authorization flow - displays a URL and code to enter in any browser:
```bash
python workflows/gmail.py --credentials gmail-credentials --headless
```

**When to use:**
- Running on a server without a display
- CI/CD pipelines
- Scheduled automation workflows
- SSH sessions

The workflow will display a URL like `https://www.google.com/device` and a device code. Open this URL on any device (phone, laptop, etc.), sign in to your Gmail account, and enter the code to authorize.

### Interactive (Local Development)
Opens browser automatically for OAuth consent:
```bash
python workflows/gmail.py --credentials gmail-credentials
```

**When to use:**
- Local development with a browser available
- One-time manual backups on your workstation

After initial OAuth (either method), credentials are stored in `~/.msgvault/tokens/` and reused for future syncs with automatic token refresh.

## Performance

### Initial Sync
- **Duration**: Depends on email volume and Gmail API rate limits
- **Rate Limits**: ~250 messages/second (Gmail API quota)
- **Large Accounts**: 10,000 emails ≈ 40 seconds, 100,000 emails ≈ 7 minutes
- **Resumability**: Supports checkpoints for interrupted syncs

### Incremental Sync
- **Duration**: Typically 5-30 seconds
- **API**: Uses Gmail History API for efficient change detection
- **Frequency**: Can run every 15 minutes without rate limit issues

## Querying Your Archive

### Using msgvault CLI

**Search emails:**
```bash
msgvault search "from:someone@example.com subject:important"
```

**Statistics:**
```bash
msgvault stats
```

**Top senders:**
```bash
msgvault list-senders --limit 20
```

**Export individual email:**
```bash
msgvault export-eml --gmail-id abc123 --output email.eml
```

### Using DuckDB

```sql
-- Connect to Parquet cache
INSTALL parquet;
LOAD parquet;

-- Query emails
SELECT date, from_email, subject
FROM read_parquet('./backups/local/gmail/your@email.com/cache/*.parquet')
WHERE date >= '2024-01-01'
ORDER BY date DESC
LIMIT 100;
```

### Using Python + SQLite

```python
import sqlite3

conn = sqlite3.connect('./backups/local/gmail/your@email.com/2026-02-02/msgvault.db')
cursor = conn.cursor()

# Full-text search
cursor.execute("""
    SELECT subject, from_email, date
    FROM emails
    WHERE emails MATCH 'important project'
    ORDER BY date DESC
    LIMIT 10
""")

for row in cursor.fetchall():
    print(row)
```

## Metadata Structure

Each backup generates `backup_metadata.json`:

```json
{
  "backup_timestamp": "2026-02-02T10:30:00Z",
  "snapshot_date": "2026-02-02T00:00:00Z",
  "workflow_version": "1.0.0",
  "email": "your@email.com",
  "sync_duration_seconds": 45.2,
  "sync_success": true,
  "total_workflow_duration_seconds": 52.8,
  "statistics": {
    "total_messages": 12453,
    "total_attachments": 3421,
    "total_size_mb": 1842.3
  },
  "database_path": "./backups/local/gmail/your@email.com/2026-02-02/msgvault.db",
  "cache_path": "./backups/local/gmail/your@email.com/2026-02-02/cache"
}
```

## Error Handling

The workflow handles:

- **Missing msgvault**: Auto-installation attempt
- **OAuth failures**: Clear error messages with manual setup instructions
- **API rate limits**: Automatic retries with exponential backoff (3 attempts)
- **Network interruptions**: Resumable checkpoints (run again to continue)
- **Database corruption**: Detected via msgvault's verify command (run manually)

Failed backups still generate metadata with error details.

## Troubleshooting

### msgvault not found
```bash
# Manual installation
curl -fsSL https://msgvault.io/install.sh | bash

# Add to PATH
export PATH="$HOME/.msgvault/bin:$PATH"
```

### OAuth errors
```bash
# Re-register account
msgvault add-account --headless

# Check config
cat ~/.msgvault/config.toml
```

### Sync failures
```bash
# Verify database
msgvault verify --sample-size 100

# Force full resync (discard checkpoints)
python workflows/gmail.py --credentials gmail-credentials --max-messages 0
```

### Database locked errors
```bash
# Close all msgvault processes
pkill msgvault

# Check for stale locks
rm -f ~/.msgvault/*.lock
```

## Multi-Account Support

To backup multiple Gmail accounts:

```python
# Register blocks for each account
for email in ["account1@gmail.com", "account2@gmail.com"]:
    block = GmailCredentialsBlock(email=email)
    block_name = f"gmail-{email.split('@')[0]}"
    block.save(block_name, overwrite=True)

# Run backups
from workflows.gmail import backup_gmail

for block_name in ["gmail-account1", "gmail-account2"]:
    result = backup_gmail(
        credentials_block_name=block_name,
        incremental=True
    )
```

## Security Considerations

1. **OAuth Tokens**: Stored in `~/.msgvault/` (600 permissions)
2. **Database**: Contains full email content (encrypt filesystem if needed)
3. **Attachments**: Content-addressed (deduplicated by SHA256 hash)
4. **API Keys**: Never store in code or Git (use Prefect Blocks)

## Future Enhancements

- [ ] NAS/remote storage sync
- [ ] Email retention policies (auto-delete old backups)
- [ ] Notification integration (email/Slack on backup completion)
- [ ] Multi-account parallel sync
- [ ] Backup verification (compare with Gmail API)
- [ ] Export to mbox/Maildir formats
- [ ] Integration with full-text search UI (msgvault TUI)

## References

- [msgvault documentation](https://msgvault.io)
- [msgvault CLI reference](https://msgvault.io/cli-reference)
- [Gmail API documentation](https://developers.google.com/gmail/api)
- [Prefect documentation](https://docs.prefect.io)

## License

This workflow is part of the Aqueduct project. See main repository LICENSE.
