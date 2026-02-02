"""
Gmail Credentials Block for msgvault OAuth authentication.

This block stores OAuth credentials for Gmail API access via msgvault.
msgvault handles OAuth flow internally, so this block primarily stores
the email address and optional configuration.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from prefect.blocks.core import Block

load_dotenv()


class GmailCredentialsBlock(Block):
    """
    Block for Gmail authentication with msgvault.

    msgvault uses OAuth and stores credentials in its own config directory
    (~/.msgvault/), so this block primarily stores the email address and
    any workflow-specific configuration.
    """

    _block_type_name = "gmail-credentials"
    _logo_url = "https://upload.wikimedia.org/wikipedia/commons/7/7e/Gmail_icon_%282020%29.svg"
    _description = "Block for Gmail OAuth authentication via msgvault."

    email: str = Field(
        ...,
        description="Gmail email address to backup",
        example="user@gmail.com"
    )

    msgvault_config_dir: Optional[Path] = Field(
        default=None,
        description="Custom msgvault config directory (defaults to ~/.msgvault)"
    )

    def get_config_dir(self) -> Path:
        """Get the msgvault config directory."""
        if self.msgvault_config_dir:
            return Path(self.msgvault_config_dir)
        return Path.home() / ".msgvault"

    def get_db_path(self, backup_dir: Path) -> Path:
        """
        Get the path to the msgvault database for this account.

        Args:
            backup_dir: Base backup directory for the account

        Returns:
            Path to the msgvault.db file
        """
        return backup_dir / "msgvault.db"


# Example registration (commented out - run manually or via script)
# To register a block, uncomment and run:
#
# if __name__ == "__main__":
#     email = os.environ.get("GMAIL_ADDRESS", "user@gmail.com")
#     block_name = f"gmail-{email.split('@')[0]}"
#
#     block_id = GmailCredentialsBlock(
#         email=email,
#     ).save(
#         block_name,
#         overwrite=True,
#     )
#
#     print(f"Gmail credentials block saved. Name: {block_name}, ID: {block_id}")
