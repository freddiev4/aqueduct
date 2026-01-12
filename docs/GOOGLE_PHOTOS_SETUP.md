# Google Photos Workflow Setup

This guide explains how to set up OAuth2 credentials for the Google Photos backup workflow.

## Prerequisites

- Google account with photos in Google Photos
- Access to Google Cloud Console
- Python 3.10+ with aqueduct installed

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name your project (e.g., "aqueduct-google-photos")
4. Click "Create"

## Step 2: Enable Google Photos Library API

1. In the Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Photos Library API"
3. Click on it and click "Enable"

## Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" user type (unless you have a Google Workspace)
3. Click "Create"
4. Fill in the required fields:
   - App name: "Aqueduct Backup"
   - User support email: your email
   - Developer contact: your email
5. Click "Save and Continue"
6. On "Scopes" page, click "Add or Remove Scopes"
7. Add the scope: `https://www.googleapis.com/auth/photoslibrary.readonly`
8. Click "Update" then "Save and Continue"
9. On "Test users" page, add your Google account email
10. Click "Save and Continue"

## Step 4: Create OAuth2 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Select "Desktop app" as application type
4. Name it "Aqueduct Desktop Client"
5. Click "Create"
6. Click "Download JSON" to download the credentials file
7. Save the file as `credentials.json` in your aqueduct project root directory

## Step 5: Configure Environment Variable

1. Open your `.env` file (create it if it doesn't exist)
2. Add the following line:
   ```bash
   GOOGLE_PHOTOS_CREDENTIALS_PATH=/path/to/your/credentials.json
   ```
3. Update the path to match where you saved the credentials file

## Step 6: Register the Prefect Block

Run the block registration script:

```bash
source .venv/bin/activate
python blocks/google_photos_block.py
```

This will create a Prefect block named "google-photos-credentials" with your credentials path.

## Step 7: First-Time Authentication

The first time you run the workflow, it will open a browser window for OAuth2 authorization:

```bash
python workflows/google_photos.py
```

Steps:
1. A browser window will open automatically
2. Sign in with your Google account (must be the account you added as a test user)
3. Click "Continue" when you see the warning about the app not being verified
4. Grant permissions to read your Google Photos library
5. The workflow will save an authentication token for future use

## Troubleshooting

### "Access blocked: This app's request is invalid"

- Make sure you added your email as a test user in the OAuth consent screen
- Verify that the Photos Library API is enabled

### "The OAuth client was not found"

- Check that `credentials.json` path in `.env` is correct
- Verify the credentials file was downloaded correctly

### "insufficient authentication scopes"

- Make sure you added the `photoslibrary.readonly` scope in the OAuth consent screen
- Delete any cached tokens and re-authenticate

## Testing the Workflow

Test with a single photo download:

```bash
python workflows/google_photos.py
```

The default configuration downloads only 1 photo for testing. Check the output:

```
backups/local/google_photos/user/media/YYYY-MM-DD/
├── <photo-id>.jpg
├── <photo-id>.json
└── media_metadata.json
```

## Production Use

To download all photos, modify the `__main__` block in `workflows/google_photos.py`:

```python
if __name__ == "__main__":
    backup_google_photos(
        block_name="google-photos-credentials",
        max_items=None,  # Download all photos
    )
```

## Security Notes

- Never commit `credentials.json` to version control (it's in `.gitignore`)
- The OAuth token is stored in `~/.google-photos-library-api/` by default
- Credentials give read-only access to your Google Photos library
- You can revoke access at any time from [Google Account Settings](https://myaccount.google.com/permissions)
