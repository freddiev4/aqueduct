import os

from dotenv import load_dotenv
from prefect.blocks.core import Block

load_dotenv()


class GooglePhotosBlock(Block):
    """
    Block for Google Photos API authentication.

    This block stores the path to OAuth2 credentials JSON file
    downloaded from Google Cloud Console.
    """
    _block_type_name = "google-photos"
    _logo_url = "https://www.gstatic.com/images/branding/product/1x/photos_48dp.png"
    _description = "Block for Google Photos API authentication."

    credentials_path: str


# Example: Save a block with credentials path from environment
credentials_path = os.environ.get("GOOGLE_PHOTOS_CREDENTIALS_PATH", "./credentials.json")
block_name = "google-photos-credentials"

block_id = GooglePhotosBlock(
    credentials_path=credentials_path,
).save(
    block_name,
    overwrite=True,
)

print(f"Google Photos block saved. Name: {block_name}, ID: {block_id}")
