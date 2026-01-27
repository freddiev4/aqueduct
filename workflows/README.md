# Aqueduct Workflows

This directory contains backup workflows for various platforms. Each workflow is a Prefect flow that can be run directly or scheduled as a deployment.

## Workflow Status

| Workflow | Status | Description |
|----------|--------|-------------|
| [Google Photos](#google-photos) | Working | Backup photos and videos from Google Photos |
| [GitHub](#github) | Working | Backup repositories and commit history |
| [YouTube](#youtube) | Working | Download YouTube videos (Twilio SMS trigger) |
| [Crunchyroll](#crunchyroll) | Working (requires auth) | Download anime from Crunchyroll |
| [Example](#example) | Template | Basic Prefect flow reference |
| `to-fix/instagram.py` | Broken | Needs repair |
| `to-fix/notion.py` | Broken | Needs repair |
| `to-fix/twitter.py` | Broken | Needs repair |

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

## Google Photos

**File:** `google_photos.py`

Backs up photos and videos from your Google Photos library with full metadata preservation.

### Setup

See [docs/GOOGLE_PHOTOS_SETUP.md](../docs/GOOGLE_PHOTOS_SETUP.md) for detailed setup instructions.

**Quick setup:**
1. Create a Google Cloud project and enable the Photos Library API
2. Create OAuth2 credentials (Desktop app type)
3. Download credentials JSON and set `GOOGLE_PHOTOS_CREDENTIALS_PATH` in `.env`
4. Register the Prefect block: `python blocks/google_photos_block.py`

### Caveats / Notes

- **OAuth Consent Screen:** Your app will be in "Testing" mode until verified by Google
  - Add test users at: `https://console.cloud.google.com/auth/audience?project=YOUR_PROJECT_ID`
  - Add scopes at: `https://console.cloud.google.com/auth/scopes?project=YOUR_PROJECT_ID`
- **403 access_denied:** The account trying to authorize isn't added as a test user
- **400 malformed request:** Usually means the Photos Library API isn't enabled or scopes aren't configured
- **First run:** Will open a browser for OAuth authorization; subsequent runs use cached token at `~/.google-photos-tokens/token.json`
- **Idempotency:** Snapshots are date-segmented; re-running on the same day skips already-downloaded items

### Usage

```bash
# Test with 1 photo
python workflows/google_photos.py

# In code (download all)
from workflows.google_photos import backup_google_photos
backup_google_photos(max_items=None)
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

## Backup Directory Structure

All backups are stored in `./backups/local/`:

```
backups/local/
├── github/
│   └── {username}/
│       └── repositories/
│           └── {date}/
├── google_photos/
│   └── {email}/
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

1. Create a new file: `workflows/platform_name.py`
2. Implement tasks with `@task` decorator for granular operations
3. Create a main flow with `@flow` decorator
4. Follow the backup directory structure: `./backups/local/platform/username/content_type/`
5. Save metadata as JSON for future querying
6. Add documentation to this README and create a setup doc in `docs/` if needed
