import os

from dotenv import load_dotenv
from prefect.blocks.core import Block

load_dotenv()

class InstagramBlock(Block):
    """
    Block for Instagram authentication.
    """
    _block_type_name = "instagram"
    _logo_url = "https://www.instagram.com/favicon.ico"
    _description = "Block for Instagram authentication."

    username: str
    password: str


username = os.environ["INSTAGRAM_USERNAME"]
password = os.environ["INSTAGRAM_PASSWORD"]
block_name = "instagram-credentials"

block_id = InstagramBlock(
    username=username, 
    password=password,
).save(
    block_name,
    overwrite=True,
)

print(f"Instagram block saved. Name: {block_name}, ID: {block_id}")