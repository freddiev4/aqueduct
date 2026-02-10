import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import SecretStr
from prefect.blocks.core import Block

load_dotenv()


class TwitterBlock(Block):
    """
    Block for X/Twitter API authentication.

    Supports two auth methods:
    - OAuth 1.0a (api_key + access_token): Required for user-context
      operations like bookmarks and likes.
    - Bearer token: Sufficient for public read-only operations like
      fetching a user's timeline.

    To create credentials:
    1. Go to https://developer.x.com/
    2. Create a project and app
    3. Generate API Key, API Secret, Bearer Token
    4. Generate Access Token and Access Token Secret (with read permissions)
    """
    _block_type_name = "twitter"
    _logo_url = "https://abs.twimg.com/favicons/twitter.3.ico"
    _description = "Block for X/Twitter API authentication."

    bearer_token: Optional[SecretStr] = None
    api_key: Optional[SecretStr] = None
    api_secret: Optional[SecretStr] = None
    access_token: Optional[SecretStr] = None
    access_token_secret: Optional[SecretStr] = None


# Example usage (uncomment and set environment variables to register):
# bearer_token = os.environ.get("X_BEARER_TOKEN")
# api_key = os.environ.get("X_API_KEY")
# api_secret = os.environ.get("X_API_SECRET")
# access_token = os.environ.get("X_ACCESS_TOKEN")
# access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")
# block_name = "twitter-credentials"

# block_id = TwitterBlock(
#     bearer_token=bearer_token,
#     api_key=api_key,
#     api_secret=api_secret,
#     access_token=access_token,
#     access_token_secret=access_token_secret,
# ).save(
#     block_name,
#     overwrite=True,
# )

# print(f"Twitter block saved. Name: {block_name}, ID: {block_id}")
