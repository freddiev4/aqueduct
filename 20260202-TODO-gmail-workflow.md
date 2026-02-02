# Gmail Backup Workflow with msgvault

## Objective
Create a Prefect-based workflow that integrates msgvault (https://msgvault.io) to backup Gmail emails locally following aqueduct's established patterns.

## Tasks
- [x] Research msgvault CLI commands and capabilities
- [x] Analyze existing workflow patterns (github.py, youtube.py)
- [x] Create GmailCredentialsBlock for OAuth credentials
- [x] Implement msgvault binary check/installation task
- [x] Implement database initialization task
- [x] Implement account registration task (OAuth)
- [x] Implement full sync task
- [x] Implement incremental sync task
- [x] Implement metadata extraction task (stats, counts)
- [x] Implement main flow orchestration
- [x] Create comprehensive documentation (GMAIL_README.md)
- [x] Create setup script for credential registration
- [ ] Test workflow locally (requires msgvault OAuth setup)
- [ ] Submit for code review

## Implementation Complete

All core workflow components have been implemented:

1. **blocks/gmail_block.py** - GmailCredentialsBlock for managing Gmail credentials
2. **workflows/gmail.py** - Complete Prefect workflow with 8 tasks and main flow
3. **workflows/GMAIL_README.md** - Comprehensive documentation (usage, examples, troubleshooting)
4. **scripts/setup_gmail.py** - Interactive setup script for credential registration

## Design Notes

### Storage Structure
```
./backups/local/gmail/
  {email_address}/
    {date}/
      msgvault.db           # SQLite database
      cache/                # Parquet files
      attachments/          # Content-addressed attachments
      backup_metadata.json  # Workflow metadata
```

### msgvault CLI Commands to Use
- `msgvault init-db` - Initialize SQLite database
- `msgvault add-account` - Register Gmail account (OAuth)
- `msgvault sync-full --limit N` - Initial sync (for testing)
- `msgvault sync-incremental` - Fast incremental updates
- `msgvault stats` - Get email counts and statistics
- `msgvault build-cache` - Generate Parquet files

### Credential Management
- Follow GitHubBlock pattern
- Store OAuth credentials in Prefect Block
- Support multiple Gmail accounts

### Key Workflow Features
- Idempotent syncs (msgvault handles this natively via History API)
- Retry logic for API rate limits
- Proper logging and error handling
- Support for max_emails parameter (testing)
- Metadata JSON with stats (email count, attachment count, size)

## Implementation Status
- Started: 2026-02-02
- Completed: 2026-02-02
- Status: Ready for Testing & Review

## Files Created

1. `/Users/freddie-mac-mini/aqueduct/blocks/gmail_block.py` (85 lines)
   - GmailCredentialsBlock class
   - Email and config directory management
   - Database path helper methods

2. `/Users/freddie-mac-mini/aqueduct/workflows/gmail.py` (735 lines)
   - 8 Prefect tasks (check/install msgvault, init db, OAuth, sync, stats, cache)
   - Main backup_gmail flow with comprehensive error handling
   - CLI interface with argparse
   - Retry logic (3x for syncs with backoff)
   - Timeout handling (2h for full sync, 10m for incremental)

3. `/Users/freddie-mac-mini/aqueduct/workflows/GMAIL_README.md` (328 lines)
   - Complete usage documentation
   - Setup instructions (msgvault, OAuth, Prefect blocks)
   - CLI and Python API examples
   - Query examples (msgvault CLI, DuckDB, SQLite)
   - Troubleshooting guide
   - Multi-account setup

4. `/Users/freddie-mac-mini/aqueduct/scripts/setup_gmail.py` (128 lines)
   - Interactive credential setup
   - Block registration automation
   - Next steps guidance

## Next Steps for User

1. Run `scripts/setup_gmail.py` to register credentials
2. Install msgvault: `curl -fsSL https://msgvault.io/install.sh | bash`
3. Setup Gmail OAuth following msgvault docs
4. Test with: `python workflows/gmail.py --credentials gmail-credentials --max-messages 10`
5. Run full backup: `python workflows/gmail.py --credentials gmail-credentials`
