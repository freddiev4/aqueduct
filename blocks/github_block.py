import os

from dotenv import load_dotenv
from pydantic import SecretStr
from prefect.blocks.core import Block

load_dotenv()


class GitHubBlock(Block):
    """
    Block for GitHub authentication.
    """
    _block_type_name = "github"
    _logo_url = "https://github.githubassets.com/favicons/favicon.png"
    _description = "Block for GitHub authentication."

    token: SecretStr


token = os.environ["GITHUB_TOKEN"]
block_name = "github-credentials"

block_id = GitHubBlock(
    token=token,
).save(
    block_name,
    overwrite=True,
)

print(f"GitHub block saved. Name: {block_name}, ID: {block_id}")
