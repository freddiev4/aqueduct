#!/usr/bin/env python3
"""Setup Reddit Prefect block from environment variables."""

from blocks.reddit_block import RedditBlock
import os
from dotenv import load_dotenv

def main():
    load_dotenv()

    required = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"]
    missing = [var for var in required if not os.getenv(var)]

    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("Add them to .env file and try again")
        return

    block = RedditBlock(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD")
    )

    block.save("reddit-credentials", overwrite=True)
    print("✓ Reddit credentials block created successfully")

if __name__ == "__main__":
    main()
