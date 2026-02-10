# Credentials Setup Guide

This guide covers credential setup for automated workflows in Aqueduct. Follow the sections for the workflows you want to run.

## Quick Start

Each workflow requires one-time credential setup:

| Workflow | Setup Time | Manual Steps During Execution | Complexity |
|----------|------------|-------------------------------|------------|
| **Reddit** | ~10 min | None (fully automatic) | ⭐ Easy |
| **Amazon** | ~15 min | None (fully automatic) | ⭐⭐ Medium |
| **Google Drive** | ~25 min | One-time browser OAuth | ⭐⭐⭐ Advanced |

---

## Reddit Workflow Setup

**Automation Status**: ✅ Fully automatic (no manual intervention during execution)

### Prerequisites
- Reddit account
- Python virtual environment activated

### Step-by-Step Setup (~10 minutes)

#### 1. Create Reddit App (5 minutes)

1. Go to https://www.reddit.com/prefs/apps
2. Scroll to bottom and click **"create another app..."**
3. Fill in the form:
   - **Name**: `Aqueduct Backup` (or any name you want)
   - **App type**: Select **"script"** (important!)
   - **Description**: `Personal data backup automation`
   - **About url**: Leave blank
   - **Redirect uri**: `http://localhost:8080` (required but not used)
4. Click **"create app"**
5. Note the credentials shown:
   - **Client ID**: The string under "personal use script" (e.g., `abc123def456`)
   - **Client Secret**: The string next to "secret" (e.g., `XYZ789...`)

#### 2. Add Credentials to .env (2 minutes)

Open your `.env` file and add:

```env
# Reddit Credentials
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
```

**Important**:
- Use your actual Reddit username and password
- Do NOT use email address for username
- Never commit `.env` to git

#### 3. Create Prefect Block (2 minutes)

Run this Python script to register credentials:

```python
from blocks.reddit_block import RedditBlock
import os
from dotenv import load_dotenv

load_dotenv()

block = RedditBlock(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD")
)

block.save("reddit-credentials", overwrite=True)
print("✓ Reddit credentials configured")
```

Or create `scripts/setup_reddit_block.py` and run:
```bash
python scripts/setup_reddit_block.py
```

#### 4. Test the Workflow (1 minute)

```bash
python workflows/reddit.py
```

**Expected behavior**:
- Authenticates automatically (no browser needed)
- Downloads saved posts, comments, and upvoted content
- Saves to `./backups/local/reddit/{username}/`

### Troubleshooting

**"Invalid credentials"**:
- Verify client ID and secret are correct
- Ensure username is your Reddit username (not email)
- Check that app type is "script" not "web app"

**"401 Unauthorized"**:
- Password may be incorrect
- Try logging into Reddit manually to verify credentials

---

## Amazon Workflow Setup

**Automation Status**: ✅ Fully automatic (automatic CAPTCHA solving + 2FA support)

### Prerequisites
- Amazon.com account (US only)
- Python 3.12 or 3.11 (required due to dependencies)
- Virtual environment activated

### Step-by-Step Setup (~15 minutes)

#### 1. Verify Python Version (2 minutes)

```bash
# Check current version
python --version

# If you need Python 3.12
uv python install 3.12
uv venv --python 3.12
source .venv/bin/activate

# Verify installation
python -c "from amazonorders.session import AmazonSession; print('✓ Ready')"
```

#### 2. Get Amazon Credentials (5 minutes)

You'll need:
- **Username**: Your Amazon account email
- **Password**: Your Amazon account password
- **OTP Secret** (optional): If you have 2FA enabled

**For 2FA users**:
- You need the TOTP secret key (base32 string shown when setting up 2FA)
- If you don't have it, you may need to reconfigure 2FA
- This allows automatic OTP code generation

#### 3. Add Credentials to .env (2 minutes)

```env
# Amazon Credentials
AMAZON_USERNAME=your-email@example.com
AMAZON_PASSWORD=your-password-here
AMAZON_OTP_SECRET=YOURBASE32SECRET  # Optional, only if 2FA enabled
```

#### 4. Create Prefect Block (2 minutes)

```python
from blocks.amazon_block import AmazonBlock
import os
from dotenv import load_dotenv

load_dotenv()

block = AmazonBlock(
    username=os.getenv("AMAZON_USERNAME"),
    password=os.getenv("AMAZON_PASSWORD"),
    otp_secret_key=os.getenv("AMAZON_OTP_SECRET")  # Optional
)

block.save("amazon-credentials", overwrite=True)
print("✓ Amazon credentials configured")
```

Or use `scripts/setup_amazon_block.py`:
```bash
python scripts/setup_amazon_block.py
```

#### 5. Test the Workflow (4 minutes)

```bash
python workflows/amazon.py
```

**Expected behavior**:
- Authenticates with Amazon via HTTP requests (no browser)
- Solves CAPTCHAs automatically
- Generates 2FA codes if needed
- Downloads order history
- Saves to `./backups/local/amazon/{username}/orders/`

**First run may take several minutes** depending on order count.

### Troubleshooting

**Import Error**:
- Ensure you fixed the import bug (should be `from amazonorders.session import ...`)
- Verify dependencies installed: `uv pip install amazon-orders`

**Authentication Failed**:
- Check credentials in `.env` are correct
- Try logging into Amazon.com manually
- If 2FA enabled, verify OTP secret is correct

**CAPTCHA Solving Failed**:
- Retry after a few minutes
- Workflow has automatic retry logic (3 attempts)
- Network issues can cause this

**Python 3.13+ Error**:
- Must use Python 3.12 or 3.11
- Recreate venv: `uv venv --python 3.12`

---

## Google Drive Workflow Setup

**Automation Status**: ⚠️ Semi-automatic (one-time browser OAuth, then fully automatic)

### Prerequisites
- Google account
- Google Cloud Console access
- Python virtual environment activated

### Step-by-Step Setup (~25 minutes)

#### 1. Google Cloud Console Setup (15 minutes)

##### 1a. Create Project
1. Go to https://console.cloud.google.com/
2. Click project dropdown → **"New Project"**
3. Name: `Aqueduct Backup` (or your choice)
4. Click **"Create"**
5. Wait for project creation (10-20 seconds)

##### 1b. Enable Google Drive API
1. Ensure your new project is selected
2. Go to **APIs & Services** → **Library**
3. Search for **"Google Drive API"**
4. Click **"Google Drive API"** result
5. Click **"Enable"**
6. Wait for API activation

##### 1c. Configure OAuth Consent Screen
1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **"External"** user type (unless you have Google Workspace)
3. Click **"Create"**
4. Fill in required fields:
   - **App name**: `Aqueduct Backup`
   - **User support email**: Your email
   - **Developer contact**: Your email
5. Click **"Save and Continue"**
6. On "Scopes" page, click **"Save and Continue"** (we'll use default scopes)
7. On "Test users" page:
   - Click **"Add Users"**
   - Enter your Google account email
   - Click **"Add"**
8. Click **"Save and Continue"**
9. Review summary and click **"Back to Dashboard"**

##### 1d. Create OAuth Credentials
1. Go to **APIs & Services** → **Credentials**
2. Click **"+ Create Credentials"** → **"OAuth client ID"**
3. Application type: **"Desktop app"**
4. Name: `Aqueduct Desktop Client`
5. Click **"Create"**
6. Download the credentials JSON file
7. Save as `~/.google-drive-credentials/credentials.json`

```bash
# Create directory and move credentials file
mkdir -p ~/.google-drive-credentials
mv ~/Downloads/client_secret_*.json ~/.google-drive-credentials/credentials.json
```

#### 2. Set Environment Variable (1 minute)

Add to `.env`:

```env
# Google Drive Credentials
GOOGLE_DRIVE_CREDENTIALS_PATH=/Users/YOUR_USERNAME/.google-drive-credentials/credentials.json
```

Or set in shell (add to `~/.bashrc` or `~/.zshrc` for persistence):

```bash
export GOOGLE_DRIVE_CREDENTIALS_PATH="$HOME/.google-drive-credentials/credentials.json"
```

#### 3. Create Prefect Block (2 minutes)

```python
from blocks.google_drive_block import GoogleDriveBlock
import os
from dotenv import load_dotenv

load_dotenv()

credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH")

block = GoogleDriveBlock(credentials_path=credentials_path)
block.save("google-drive-credentials", overwrite=True)

print("✓ Google Drive credentials block configured")
```

Or use `scripts/setup_google_drive_block.py`:
```bash
python scripts/setup_google_drive_block.py
```

#### 4. Complete OAuth Authorization (5 minutes)

Run the workflow for the first time:

```bash
python workflows/google_drive.py
```

**What happens**:
1. Browser opens automatically to Google login
2. You'll see: "Aqueduct Backup wants to access your Google Account"
3. Click **"Allow"**
4. You may see a warning about "unverified app" (this is normal for personal projects)
   - Click **"Advanced"** → **"Go to Aqueduct Backup (unsafe)"**
5. Click **"Allow"** again to grant permissions
6. See "Authentication successful!" message in browser
7. Token saved to `~/.google-drive-tokens/token.json`

**This browser step only happens once.** Subsequent runs use the saved token.

#### 5. Verify Backup Files (2 minutes)

Check that files were downloaded:

```bash
ls -la ./backups/local/google-drive/
```

You should see directories for files, folders, and manifests.

### Troubleshooting

**"Redirect URI mismatch"**:
- Ensure OAuth client type is "Desktop app" not "Web app"
- Desktop apps don't need redirect URI configuration

**"Access blocked: Unverified app"**:
- Normal for personal projects
- Click "Advanced" → "Go to [app name] (unsafe)"
- This is safe because you created the app yourself

**"Token expired or invalid"**:
- Delete `~/.google-drive-tokens/token.json`
- Run workflow again to re-authenticate

**"Credentials file not found"**:
- Verify `GOOGLE_DRIVE_CREDENTIALS_PATH` is set correctly
- Check file exists: `cat ~/.google-drive-credentials/credentials.json`

---

## Security Best Practices

### All Workflows

1. **Environment Variables**:
   - Never commit `.env` to git (already in `.gitignore`)
   - Use strong, unique passwords
   - Rotate credentials periodically

2. **Prefect Blocks**:
   - Blocks are stored in Prefect's database
   - Not committed to git
   - Can be managed via Prefect UI at http://localhost:4200

3. **File Permissions**:
   - Backup files contain sensitive data
   - Ensure proper permissions: `chmod 700 ./backups`
   - Consider encrypting backups for shared systems

### Reddit-Specific

- Use "script" type OAuth (not "web app")
- Client secret is sensitive - treat like a password
- Consider 2FA on your Reddit account for extra security

### Amazon-Specific

- Store OTP secret securely (treat like a password)
- Backup OTP secret in case of device loss
- Monitor Amazon's "Login & security" page for unusual activity
- Sessions appear as normal web logins in Amazon's activity log

### Google Drive-Specific

- Workflow uses read-only scope (`drive.readonly`)
- OAuth tokens stored outside project: `~/.google-drive-tokens/`
- Consider publishing app if using for a team (removes "unverified" warning)
- Token refresh happens automatically - no re-authentication needed

---

## Script Templates

Create these helper scripts in `scripts/` directory:

### scripts/setup_reddit_block.py

```python
#!/usr/bin/env python3
"""Setup Reddit Prefect block from environment variables."""

from blocks.reddit_block import RedditBlock
import os
from dotenv import load_dotenv

def main():
    load_dotenv()

    required = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"]
    missing = [var for var in required if not os.getenv(var)]

    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("Add them to .env file and try again")
        return

    block = RedditBlock(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD")
    )

    block.save("reddit-credentials", overwrite=True)
    print("✓ Reddit credentials block created successfully")

if __name__ == "__main__":
    main()
```

### scripts/setup_amazon_block.py

```python
#!/usr/bin/env python3
"""Setup Amazon Prefect block from environment variables."""

from blocks.amazon_block import AmazonBlock
import os
from dotenv import load_dotenv

def main():
    load_dotenv()

    username = os.getenv("AMAZON_USERNAME")
    password = os.getenv("AMAZON_PASSWORD")
    otp_secret = os.getenv("AMAZON_OTP_SECRET")

    if not username or not password:
        print("❌ Missing required environment variables:")
        print("   - AMAZON_USERNAME")
        print("   - AMAZON_PASSWORD")
        print("Add them to .env file and try again")
        return

    block = AmazonBlock(
        username=username,
        password=password,
        otp_secret_key=otp_secret
    )

    block.save("amazon-credentials", overwrite=True)
    print("✓ Amazon credentials block created successfully")

    if not otp_secret:
        print("ℹ️  Note: No OTP secret provided (2FA disabled or not configured)")

if __name__ == "__main__":
    main()
```

### scripts/setup_google_drive_block.py

```python
#!/usr/bin/env python3
"""Setup Google Drive Prefect block from environment variables."""

from blocks.google_drive_block import GoogleDriveBlock
import os
from pathlib import Path
from dotenv import load_dotenv

def main():
    load_dotenv()

    credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH")

    if not credentials_path:
        print("❌ Missing environment variable: GOOGLE_DRIVE_CREDENTIALS_PATH")
        print("Add it to .env file or set in shell:")
        print('   export GOOGLE_DRIVE_CREDENTIALS_PATH="$HOME/.google-drive-credentials/credentials.json"')
        return

    if not Path(credentials_path).exists():
        print(f"❌ Credentials file not found: {credentials_path}")
        print("Download OAuth credentials from Google Cloud Console")
        return

    block = GoogleDriveBlock(credentials_path=credentials_path)
    block.save("google-drive-credentials", overwrite=True)
    print("✓ Google Drive credentials block created successfully")
    print("ℹ️  Run the workflow to complete OAuth authorization in browser")

if __name__ == "__main__":
    main()
```

### Make scripts executable

```bash
chmod +x scripts/setup_*.py
```

---

## Testing Your Setup

After setting up credentials for each workflow, test them:

```bash
# Test Reddit
python workflows/reddit.py

# Test Amazon (requires Python 3.12 or 3.11)
python workflows/amazon.py

# Test Google Drive (will open browser on first run)
python workflows/google_drive.py
```

**Success indicators**:
- No authentication errors
- Backup files created in `./backups/local/{platform}/`
- Manifest JSON files show statistics
- Workflow completes without errors

---

## Next Steps

After successful credential setup:

1. **Review backup files** to ensure data is captured correctly
2. **Set up scheduled deployments** using Prefect
3. **Configure remote backups** (when implemented)
4. **Monitor workflow execution** via Prefect UI
5. **Document any custom configurations** in workflow-specific docs

---

## Additional Resources

- **Workflow-Specific Setup Guides**:
  - Reddit: `docs/reddit/setup.md`
  - Amazon: `docs/amazon/SETUP.md`
  - Google Drive: `docs/google-drive/SETUP.md`

- **Block Implementations**:
  - `blocks/reddit_block.py`
  - `blocks/amazon_block.py`
  - `blocks/google_drive_block.py`

- **Workflow Source Code**:
  - `workflows/reddit.py`
  - `workflows/amazon.py`
  - `workflows/google_drive.py`

- **Prefect UI**: http://localhost:4200 (when server is running)
