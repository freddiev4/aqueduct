#!/usr/bin/env python3
"""
Setup script for Gmail backup workflow.

Registers a GmailCredentialsBlock for use with the Gmail backup workflow.

Usage:
    python scripts/setup_gmail.py
    python scripts/setup_gmail.py --email your@gmail.com --block-name custom-block
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.gmail_block import GmailCredentialsBlock


def setup_gmail_credentials(email: str, block_name: str = None) -> str:
    """
    Register a GmailCredentialsBlock.

    Args:
        email: Gmail address to backup
        block_name: Optional custom block name (defaults to gmail-{username})

    Returns:
        The block name that was registered
    """
    if block_name is None:
        # Generate block name from email
        username = email.split("@")[0]
        block_name = f"gmail-{username}"

    print(f"Registering GmailCredentialsBlock...")
    print(f"  Email: {email}")
    print(f"  Block name: {block_name}")

    try:
        block = GmailCredentialsBlock(email=email)
        block_id = block.save(block_name, overwrite=True)

        print(f"\n✓ Successfully registered Gmail credentials block")
        print(f"  Block name: {block_name}")
        print(f"  Block ID: {block_id}")
        print(f"\nYou can now run the Gmail backup workflow:")
        print(f"  python workflows/gmail.py --credentials {block_name}")

        return block_name

    except Exception as e:
        print(f"\n✗ Failed to register block: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Setup Gmail backup credentials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive setup
  python scripts/setup_gmail.py

  # Non-interactive setup
  python scripts/setup_gmail.py --email user@gmail.com

  # Custom block name
  python scripts/setup_gmail.py --email user@gmail.com --block-name my-gmail
        """
    )

    parser.add_argument(
        "--email",
        help="Gmail address to backup"
    )

    parser.add_argument(
        "--block-name",
        help="Custom Prefect block name (default: gmail-{username})"
    )

    args = parser.parse_args()

    # Interactive mode if email not provided
    if not args.email:
        print("Gmail Backup Setup")
        print("=" * 50)
        print("\nThis will register a GmailCredentialsBlock for use with")
        print("the Gmail backup workflow.\n")

        email = input("Enter Gmail address to backup: ").strip()

        if not email:
            print("Error: Email address is required")
            sys.exit(1)

        if "@" not in email:
            print("Error: Invalid email address")
            sys.exit(1)
    else:
        email = args.email

    # Setup credentials
    block_name = setup_gmail_credentials(email, args.block_name)

    print("\n" + "=" * 50)
    print("Next steps:")
    print("=" * 50)
    print("\n1. Install msgvault (if not already installed):")
    print("   curl -fsSL https://msgvault.io/install.sh | bash")
    print("\n2. Setup Gmail OAuth credentials:")
    print("   Follow: https://msgvault.io/guides/oauth-setup/")
    print("\n3. Run your first backup (headless mode for servers/automation):")
    print(f"   python workflows/gmail.py --credentials {block_name} --max-messages 10 --headless")
    print("\n   Or for local development (opens browser):")
    print(f"   python workflows/gmail.py --credentials {block_name} --max-messages 10")
    print("\n4. After successful test, run full backup:")
    print(f"   python workflows/gmail.py --credentials {block_name} --headless")
    print("\n5. Schedule incremental backups:")
    print(f"   python workflows/gmail.py --credentials {block_name} --incremental --headless")


if __name__ == "__main__":
    main()
