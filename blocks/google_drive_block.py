import os

from dotenv import load_dotenv
from prefect.blocks.core import Block

load_dotenv()


class GoogleDriveBlock(Block):
    """
    Block for Google Drive API authentication.

    This block stores the path to OAuth2 credentials JSON file
    downloaded from Google Cloud Console.

    The credentials.json file should be obtained by:
    1. Creating a project in Google Cloud Console
    2. Enabling the Google Drive API
    3. Creating OAuth 2.0 credentials (Desktop app type)
    4. Downloading the credentials.json file
    """
    _block_type_name = "google-drive"
    _logo_url = "https://www.gstatic.com/images/branding/product/1x/drive_2020q4_48dp.png"
    _description = "Block for Google Drive API authentication."

    credentials_path: str


# Example: Save a block with credentials path from environment
# Uncomment and set environment variables to register:
# credentials_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH", "./credentials.json")
# block_name = "google-drive-credentials"
#
# block_id = GoogleDriveBlock(
#     credentials_path=credentials_path,
# ).save(
#     block_name,
#     overwrite=True,
# )
#
# print(f"Google Drive block saved. Name: {block_name}, ID: {block_id}")
