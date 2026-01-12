"""
Script to save Instagram session cookies for use with instaloader.

Instructions:
1. Log into Instagram in Chrome
2. Open DevTools (F12) → Application tab → Cookies → https://www.instagram.com
3. Copy the cookie values below and replace the placeholder strings
4. Run this script: python scripts/save_instagram_cookies.py
"""

import pickle
import sys
from pathlib import Path

# Add parent directory to path to import blocks
sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.instagram_block import InstagramBlock

# ============================================================================
# FILL IN YOUR COOKIE VALUES BELOW (replace the "YOUR_..." placeholders)
# ============================================================================

COOKIES = {
    "sessionid": "YOUR_SESSIONID_HERE",
    "csrftoken": "YOUR_CSRFTOKEN_HERE",
    "ds_user_id": "YOUR_DS_USER_ID_HERE",
    "mid": "YOUR_MID_HERE",
    "ig_did": "YOUR_IG_DID_HERE",
    "rur": "YOUR_RUR_HERE",  # Optional but recommended
}

# ============================================================================


def save_instagram_session(username: str, cookies: dict, session_dir: Path = None):
    """
    Save Instagram cookies in instaloader session format.

    Args:
        username: Instagram username
        cookies: Dictionary of cookie name-value pairs
        session_dir: Directory to save session files (defaults to ~/.config/instaloader)
    """
    if session_dir is None:
        session_dir = Path.home() / ".config" / "instaloader"

    session_dir.mkdir(parents=True, exist_ok=True)

    # Save session file in instaloader format (pickle)
    session_file = session_dir / f"session-{username}"

    print(f"Saving session for {username} to {session_file}...")

    with open(session_file, 'wb') as f:
        pickle.dump(cookies, f)

    print(f"✓ Session saved successfully!")
    print(f"  Location: {session_file}")
    print(f"\nYou can now run the Instagram workflow without password authentication.")

    return session_file


if __name__ == "__main__":
    # Check if cookies have been filled in
    if "YOUR_SESSIONID_HERE" in COOKIES["sessionid"]:
        print("ERROR: Please fill in the cookie values first!")
        print("\nInstructions:")
        print("1. Log into Instagram in Chrome")
        print("2. Open DevTools (F12 or Right-click → Inspect)")
        print("3. Go to: Application tab → Cookies → https://www.instagram.com")
        print("4. Copy the values for: sessionid, csrftoken, ds_user_id, mid, ig_did, rur")
        print("5. Replace the 'YOUR_...' placeholders in this script")
        print("6. Run this script again")
        sys.exit(1)

    # Load Instagram credentials to get username
    print("Loading Instagram credentials from Prefect block...")
    block_name = "instagram-credentials"

    try:
        instagram_creds = InstagramBlock.load(block_name)
        username = instagram_creds.username
    except Exception as e:
        print(f"Error loading Instagram credentials block '{block_name}': {e}")
        print("Using default username, or you can specify it directly in this script.")
        username = input("Enter your Instagram username: ").strip()

    # Save the session
    try:
        save_instagram_session(username, COOKIES)
    except Exception as e:
        print(f"Error saving session: {e}")
        sys.exit(1)
