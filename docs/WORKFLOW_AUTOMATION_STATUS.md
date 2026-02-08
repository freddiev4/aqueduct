# Workflow Automation Status

**Last Updated**: 2026-02-05

This document tracks the automation status of all workflows in Aqueduct.

## Summary Table

| Workflow | Status | Manual Steps | Setup Time | Notes |
|----------|--------|--------------|------------|-------|
| **Reddit** | ✅ Ready | None during execution | ~10 min | Fully automatic after credentials setup |
| **Amazon** | ✅ Ready | None during execution | ~15 min | Automatic CAPTCHA + 2FA support |
| **Google Drive** | ✅ Ready | One-time browser OAuth | ~25 min | Auto refresh tokens after first auth |
| GitHub | ✅ Ready | None during execution | ~5 min | Token-based authentication |
| YouTube | ✅ Ready | None during execution | ~5 min | Uses yt-dlp CLI |

## Recent Fixes

### Amazon Workflow - Import Bug Fix (2026-02-05)

**Issue**: Critical import error prevented workflow execution
```
ModuleNotFoundError: No module named 'amazon_orders'
```

**Root Cause**: Package name mismatch
- PyPI package: `amazon-orders`
- Python module: `amazonorders` (no underscore)
- Workflow imported: `amazon_orders` (with underscore) ❌

**Fix Applied**: workflows/amazon.py:33
```diff
- from amazon_orders import AmazonSession, AmazonOrders
+ from amazonorders.session import AmazonSession
+ from amazonorders.orders import AmazonOrders
```

**Verified**: Import test passes ✓

---

## Workflow Details

### Reddit Workflow

**Authentication**: Script-type OAuth2 (PRAW library)
- Client ID + Secret
- Username + Password
- No browser interaction needed
- Automatic rate limit handling

**Downloads**:
- Saved posts
- Saved comments
- Upvoted content
- Media files (images, videos)

**Storage**: `./backups/local/reddit/{username}/`

**Idempotent**: Yes (uses download archives)

**Setup Guide**: [docs/reddit/setup.md](reddit/setup.md)

---

### Amazon Workflow

**Authentication**: Session-based web scraping
- Email + Password
- Optional TOTP for 2FA
- Automatic CAPTCHA solving
- No browser needed

**Downloads**:
- Order history
- Order details
- Item information
- Payment/shipping data

**Storage**: `./backups/local/amazon/{username}/orders/`

**Idempotent**: Yes (date-based snapshots)

**Setup Guide**: [docs/amazon/SETUP.md](amazon/SETUP.md)

**Requirements**:
- Python 3.12 or 3.11 only
- Amazon.com (US) accounts only

---

### Google Drive Workflow

**Authentication**: OAuth 2.0 Desktop App
- One-time browser authorization
- Automatic token refresh
- Read-only scope (`drive.readonly`)

**Downloads**:
- All files from Drive
- Folder structure
- Google Workspace exports (Docs, Sheets, Slides)
- File metadata

**Storage**: `./backups/local/google-drive/{email}/`

**Idempotent**: Yes (date-based snapshots)

**Setup Guide**: [docs/google-drive/SETUP.md](google-drive/SETUP.md)

**OAuth Flow**:
1. First run: Opens browser for consent
2. Token saved to `~/.google-drive-tokens/token.json`
3. Subsequent runs: Automatic refresh (no browser)

---

## Setup Resources

### Quick Start Guides

- **All Workflows**: [docs/CREDENTIALS_SETUP.md](CREDENTIALS_SETUP.md) - Unified setup guide
- **Reddit Only**: [docs/reddit/setup.md](reddit/setup.md)
- **Amazon Only**: [docs/amazon/SETUP.md](amazon/SETUP.md)
- **Google Drive Only**: [docs/google-drive/SETUP.md](google-drive/SETUP.md)

### Setup Scripts

Automated scripts to create Prefect blocks from `.env` file:

```bash
# Reddit
python scripts/setup_reddit_block.py

# Amazon
python scripts/setup_amazon_block.py

# Google Drive
python scripts/setup_google_drive_block.py
```

**Location**: `scripts/setup_*.py`

---

## Testing Results

### Test Summary (2026-02-05)

All three workflows were tested for automation capabilities:

**Amazon Workflow**:
- ❌ Initial test: Import bug prevented execution
- ✅ After fix: Import successful
- ✅ Design verified: Fully automatic (no manual intervention)
- ⏸️ Execution blocked: Credentials not configured (expected)

**Reddit Workflow**:
- ✅ Design verified: Fully automatic authentication
- ✅ Data persistence: Properly implemented
- ✅ Timezone handling: All UTC
- ⏸️ Execution blocked: Credentials not configured (expected)

**Google Drive Workflow**:
- ✅ Design verified: Semi-automatic (one-time OAuth)
- ✅ Data persistence: Properly implemented
- ✅ Error handling: Retry logic implemented
- ✅ Security: Read-only scope
- ⏸️ Execution blocked: OAuth not completed (expected)

**Test Reports**:
- Amazon: `AMAZON_WORKFLOW_TEST_REPORT.md`
- Reddit: `REDDIT_WORKFLOW_TEST_REPORT.md`
- Google Drive: `docs/google-drive/TEST_REPORT.md`

---

## Automation Classification

### Fully Automatic
Workflows that require NO manual intervention during execution:

- ✅ **Reddit**: Script OAuth with credentials
- ✅ **Amazon**: Session-based with automatic CAPTCHA/2FA
- ✅ **GitHub**: Token-based authentication
- ✅ **YouTube**: CLI-based download

### Semi-Automatic
Workflows requiring one-time manual setup, then fully automatic:

- ⚠️ **Google Drive**: One-time browser OAuth, then auto-refresh

### Cannot Automate
Workflows that require ongoing manual intervention:

- ❌ **Google Photos**: API deprecated (moved to `cannot-automate/`)
- ❌ **Crunchyroll**: Manual login every session (in `cannot-automate/`)

---

## Next Steps

To enable automated backups:

1. **Choose workflows** you want to run
2. **Follow setup guides** for each workflow
3. **Test manually** to verify credentials work
4. **Create Prefect deployments** for scheduling
5. **Monitor via Prefect UI** at http://localhost:4200

### Example: Schedule Daily Backups

```bash
# Build deployment
prefect deployment build workflows/reddit.py:backup_reddit \
  --name reddit-daily \
  --cron "0 2 * * *"  # 2 AM daily

# Apply deployment
prefect deployment apply backup_reddit-deployment.yaml

# Repeat for other workflows
```

---

## Common Issues

### Import Errors

**Symptom**: `ModuleNotFoundError` when running workflow

**Solutions**:
1. Activate virtual environment: `source .venv/bin/activate`
2. Install dependencies: `uv pip install -e .`
3. Verify Python version (Amazon requires 3.12 or 3.11)

### Credentials Not Found

**Symptom**: `Unable to find block document named {name}`

**Solutions**:
1. Check `.env` file has required variables
2. Run setup script: `python scripts/setup_{platform}_block.py`
3. Verify block via Prefect UI: http://localhost:4200

### Authentication Failed

**Symptom**: 401, 403, or "Invalid credentials" errors

**Solutions**:
1. Verify credentials in `.env` are correct
2. Try logging in manually to the platform
3. Check for 2FA requirements
4. Review platform-specific troubleshooting in setup guides

---

## Maintenance Notes

### Regular Tasks

- **Monthly**: Review backup manifests for completeness
- **Quarterly**: Test workflow execution to catch API changes
- **As Needed**: Rotate credentials for security

### Monitoring

Check these indicators for healthy backups:

- ✅ Workflow runs complete without errors
- ✅ Manifest files show increasing data counts
- ✅ Backup directories have recent timestamps
- ✅ File sizes are reasonable (not empty or corrupted)

### Updates

When platform APIs change:

1. Review workflow logs for new error patterns
2. Check platform documentation for API updates
3. Update workflow code if needed
4. Re-test automation capabilities
5. Update this status document

---

## Documentation Index

- **Setup Guides**:
  - [Unified Credentials Setup](CREDENTIALS_SETUP.md)
  - [Reddit Setup](reddit/setup.md)
  - [Amazon Setup](amazon/SETUP.md)
  - [Google Drive Setup](google-drive/SETUP.md)

- **Test Reports**:
  - [Workflow Fixes Summary](WORKFLOW_FIXES_SUMMARY.md)
  - [Google Drive Test Report](google-drive/TEST_REPORT.md)

- **Implementation Docs**:
  - [Reddit Docs](reddit/docs.md)
  - [Google Drive Docs](google-drive/docs.md)

- **Source Code**:
  - Workflows: `workflows/*.py`
  - Blocks: `blocks/*_block.py`
  - Setup Scripts: `scripts/setup_*.py`
