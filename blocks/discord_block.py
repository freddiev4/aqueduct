import os

from dotenv import load_dotenv
from pydantic import SecretStr
from prefect.blocks.core import Block

load_dotenv()


class DiscordBlock(Block):
    """
    Block for Discord bot authentication.
    Stores bot token for accessing Discord HTTP API.

    To create a Discord bot:
    1. Go to https://discord.com/developers/applications
    2. Click "New Application" and give it a name
    3. Go to the "Bot" section and click "Add Bot"
    4. Under "Privileged Gateway Intents", enable:
       - Message Content Intent (required to read message content)
       - Server Members Intent (optional, for member info)
    5. Copy the bot token (under "TOKEN" section)
    6. Go to OAuth2 > URL Generator
    7. Select scopes: "bot"
    8. Select permissions: "Read Messages/View Channels", "Read Message History"
    9. Use the generated URL to invite the bot to your server(s)

    Required bot permissions:
    - VIEW_CHANNEL
    - READ_MESSAGE_HISTORY
    - Message Content privileged intent enabled in developer portal
    """
    _block_type_name = "discord"
    _logo_url = "https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png"
    _description = "Block for Discord bot authentication."

    bot_token: SecretStr


# Example usage (uncomment and set environment variables to register):
# bot_token = os.environ["DISCORD_BOT_TOKEN"]
# block_name = "discord-credentials"

# block_id = DiscordBlock(
#     bot_token=bot_token,
# ).save(
#     block_name,
#     overwrite=True,
# )

# print(f"Discord block saved. Name: {block_name}, ID: {block_id}")
