import os

from dotenv import load_dotenv
from pydantic import SecretStr
from prefect.blocks.core import Block

load_dotenv()


class RedditBlock(Block):
    """
    Block for Reddit authentication using PRAW.
    Stores OAuth2 credentials for accessing Reddit API.

    To create a Reddit app:
    1. Go to https://www.reddit.com/prefs/apps
    2. Click "create app" or "create another app"
    3. Choose "script" as the app type
    4. Set redirect uri to http://localhost:8080
    5. Copy the client_id (under app name) and client_secret
    """
    _block_type_name = "reddit"
    _logo_url = "https://www.redditstatic.com/desktop2x/img/favicon/favicon-32x32.png"
    _description = "Block for Reddit API authentication using PRAW."

    client_id: SecretStr
    client_secret: SecretStr
    username: SecretStr
    password: SecretStr
    user_agent: str = "aqueduct:backup:v1.0.0 (by /u/USERNAME)"


# Example usage (uncomment and set environment variables to register):
# client_id = os.environ["REDDIT_CLIENT_ID"]
# client_secret = os.environ["REDDIT_CLIENT_SECRET"]
# username = os.environ["REDDIT_USERNAME"]
# password = os.environ["REDDIT_PASSWORD"]
# user_agent = "aqueduct:backup:v1.0.0 (by /u/YOUR_USERNAME)"
# block_name = "reddit-credentials"

# block_id = RedditBlock(
#     client_id=client_id,
#     client_secret=client_secret,
#     username=username,
#     password=password,
#     user_agent=user_agent,
# ).save(
#     block_name,
#     overwrite=True,
# )

# print(f"Reddit block saved. Name: {block_name}, ID: {block_id}")
