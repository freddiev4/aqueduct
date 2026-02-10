# Amazon Orders Backup - Setup Guide

This guide walks through setting up automated Amazon order history backups.

## Overview

The Amazon workflow downloads your complete order history including:
- Order details and metadata
- Item information
- Pricing and payment data
- Shipping information
- Order timestamps

**Authentication Method**: Session-based web scraping (no official API available)
- Automatic CAPTCHA solving via `amazoncaptcha` library
- Optional 2FA support via TOTP (Time-based One-Time Password)
- No browser interaction required during execution

## Prerequisites

- Python 3.12 or 3.11 (required due to dependency constraints)
- Amazon.com account (US site only)
- Virtual environment activated

## One-Time Setup

### Step 1: Verify Python Version (2 minutes)

The `amazon-orders` library requires Python 3.12 or 3.11 due to dependencies on older versions of Pillow.

```bash
# Check your current Python version
python --version

# If you need Python 3.12, install it with uv
uv python install 3.12

# Create venv with Python 3.12
uv venv --python 3.12

# Activate the virtual environment
source .venv/bin/activate
```

### Step 2: Install Dependencies (1 minute)

Dependencies should already be installed if you ran `uv pip install -e .`. Verify:

```bash
# Check if amazon-orders is installed
python -c "from amazonorders.session import AmazonSession; print('✓ Installed')"
```

If you see an error, install manually:

```bash
uv pip install amazon-orders amazoncaptcha pyotp
```

### Step 3: Get Amazon Credentials (5 minutes)

You'll need your Amazon login credentials:

1. **Email/Username**: Your Amazon account email
2. **Password**: Your Amazon account password
3. **OTP Secret Key** (optional, for 2FA):
   - If you have 2FA enabled, you'll need the TOTP secret key
   - This is the base32 secret shown when you set up 2FA
   - If you don't have it, you may need to reconfigure 2FA to get it

**Security Note**: The workflow uses these credentials to log in via HTTP requests (not a browser). The session is authenticated once and reused.

### Step 4: Add Credentials to Environment (2 minutes)

Add your Amazon credentials to the `.env` file:

```bash
# Open .env file
nano .env
```

Add these lines:

```env
# Amazon Credentials
AMAZON_USERNAME=your-email@example.com
AMAZON_PASSWORD=your-password-here
AMAZON_OTP_SECRET=YOURBASE32SECRETKEY  # Optional, only if you have 2FA
```

**Important**:
- Never commit `.env` to git (it's already in `.gitignore`)
- Keep your credentials secure
- The OTP secret is optional - leave it out if you don't have 2FA enabled

### Step 5: Register Prefect Block (3 minutes)

Create a Prefect block to store your credentials:

```python
# Run this in a Python shell or create a script
from blocks.amazon_block import AmazonBlock
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create and save the block
block = AmazonBlock(
    username=os.getenv("AMAZON_USERNAME"),
    password=os.getenv("AMAZON_PASSWORD"),
    otp_secret_key=os.getenv("AMAZON_OTP_SECRET")  # Optional
)

block.save("amazon-credentials", overwrite=True)
print("✓ Amazon credentials block created successfully")
```

Or create a setup script `scripts/setup_amazon_block.py`:

```python
#!/usr/bin/env python3
"""Setup script for Amazon Prefect block."""

from blocks.amazon_block import AmazonBlock
import os
from dotenv import load_dotenv

def main():
    load_dotenv()

    username = os.getenv("AMAZON_USERNAME")
    password = os.getenv("AMAZON_PASSWORD")
    otp_secret = os.getenv("AMAZON_OTP_SECRET")

    if not username or not password:
        print("❌ Error: AMAZON_USERNAME and AMAZON_PASSWORD must be set in .env")
        return

    block = AmazonBlock(
        username=username,
        password=password,
        otp_secret_key=otp_secret
    )

    block.save("amazon-credentials", overwrite=True)
    print("✓ Amazon credentials block created successfully")

if __name__ == "__main__":
    main()
```

Run it:

```bash
python scripts/setup_amazon_block.py
```

### Step 6: Test the Workflow (5 minutes)

Run a test backup to verify everything works:

```bash
# Activate virtual environment if not already active
source .venv/bin/activate

# Run the workflow
python workflows/amazon.py
```

**What to expect**:
1. Workflow loads credentials from Prefect block
2. Authenticates with Amazon (may take 10-20 seconds)
3. Solves any CAPTCHAs automatically
4. Fetches order history
5. Downloads order details
6. Saves to `./backups/local/amazon/{username}/orders/{date}/`

**First run may take several minutes** depending on how many orders you have.

### Step 7: Verify Backup Files (1 minute)

Check that files were created:

```bash
# List backup directory
ls -la ./backups/local/amazon/

# Check manifest file
cat ./backups/local/amazon/*/orders/*/backup_manifest_*.json | head -20
```

You should see:
- `orders.json` - Complete list of all orders
- `order_{number}.json` - Individual order details
- `backup_manifest_{date}.json` - Backup statistics and metadata

---

## Usage

### Manual Execution

Run a backup for today:

```bash
python workflows/amazon.py
```

### Limited Testing

Test with a subset of orders:

```python
from workflows.amazon import backup_amazon_orders
from datetime import datetime, timezone

# Only download orders from a specific year
backup_amazon_orders(
    snapshot_date=datetime.now(timezone.utc),
    year=2024,  # Only 2024 orders
    max_orders=10  # Limit to 10 orders
)
```

### Scheduled Backups

Create a Prefect deployment for automatic daily backups:

```bash
# Build deployment
prefect deployment build workflows/amazon.py:backup_amazon_orders \
  --name amazon-daily \
  --cron "0 2 * * *"  # 2 AM daily

# Apply deployment
prefect deployment apply backup_amazon_orders-deployment.yaml
```

---

## Troubleshooting

### Import Error: "No module named 'amazon_orders'"

**Issue**: The package name changed from `amazon_orders` to `amazonorders`.

**Fix**: This has been fixed in the workflow. If you see this error, make sure you have the latest version of `workflows/amazon.py`.

### Authentication Failed

**Possible causes**:
1. Incorrect credentials in `.env` file
2. Amazon account locked or requires additional verification
3. 2FA enabled but OTP secret not provided

**Solutions**:
- Verify credentials in `.env` are correct
- Try logging into Amazon.com manually to check account status
- If 2FA is enabled, ensure you have the correct OTP secret key

### CAPTCHA Solving Failed

**Issue**: The workflow couldn't solve the CAPTCHA automatically.

**Possible causes**:
- Network issues
- Amazon changed their CAPTCHA format
- Rate limiting from too many requests

**Solutions**:
- Wait a few minutes and try again
- Check your internet connection
- The workflow will retry automatically (3 attempts)

### Session Expired

**Issue**: Authentication session expired during long-running backup.

**Fix**: The workflow creates a fresh session for each run. If you see this error, simply run the workflow again.

### Rate Limiting

**Issue**: Too many requests to Amazon in a short time.

**Solution**:
- The workflow includes automatic delays between requests
- Wait 10-15 minutes before retrying
- Consider using `max_orders` to limit backup size during testing

### Python Version Error

**Issue**: Dependencies fail to install on Python 3.13+

**Fix**:
```bash
# Install Python 3.12
uv python install 3.12

# Recreate venv with Python 3.12
uv venv --python 3.12
source .venv/bin/activate

# Reinstall dependencies
uv pip install -e .
```

---

## Security Best Practices

1. **Credentials Storage**:
   - Store credentials in `.env` file (never commit to git)
   - Use Prefect blocks to manage credentials securely
   - Consider using a password manager for the OTP secret

2. **2FA Recommendation**:
   - Keep 2FA enabled on your Amazon account
   - Store the OTP secret securely (treat it like a password)
   - Backup the OTP secret in case you need to reconfigure

3. **Access Monitoring**:
   - Check Amazon's "Login & security" page for unusual activity
   - The workflow creates sessions that appear as normal web logins
   - Consider using a dedicated "automation" Amazon account if concerned

4. **Data Protection**:
   - Backup files contain sensitive information (addresses, payment details)
   - Ensure proper file permissions on backup directory
   - Consider encrypting backups if storing on shared systems

---

## Backup Structure

```
./backups/local/amazon/
└── {username}/
    └── orders/
        └── {YYYY-MM-DD}/
            ├── orders.json                    # Complete order list
            ├── order_{number}.json            # Individual order details
            ├── order_{number}.json
            └── backup_manifest_{date}.json    # Backup metadata
```

### File Contents

**orders.json**: Array of all orders with basic information
```json
[
  {
    "order_number": "123-4567890-1234567",
    "order_date": "2024-01-15T18:30:00+00:00",
    "total": "$42.99",
    "items_count": 2
  }
]
```

**order_{number}.json**: Detailed information for each order
```json
{
  "order_number": "123-4567890-1234567",
  "order_date": "2024-01-15T18:30:00+00:00",
  "total": "$42.99",
  "items": [...],
  "shipping_address": {...},
  "payment_method": {...}
}
```

**backup_manifest_{date}.json**: Backup statistics
```json
{
  "snapshot_date": "2026-02-05T12:00:00+00:00",
  "execution_timestamp": "2026-02-05T12:05:30+00:00",
  "username": "user@example.com",
  "statistics": {
    "total_orders": 156,
    "year_filter": null,
    "time_range": "all_time"
  }
}
```

---

## Idempotency

The workflow is **idempotent** - running it multiple times on the same day will not create duplicate backups:

- Checks if snapshot for the date already exists
- If exists, skips backup and exits early
- Safe to run multiple times per day
- Each day gets a new snapshot directory

**To force a new backup** for the same day, delete the existing snapshot directory first.

---

## Limitations

1. **US Amazon.com Only**: The workflow only supports Amazon.com (US site)
2. **Web Scraping**: No official API - may break if Amazon changes their website
3. **No Media Downloads**: Only downloads order metadata (no product images)
4. **Session-Based**: Each run creates a new session (no persistent login)
5. **Python Version**: Requires Python 3.12 or 3.11 due to dependency constraints

---

## Next Steps

After successful setup:

1. **Schedule regular backups** using Prefect deployments
2. **Monitor backup files** to ensure data is being captured correctly
3. **Test restore process** by examining backup JSON files
4. **Consider archiving old backups** to save disk space

---

## Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review workflow logs for error messages
3. Verify credentials are correct in `.env` file
4. Check that Python version is 3.12 or 3.11

**Related Documentation**:
- `workflows/amazon.py` - Workflow source code
- `blocks/amazon_block.py` - Credentials block implementation
- `.env.example` - Environment variable template
