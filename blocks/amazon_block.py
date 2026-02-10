import os

from dotenv import load_dotenv
from pydantic import SecretStr
from prefect.blocks.core import Block

load_dotenv()


class AmazonBlock(Block):
    """
    Block for Amazon authentication.
    Stores credentials for accessing Amazon order history.
    """
    _block_type_name = "amazon"
    _logo_url = "https://www.amazon.com/favicon.ico"
    _description = "Block for Amazon authentication."

    username: SecretStr
    password: SecretStr
    otp_secret_key: SecretStr | None = None


# Example usage (uncomment and set environment variables to register):
# username = os.environ["AMAZON_USERNAME"]
# password = os.environ["AMAZON_PASSWORD"]
# otp_secret_key = os.environ.get("AMAZON_OTP_SECRET_KEY")  # Optional for 2FA
# block_name = "amazon-credentials"

# block_id = AmazonBlock(
#     username=username,
#     password=password,
#     otp_secret_key=otp_secret_key,
# ).save(
#     block_name,
#     overwrite=True,
# )

# print(f"Amazon block saved. Name: {block_name}, ID: {block_id}")
