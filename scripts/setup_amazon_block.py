#!/usr/bin/env python3
"""Setup Amazon Prefect block from environment variables."""

from blocks.amazon_block import AmazonBlock
import os
from dotenv import load_dotenv

def main():
    load_dotenv()

    username = os.getenv("AMAZON_USERNAME")
    password = os.getenv("AMAZON_PASSWORD")
    otp_secret = os.getenv("AMAZON_OTP_SECRET")

    if not username or not password:
        print("❌ Missing required environment variables:")
        print("   - AMAZON_USERNAME")
        print("   - AMAZON_PASSWORD")
        print("Add them to .env file and try again")
        return

    block = AmazonBlock(
        username=username,
        password=password,
        otp_secret_key=otp_secret
    )

    block.save("amazon-credentials", overwrite=True)
    print("✓ Amazon credentials block created successfully")

    if not otp_secret:
        print("ℹ️  Note: No OTP secret provided (2FA disabled or not configured)")

if __name__ == "__main__":
    main()
