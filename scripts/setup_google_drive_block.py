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
