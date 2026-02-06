# Google Drive Workflow Setup Guide

This guide walks you through setting up the Google Drive backup workflow from scratch.

## Prerequisites

- Python 3.10 or higher
- Google account with files in Google Drive
- Access to Google Cloud Console
- Terminal/command line access

## Step 1: Install Dependencies

All required dependencies are already in `pyproject.toml`:

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -e .
```

Required packages:
- `google-api-python-client` - Google Drive API client
- `google-auth` - Authentication library
- `google-auth-oauthlib` - OAuth 2.0 flow
- `google-auth-httplib2` - HTTP transport
- `prefect` - Workflow orchestration

## Step 2: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" at the top
3. Click "New Project"
4. Enter project name (e.g., "Aqueduct Backup")
5. Click "Create"
6. Wait for project creation to complete
7. Select your new project from the dropdown

## Step 3: Enable Google Drive API

1. In your project, go to "APIs & Services" > "Library"
   - Or visit: https://console.cloud.google.com/apis/library
2. Search for "Google Drive API"
3. Click on "Google Drive API" in the results
4. Click the "Enable" button
5. Wait for the API to be enabled (takes a few seconds)

## Step 4: Create OAuth 2.0 Credentials

### Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
   - Or visit: https://console.cloud.google.com/apis/credentials/consent
2. Choose "External" user type (unless you have a Google Workspace account)
3. Click "Create"
4. Fill in the required fields:
   - **App name**: "Aqueduct Drive Backup" (or your preferred name)
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
5. Click "Save and Continue"
6. On "Scopes" page, click "Add or Remove Scopes"
   - Search for "drive"
   - Select `https://www.googleapis.com/auth/drive.readonly`
   - Click "Update"
   - Click "Save and Continue"
7. On "Test users" page, click "Add Users"
   - Add your Google account email
   - Click "Add"
   - Click "Save and Continue"
8. Review and click "Back to Dashboard"

### Create OAuth Client ID

1. Go to "APIs & Services" > "Credentials"
   - Or visit: https://console.cloud.google.com/apis/credentials
2. Click "Create Credentials" at the top
3. Select "OAuth client ID"
4. For "Application type", select "Desktop app"
   - **Important**: Must be "Desktop app", not "Web application"
5. Enter a name: "Aqueduct Desktop Client"
6. Click "Create"
7. You'll see a dialog with your Client ID and Client Secret
8. Click "Download JSON"
9. Save the file as `credentials.json` in a secure location
   - **Recommended location**: `~/.google-drive-credentials/credentials.json`
   - **Never commit this file to git**

## Step 5: Set Environment Variable

Add the credentials path to your environment:

### Option A: Using .env file (recommended)

```bash
# In your aqueduct project directory
echo "GOOGLE_DRIVE_CREDENTIALS_PATH=$HOME/.google-drive-credentials/credentials.json" >> .env
```

### Option B: Export in shell

```bash
export GOOGLE_DRIVE_CREDENTIALS_PATH="$HOME/.google-drive-credentials/credentials.json"
```

Add to your `~/.bashrc` or `~/.zshrc` to make it permanent:

```bash
echo 'export GOOGLE_DRIVE_CREDENTIALS_PATH="$HOME/.google-drive-credentials/credentials.json"' >> ~/.bashrc
source ~/.bashrc
```

## Step 6: Register Prefect Block

### Option A: Edit and run the block file

1. Edit `blocks/google_drive_block.py`
2. Uncomment the example code at the bottom:

```python
# Example: Save a block with credentials path from environment
credentials_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH", "./credentials.json")
block_name = "google-drive-credentials"

block_id = GoogleDriveBlock(
    credentials_path=credentials_path,
).save(
    block_name,
    overwrite=True,
)

print(f"Google Drive block saved. Name: {block_name}, ID: {block_id}")
```

3. Run the file:

```bash
python blocks/google_drive_block.py
```

### Option B: Use Python REPL

```python
from blocks.google_drive_block import GoogleDriveBlock
import os

credentials_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH")
block_name = "google-drive-credentials"

block_id = GoogleDriveBlock(
    credentials_path=credentials_path,
).save(
    block_name,
    overwrite=True,
)

print(f"Google Drive block saved. Name: {block_name}, ID: {block_id}")
```

## Step 7: First Run - OAuth Authentication

Run the workflow for the first time:

```bash
python workflows/google_drive.py
```

What will happen:

1. The workflow will detect no token exists
2. A browser window will open automatically
3. You'll be asked to sign in to your Google account
4. Google will show a consent screen asking for permission to:
   - "See and download all your Google Drive files"
5. Click "Continue" or "Allow"
6. You'll see "Authentication successful!" in the browser
7. Close the browser window
8. The workflow will save a token to `~/.google-drive-tokens/token.json`
9. The backup will proceed

**Note**: The token will be automatically refreshed when it expires. You only need to authenticate once.

## Step 8: Verify Setup

Check that the backup completed successfully:

```bash
# Check the backup directory
ls -la ./backups/local/google-drive/

# You should see:
# - A directory with your email address
# - Inside: files/, folders/, manifests/ directories
# - A manifest file with backup statistics
```

## Troubleshooting

### "No module named 'google.auth'"

Solution:
```bash
source .venv/bin/activate
uv pip install -e .
```

### "FileNotFoundError: credentials.json"

Solution:
- Verify the credentials file exists at the path specified
- Check the environment variable is set correctly:
  ```bash
  echo $GOOGLE_DRIVE_CREDENTIALS_PATH
  ```
- Ensure the path is absolute, not relative

### "redirect_uri_mismatch" error during OAuth

Solution:
- You created a "Web application" instead of "Desktop app"
- Delete the OAuth client in Google Cloud Console
- Create a new one with "Desktop app" type
- Download the new credentials.json

### Browser doesn't open during OAuth

Solution:
- Copy the URL from the terminal output
- Paste it into your browser manually
- Complete the authorization
- The workflow will continue

### "Access blocked: This app's request is invalid"

Solution:
- You didn't configure the OAuth consent screen
- Go back to Step 4 and complete the consent screen setup
- Make sure you added your email as a test user

### "insufficient authentication scopes"

Solution:
- Delete the token file: `rm ~/.google-drive-tokens/token.json`
- Run the workflow again to re-authenticate
- This will request the correct scopes

### "The user has not granted the app" error

Solution:
- You need to add yourself as a test user
- Go to "OAuth consent screen" > "Test users"
- Click "Add Users" and add your email address

## Security Best Practices

1. **Never commit credentials.json to git**
   - Add to `.gitignore`:
     ```
     credentials.json
     .google-drive-tokens/
     ```

2. **Keep token.json secure**
   - Contains access and refresh tokens
   - Treat like a password
   - Located at: `~/.google-drive-tokens/token.json`

3. **Use read-only scope**
   - Workflow uses `drive.readonly` scope
   - Cannot modify or delete files
   - Safe to use on production data

4. **Revoke access when done**
   - Go to: https://myaccount.google.com/permissions
   - Find "Aqueduct Drive Backup"
   - Click "Remove Access" if you want to revoke

## Next Steps

Once setup is complete:

1. **Test with limited files**:
   ```bash
   # Edit workflows/google_drive.py __main__ block
   # Set max_files=10
   python workflows/google_drive.py
   ```

2. **Run full backup**:
   ```bash
   # Remove max_files limit
   python workflows/google_drive.py
   ```

3. **Schedule regular backups**:
   - See main documentation for scheduling with Prefect
   - Set up incremental backups with `modified_after` parameter

4. **Monitor backups**:
   - Check manifest files for statistics
   - Review failed_count for errors
   - Monitor disk space usage

## Additional Resources

- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/reference)
- [OAuth 2.0 Setup](https://developers.google.com/identity/protocols/oauth2)
- [Prefect Documentation](https://docs.prefect.io/)
- [Main Workflow Documentation](./docs.md)
