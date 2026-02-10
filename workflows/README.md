# Aqueduct Workflows

This directory contains backup workflows for various platforms. Each workflow is a Prefect flow that can be run directly or scheduled as a deployment.

## Workflow Status

| Workflow | Status | Description |
|----------|--------|-------------|
| [GitHub](#github) | Working | Backup repositories and commit history |
| [Twitter/X](#twitterx) | Working | Backup tweets, bookmarks, and likes with media |
| [YouTube](#youtube) | Working | Download YouTube videos (Twilio SMS trigger) |
| [Crunchyroll](#crunchyroll) | Working (requires auth) | Download anime from Crunchyroll |
| [Reddit](#reddit) | Working | Backup saved posts, comments, and upvoted content |
| [Google Drive](#google-drive) | Working | Download files and folders with Workspace exports |
| [Amazon](#amazon) | Working (Python 3.12/3.11) | Download order history |
| [Discord](#discord) | Working | Backup messages, attachments, and metadata |
| [Example](#example) | Template | Basic Prefect flow reference |
| `cannot-automate/google_photos.py` | Cannot automate | Google deprecated Library API scopes April 1, 2025 |
| `to-fix/instagram.py` | Broken | Needs repair |
| `to-fix/notion.py` | Broken | Needs repair |

---

## System Dependencies

These must be installed on the host system (or in Docker):

| Dependency | Required By | Install (macOS) | Install (Ubuntu) |
|------------|-------------|-----------------|------------------|
| ffmpeg | youtube, crunchyroll | `brew install ffmpeg` | `apt install ffmpeg` |
| git | github | Pre-installed | `apt install git` |
| mkvtoolnix | crunchyroll | `brew install mkvtoolnix` | `apt install mkvtoolnix` |
| Node.js 18+ | crunchyroll | `brew install node` | `apt install nodejs` |
| pnpm | crunchyroll | `npm install -g pnpm` | `npm install -g pnpm` |

### Crunchyroll: multi-downloader-nx

The Crunchyroll workflow requires [multi-downloader-nx](https://github.com/anidl/multi-downloader-nx). No npm package exists - build from source:

```bash
# Clone the repo
git clone https://github.com/anidl/multi-downloader-nx.git ~/tools/multi-downloader-nx
cd ~/tools/multi-downloader-nx

# Install dependencies (requires pnpm)
pnpm install

# Build CLI
pnpm run prebuild-cli

# Create wrapper script
cat > ~/tools/multi-downloader-nx/multi-downloader-nx << 'EOF'
#!/bin/bash
SCRIPT_DIR="$HOME/tools/multi-downloader-nx/lib"
cd "$SCRIPT_DIR"
exec node index.js "$@"
EOF
chmod +x ~/tools/multi-downloader-nx/multi-downloader-nx

# Add to PATH (create ~/bin and symlink)
mkdir -p ~/bin
ln -sf ~/tools/multi-downloader-nx/multi-downloader-nx ~/bin/multi-downloader-nx
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc  # or ~/.bashrc
source ~/.zshrc

# Verify installation
multi-downloader-nx --version
```

**Current installation:** `~/tools/multi-downloader-nx/` (v5.6.9)

**Note**: Crunchyroll uses DRM protection. Requires a **Crunchyroll Premium** subscription. May require additional decryption tools (`mp4decrypt` or `shaka-packager`) for some content.

---

## Docker Deployment

For running workflows in Docker containers with Prefect, see: https://docs.prefect.io/v3/how-to-guides/deployment_infra/docker

### Example Dockerfile

```dockerfile
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    mkvtoolnix \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for crunchyroll)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm

# Install multi-downloader-nx
WORKDIR /tools
RUN git clone https://github.com/anidl/multi-downloader-nx.git \
    && cd multi-downloader-nx \
    && pnpm install \
    && pnpm run prebuild-cli
ENV PATH="/tools/multi-downloader-nx/lib:${PATH}"

# Install Python dependencies
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy workflow code
COPY . .

# Default command
CMD ["prefect", "worker", "start", "--pool", "docker-pool"]
```

### Work Pool Setup

```bash
# Create a Docker work pool
prefect work-pool create --type docker aqueduct-docker-pool

# Start a worker
prefect worker start --pool aqueduct-docker-pool
```

### Deploying a Workflow

```python
from workflows.youtube import download_youtube_video
from prefect.docker import DockerImage

download_youtube_video.deploy(
    name="youtube-download",
    work_pool_name="aqueduct-docker-pool",
    image=DockerImage(
        name="aqueduct",
        tag="latest",
        dockerfile="Dockerfile"
    ),
    push=False  # Set True to push to registry
)
```

---

## GitHub

**File:** `github.py`

Backs up repositories and commit history using the GitHub GraphQL API.

### Setup

1. Create a GitHub personal access token with `repo` scope
2. Set `GITHUB_TOKEN` in `.env`
3. Register the Prefect block: `prefect block register -m prefect_github`

### Caveats / Notes

- Uses GraphQL API for efficient data fetching
- Supports `until_date` parameter for incremental backups
- Clones repositories locally in addition to fetching metadata

### Usage

```bash
python workflows/github.py
```

---

## Twitter/X

**File:** `twitter.py`

Downloads tweets, bookmarks, and likes with media files using the X API v2 (xdk SDK).

### Setup

1. Create a Twitter/X Developer account and app at https://developer.x.com
2. Generate OAuth 2.0 credentials with read permissions
3. Set the following in `.env`:
   ```
   TWITTER_CLIENT_ID=your_client_id
   TWITTER_CLIENT_SECRET=your_client_secret
   TWITTER_REDIRECT_URI=http://localhost:8080/callback
   ```
4. Register the Prefect block: `python blocks/twitter_block.py`

### Caveats / Notes

- Uses OAuth 2.0 PKCE flow for authentication
- First run opens browser for authorization
- Saves tokens at `~/.twitter-tokens/token.json` for subsequent runs
- Downloads all media (photos, videos) associated with tweets
- Preserves full tweet metadata in JSON format

### Usage

```bash
python workflows/twitter.py
```

---

## Reddit

**File:** `reddit.py`

Downloads saved posts, comments, and upvoted content using PRAW (Python Reddit API Wrapper).

### Setup

1. Create a Reddit app at https://www.reddit.com/prefs/apps
   - App type: "script"
   - Redirect URI: http://localhost:8080
2. Set the following in `.env`:
   ```
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USER_AGENT=aqueduct-backup/1.0
   REDDIT_USERNAME=your_username
   REDDIT_PASSWORD=your_password
   ```
3. Register the Prefect block: `python blocks/reddit_block.py`

### Caveats / Notes

- Downloads saved posts, saved comments, and upvoted posts
- Saves media files (images, videos) alongside metadata
- Uses date-segmented directories for organization
- Implements rate limiting to avoid Reddit API throttling

### Usage

```bash
python workflows/reddit.py
```

---

## Google Drive

**File:** `google_drive.py`

Downloads files and folders with Google Workspace exports using the Drive API.

### Setup

1. Create a Google Cloud project and enable the Drive API
2. Create OAuth2 credentials (Desktop app type)
3. Download credentials JSON and set `GOOGLE_DRIVE_CREDENTIALS_PATH` in `.env`
4. Register the Prefect block: `python blocks/google_drive_block.py`

### Caveats / Notes

- Exports Google Workspace files (Docs, Sheets, Slides) to standard formats
- First run opens browser for OAuth authorization
- Tokens cached at `~/.google-drive-tokens/token.json`
- Preserves folder structure
- Date-segmented backups for idempotency

### Usage

```bash
python workflows/google_drive.py
```

---

## Amazon

**File:** `amazon.py`

Downloads order history from Amazon.

### Setup

**Important:** Requires Python 3.12 or 3.11 due to dependency constraints (amazon-orders → amazoncaptcha → pillow<9.6.0 cannot build on Python 3.13).

1. Install with compatible Python version:
   ```bash
   uv venv --python 3.12
   source .venv/bin/activate
   uv pip install -e .
   ```
2. Set Amazon credentials in `.env`:
   ```
   AMAZON_EMAIL=your_email
   AMAZON_PASSWORD=your_password
   ```
3. Register the Prefect block: `python blocks/amazon_block.py`

### Caveats / Notes

- May require CAPTCHA solving on first run
- Downloads order details and metadata
- Preserves order history in structured JSON format

### Usage

```bash
python workflows/amazon.py
```

---

## Discord

**File:** `discord.py`

Backs up Discord messages, attachments, and metadata.

### Setup

1. Get your Discord user token (see instructions in `discord.py`)
2. Set `DISCORD_TOKEN` in `.env`
3. Register the Prefect block: `python blocks/discord_block.py`

### Caveats / Notes

- Backs up messages from specified channels
- Downloads all attachments (images, videos, files)
- Preserves message metadata and thread structure
- Rate-limited to respect Discord API limits

### Usage

```bash
python workflows/discord.py
```

---

## YouTube

**File:** `youtube.py`

Downloads YouTube videos using yt-dlp. Supports Twilio SMS webhook trigger.

### Setup

**System dependencies:**
```bash
brew install ffmpeg  # macOS
# or
apt install ffmpeg   # Ubuntu
```

**Twilio SMS Webhook (optional):**
1. Get a Twilio account and phone number
2. Run the webhook server:
   ```bash
   python workflows/youtube.py --serve
   ```
3. Expose locally with ngrok:
   ```bash
   ngrok http 5000
   ```
4. Configure Twilio webhook URL: `https://your-ngrok-url.ngrok.io/sms`
5. Text a YouTube URL to your Twilio number

### Usage

```bash
# Interactive download
python workflows/youtube.py

# Run Twilio webhook server
python workflows/youtube.py --serve

# In code
from workflows.youtube import download_youtube_video
download_youtube_video(url="https://youtube.com/watch?v=...")
```

### Caveats / Notes

- No authentication required (public videos only)
- Uses `download_archive.txt` for idempotency (won't re-download)
- Saves video + metadata JSON + thumbnail + subtitles
- Default quality: 1080p max

---

## Crunchyroll

**File:** `crunchyroll.py`

Downloads anime from Crunchyroll using multi-downloader-nx.

### Setup

1. Install system dependencies (see [System Dependencies](#system-dependencies))
2. Build multi-downloader-nx from source (see [above](#crunchyroll-multi-downloader-nx))
3. Have a Crunchyroll Premium subscription
4. **Authenticate with Crunchyroll:**
   ```bash
   multi-downloader-nx --service crunchy --auth
   ```
   This will prompt you to log in. Credentials are saved locally.

### Search for anime

```bash
multi-downloader-nx --service crunchy --search "solo leveling"
```

### Configuration

Edit `config/crunchyroll_series.json`:

```json
{
  "crunchyroll_config": {
    "quality": "1080",
    "audio_lang": "jaJP",
    "subtitle_lang": "enUS"
  },
  "series": [
    {
      "name": "Solo Leveling",
      "url": "https://www.crunchyroll.com/series/GDKHZEJ0K/solo-leveling",
      "episodes": "1-12",
      "enabled": true
    }
  ]
}
```

### Usage

```bash
# Run backup of all configured series
python workflows/crunchyroll.py

# Add a series interactively
python workflows/crunchyroll.py --add

# List configured series
python workflows/crunchyroll.py --list

# Download single series directly
python workflows/crunchyroll.py --download "Solo Leveling" "https://crunchyroll.com/series/..." "1-12"
```

### Caveats / Notes

- Crunchyroll uses DRM; may require additional decryption tools
- Episode ranges: `1-12` (range), `1-` (all from 1), `1,5,10` (specific)
- Output: MKV with Japanese audio and English subtitles by default

---

## Example

**File:** `example.py`

A template workflow showing the basic Prefect flow structure. Use this as a reference when creating new workflows.

```bash
python workflows/example.py
```

---

## Cannot Automate

### Google Photos

**File:** `cannot-automate/google_photos.py`

**Status:** Cannot be automated as of April 1, 2025

Google deprecated the Photos Library API scopes required for programmatic backup. The API now only supports limited read access for approved applications.

See `workflows/cannot-automate/README.md` for details.

---

## Backup Directory Structure

All backups are stored in `./backups/local/`:

```
backups/local/
├── github/
│   └── {username}/
│       └── repositories/
│           └── {date}/
├── twitter/
│   └── {username}/
│       └── {date}/
│           ├── tweets/
│           ├── bookmarks/
│           └── likes/
├── reddit/
│   └── {username}/
│       └── {date}/
│           ├── saved_posts/
│           ├── saved_comments/
│           └── upvoted/
├── google_drive/
│   └── {email}/
│       └── {date}/
├── amazon/
│   └── {email}/
│       └── orders/
│           └── {date}/
├── discord/
│   └── {username}/
│       └── {date}/
├── youtube/
│   ├── videos/
│   │   └── {uploader}/
│   ├── download_archive.txt
│   └── _records/
└── crunchyroll/
    └── {series_name}/
```

---

## Creating a New Workflow

**Before starting, research the platform's APIs:**
1. Ensure the APIs are not deprecated (e.g., Google Photos API was deprecated April 1, 2025)
2. Verify the workflow can be fully automated without manual intervention
3. If manual steps are required (e.g., CAPTCHA, manual auth), place in `cannot-automate/` directory

**Development process:**
1. Use the workflow-builder agent to create the initial workflow (see `.claude/agents/workflow-builder.md`)
2. Create a credentials block in `blocks/` that extends `prefect.blocks.core.Block` with `SecretStr` fields
3. Add corresponding environment variables to `.env.example`
4. Implement the workflow following these patterns:
   - Use `@task` decorator for granular operations (auth, API calls, downloads, processing)
   - Create a main `@flow` decorated function to orchestrate tasks
   - Follow backup structure: `./backups/local/platform/username/content_type/`
   - Save metadata as JSON for future querying
   - Use `cache_policy=NO_CACHE` to ensure fresh data
5. Use the idempotency-guardian agent to ensure the workflow is idempotent
6. Use the workflow-testing-agent to test the workflow end-to-end
7. Add documentation to this README with setup instructions, caveats, and usage examples
