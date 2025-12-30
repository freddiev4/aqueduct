import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import urllib.request
import urllib.parse

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

try:
    from notion_client import Client
except ImportError:
    raise ImportError(
        "notion-client is required. Install it with: uv pip install notion-client"
    )


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to be filesystem-safe."""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename or "untitled"


@task(cache_policy=NO_CACHE)
def get_all_pages(
    notion_token: str,
    local_backup_dir: Path = Path("./backups/local"),
) -> List[Dict[str, Any]]:
    """
    Get all pages accessible by the Notion integration.
    
    Args:
        notion_token: Notion integration token
        local_backup_dir: Base directory for backups
    
    Returns:
        List of page dictionaries with metadata
    """
    client = Client(auth=notion_token)
    
    all_pages = []
    start_cursor = None
    
    print("Fetching all pages from Notion...")
    
    while True:
        try:
            if start_cursor:
                response = client.search(
                    filter={"property": "object", "value": "page"},
                    start_cursor=start_cursor,
                )
            else:
                response = client.search(
                    filter={"property": "object", "value": "page"},
                )
            
            pages = response.get("results", [])
            all_pages.extend(pages)
            
            # Check if there are more pages
            has_more = response.get("has_more", False)
            if has_more:
                start_cursor = response.get("next_cursor")
            else:
                break
                
        except Exception as e:
            print(f"Error fetching pages: {e}")
            break
    
    print(f"Found {len(all_pages)} pages")
    return all_pages


@task(cache_policy=NO_CACHE)
def download_media_file(
    url: str,
    output_path: Path,
    notion_token: Optional[str] = None,
) -> Optional[Path]:
    """
    Download a media file (image, video, etc.) from a URL.
    
    Args:
        url: URL of the media file
        output_path: Path where to save the file
        notion_token: Notion token for authenticated requests (if needed)
    
    Returns:
        Path to downloaded file, or None if download failed
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create request with headers
        req = urllib.request.Request(url)
        if notion_token and "notion.so" in url:
            req.add_header("Authorization", f"Bearer {notion_token}")
        
        with urllib.request.urlopen(req) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())
        
        return output_path
    except Exception as e:
        print(f"Error downloading media from {url}: {e}")
        return None


def extract_media_urls(block: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extract media URLs from a Notion block.
    
    Returns:
        List of dicts with 'url' and 'type' keys
    """
    media_items = []
    block_type = block.get("type", "")
    
    if block_type == "image":
        image_data = block.get("image", {})
        if isinstance(image_data, dict):
            file_data = image_data.get("file") or image_data.get("external")
            if file_data and isinstance(file_data, dict):
                url = file_data.get("url", "")
                if url:
                    media_items.append({"url": url, "type": "image"})
    
    elif block_type == "video":
        video_data = block.get("video", {})
        if isinstance(video_data, dict):
            file_data = video_data.get("file") or video_data.get("external")
            if file_data and isinstance(file_data, dict):
                url = file_data.get("url", "")
                if url:
                    media_items.append({"url": url, "type": "video"})
    
    elif block_type == "file":
        file_data = block.get("file", {})
        if isinstance(file_data, dict):
            file_info = file_data.get("file") or file_data.get("external")
            if file_info and isinstance(file_info, dict):
                url = file_info.get("url", "")
                if url:
                    media_items.append({"url": url, "type": "file"})
    
    elif block_type == "pdf":
        pdf_data = block.get("pdf", {})
        if isinstance(pdf_data, dict):
            file_data = pdf_data.get("file") or pdf_data.get("external")
            if file_data and isinstance(file_data, dict):
                url = file_data.get("url", "")
                if url:
                    media_items.append({"url": url, "type": "pdf"})
    
    return media_items


def block_to_markdown(block: Dict[str, Any], notion_token: Optional[str] = None) -> str:
    """
    Convert a Notion block to Markdown format.
    
    Args:
        block: Notion block dictionary
        notion_token: Notion token for downloading media
    
    Returns:
        Markdown string representation of the block
    """
    block_type = block.get("type", "")
    block_id = block.get("id", "")
    
    # Get the content based on block type
    content = block.get(block_type, {})
    
    # Extract rich text
    def extract_rich_text(rich_text_array):
        """Extract text from rich text array."""
        if not rich_text_array:
            return ""
        text_parts = []
        for item in rich_text_array:
            if isinstance(item, dict):
                text = item.get("plain_text", "")
                annotations = item.get("annotations", {})
                
                # Apply formatting
                if annotations.get("bold"):
                    text = f"**{text}**"
                if annotations.get("italic"):
                    text = f"*{text}*"
                if annotations.get("strikethrough"):
                    text = f"~~{text}~~"
                if annotations.get("code"):
                    text = f"`{text}`"
                
                # Handle links
                link = item.get("href")
                if link:
                    text = f"[{text}]({link})"
                
                text_parts.append(text)
        return "".join(text_parts)
    
    markdown = ""
    
    if block_type == "paragraph":
        text = extract_rich_text(content.get("rich_text", []))
        markdown = f"{text}\n\n"
    
    elif block_type == "heading_1":
        text = extract_rich_text(content.get("rich_text", []))
        markdown = f"# {text}\n\n"
    
    elif block_type == "heading_2":
        text = extract_rich_text(content.get("rich_text", []))
        markdown = f"## {text}\n\n"
    
    elif block_type == "heading_3":
        text = extract_rich_text(content.get("rich_text", []))
        markdown = f"### {text}\n\n"
    
    elif block_type == "bulleted_list_item":
        text = extract_rich_text(content.get("rich_text", []))
        markdown = f"- {text}\n"
    
    elif block_type == "numbered_list_item":
        text = extract_rich_text(content.get("rich_text", []))
        markdown = f"1. {text}\n"
    
    elif block_type == "to_do":
        text = extract_rich_text(content.get("rich_text", []))
        checked = content.get("checked", False)
        checkbox = "[x]" if checked else "[ ]"
        markdown = f"{checkbox} {text}\n"
    
    elif block_type == "toggle":
        text = extract_rich_text(content.get("rich_text", []))
        markdown = f"<details><summary>{text}</summary>\n\n"
        # Note: Toggle content would be in child blocks
    
    elif block_type == "quote":
        text = extract_rich_text(content.get("rich_text", []))
        markdown = f"> {text}\n\n"
    
    elif block_type == "callout":
        text = extract_rich_text(content.get("rich_text", []))
        emoji = content.get("icon", {}).get("emoji", "") if isinstance(content.get("icon"), dict) else ""
        markdown = f"> {emoji} {text}\n\n"
    
    elif block_type == "code":
        text = extract_rich_text(content.get("rich_text", []))
        language = content.get("language", "")
        markdown = f"```{language}\n{text}\n```\n\n"
    
    elif block_type == "divider":
        markdown = "---\n\n"
    
    elif block_type in ["image", "video", "file", "pdf"]:
        media_items = extract_media_urls(block)
        for media in media_items:
            url = media["url"]
            media_type = media["type"]
            # Use block ID as filename hint
            filename = f"{block_id[:8]}.{media_type}"
            
            if media_type == "image":
                markdown = f"![Image]({url})\n\n"
            elif media_type == "video":
                markdown = f"![Video]({url})\n\n"
            else:
                markdown = f"[{media_type.upper()}]({url})\n\n"
    
    elif block_type == "bookmark":
        url = content.get("url", "")
        caption = extract_rich_text(content.get("caption", []))
        markdown = f"[Bookmark: {url}]({url})\n{caption}\n\n" if caption else f"[Bookmark]({url})\n\n"
    
    elif block_type == "equation":
        expression = content.get("expression", "")
        markdown = f"$${expression}$$\n\n"
    
    else:
        # Fallback for unknown block types
        text = extract_rich_text(content.get("rich_text", [])) if content.get("rich_text") else ""
        markdown = f"<!-- {block_type} -->\n{text}\n\n"
    
    return markdown


def fetch_all_child_blocks(
    client: Client,
    block_id: str,
    notion_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Recursively fetch all child blocks for a given block.
    
    Args:
        client: Notion API client
        block_id: ID of the parent block
        notion_token: Notion token (for consistency, not used here)
    
    Returns:
        List of all child blocks (flattened)
    """
    all_blocks = []
    start_cursor = None
    
    while True:
        try:
            if start_cursor:
                response = client.blocks.children.list(
                    block_id=block_id,
                    start_cursor=start_cursor,
                )
            else:
                response = client.blocks.children.list(block_id=block_id)
            
            blocks = response.get("results", [])
            
            # For each block, check if it has children and fetch them recursively
            for block in blocks:
                all_blocks.append(block)
                # Check if block has children
                has_children = block.get("has_children", False)
                if has_children:
                    child_blocks = fetch_all_child_blocks(
                        client=client,
                        block_id=block.get("id", ""),
                        notion_token=notion_token,
                    )
                    all_blocks.extend(child_blocks)
            
            has_more = response.get("has_more", False)
            if has_more:
                start_cursor = response.get("next_cursor")
            else:
                break
        except Exception as e:
            print(f"Error fetching child blocks for {block_id}: {e}")
            break
    
    return all_blocks


@task(cache_policy=NO_CACHE)
def backup_page(
    page: Dict[str, Any],
    notion_token: str,
    local_backup_dir: Path = Path("./backups/local"),
) -> Dict[str, Any]:
    """
    Backup a single Notion page with all its content and media.
    
    Args:
        page: Notion page dictionary
        notion_token: Notion integration token
        local_backup_dir: Base directory for backups
    
    Returns:
        Dictionary with backup statistics
    """
    client = Client(auth=notion_token)
    
    page_id = page.get("id", "")
    page_properties = page.get("properties", {})
    
    # Get page title
    title = "Untitled"
    if "title" in page_properties:
        title_prop = page_properties["title"]
        if title_prop.get("type") == "title":
            title_rich_text = title_prop.get("title", [])
            if title_rich_text:
                title = "".join([item.get("plain_text", "") for item in title_rich_text])
    
    # Sanitize title for filesystem
    safe_title = sanitize_filename(title)
    page_dir = local_backup_dir / "notion" / "pages" / f"{safe_title}_{page_id[:8]}"
    page_dir.mkdir(parents=True, exist_ok=True)
    
    # Create media directory
    media_dir = page_dir / "media"
    media_dir.mkdir(exist_ok=True)
    
    print(f"Backing up page: {title}")
    
    # Fetch all blocks recursively (including nested children)
    all_blocks = fetch_all_child_blocks(
        client=client,
        block_id=page_id,
        notion_token=notion_token,
    )
    
    media_files = []
    
    # Convert blocks to markdown and download media
    markdown_content = f"# {title}\n\n"
    markdown_content += f"*Page ID: {page_id}*\n"
    markdown_content += f"*Backed up: {datetime.now(timezone.utc).isoformat()}*\n\n"
    markdown_content += "---\n\n"
    
    # Track toggle state for proper closing
    toggle_stack = []
    
    for i, block in enumerate(all_blocks):
        block_type = block.get("type", "")
        
        # Close any open toggles if we're moving to a new top-level block
        # (This is a heuristic - Notion's block structure can be complex)
        if block_type not in ["bulleted_list_item", "numbered_list_item"] and toggle_stack:
            # Close all open toggles
            while toggle_stack:
                markdown_content += "</details>\n\n"
                toggle_stack.pop()
        
        # Extract media URLs
        media_items = extract_media_urls(block)
        
        # Download media files
        for media in media_items:
            url = media["url"]
            media_type = media["type"]
            block_id_short = block.get("id", "")[:8]
            
            # Determine file extension
            ext_map = {
                "image": ".jpg",
                "video": ".mp4",
                "file": "",
                "pdf": ".pdf",
            }
            ext = ext_map.get(media_type, "")
            
            # Try to get filename from URL
            parsed_url = urllib.parse.urlparse(url)
            filename_from_url = Path(parsed_url.path).name
            if filename_from_url and "." in filename_from_url:
                filename = sanitize_filename(filename_from_url)
            else:
                filename = f"{block_id_short}{ext}"
            
            media_path = media_dir / filename
            
            # Download the media file
            downloaded_path = download_media_file(url, media_path, notion_token)
            if downloaded_path:
                media_files.append({
                    "original_url": url,
                    "local_path": str(downloaded_path.relative_to(page_dir)),
                    "type": media_type,
                })
                # Update markdown to reference local file
                markdown_content += f"![{media_type}]({downloaded_path.relative_to(page_dir)})\n\n"
            else:
                # Fallback to URL if download fails
                markdown_content += f"![{media_type}]({url})\n\n"
        
        # Convert block to markdown (if not already handled as media)
        if not media_items:
            block_md = block_to_markdown(block, notion_token)
            
            # Handle toggle blocks specially
            if block_type == "toggle":
                toggle_stack.append(block.get("id", ""))
            elif block_type == "divider" and toggle_stack:
                # Close toggles before divider
                while toggle_stack:
                    markdown_content += "</details>\n\n"
                    toggle_stack.pop()
            
            markdown_content += block_md
    
    # Close any remaining open toggles
    while toggle_stack:
        markdown_content += "</details>\n\n"
        toggle_stack.pop()
    
    # Save markdown file
    markdown_file = page_dir / "content.md"
    with open(markdown_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    # Save page metadata
    metadata = {
        "page_id": page_id,
        "title": title,
        "created_time": page.get("created_time", ""),
        "last_edited_time": page.get("last_edited_time", ""),
        "url": page.get("url", ""),
        "properties": page_properties,
        "backup_date": datetime.now(timezone.utc).isoformat(),
        "block_count": len(all_blocks),
        "media_count": len(media_files),
        "media_files": media_files,
    }
    
    metadata_file = page_dir / "metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"  - Blocks: {len(all_blocks)}, Media: {len(media_files)}")
    
    return {
        "page_id": page_id,
        "title": title,
        "backup_path": str(page_dir),
        "block_count": len(all_blocks),
        "media_count": len(media_files),
    }


@flow()
def backup_notion(
    notion_token: str,
    local_backup_dir: Path = Path("./backups/local"),
    max_pages: Optional[int] = None,
):
    """
    Main flow to backup all Notion pages.
    
    Args:
        notion_token: Notion integration token (get from https://www.notion.so/my-integrations)
        local_backup_dir: Base directory for backups
        max_pages: Maximum number of pages to backup (None for all)
    """
    print("Starting Notion backup...")
    
    # Get all pages
    pages = get_all_pages(
        notion_token=notion_token,
        local_backup_dir=local_backup_dir,
    )
    
    if max_pages:
        pages = pages[:max_pages]
    
    print(f"Backing up {len(pages)} pages...")
    
    # Backup each page
    results = []
    for i, page in enumerate(pages, 1):
        try:
            result = backup_page(
                page=page,
                notion_token=notion_token,
                local_backup_dir=local_backup_dir,
            )
            results.append(result)
            print(f"Progress: {i}/{len(pages)}")
        except Exception as e:
            print(f"Error backing up page {page.get('id', 'unknown')}: {e}")
            continue
    
    # Save summary
    summary = {
        "backup_date": datetime.now(timezone.utc).isoformat(),
        "total_pages": len(pages),
        "pages_backed_up": len(results),
        "total_blocks": sum(r.get("block_count", 0) for r in results),
        "total_media": sum(r.get("media_count", 0) for r in results),
        "pages": results,
    }
    
    summary_file = local_backup_dir / "notion" / "backup_summary.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\nNotion backup completed!")
    print(f"  - Pages backed up: {len(results)}/{len(pages)}")
    print(f"  - Total blocks: {summary['total_blocks']}")
    print(f"  - Total media files: {summary['total_media']}")
    print(f"  - Summary saved to: {summary_file}")
    
    return summary


if __name__ == "__main__":
    # Example usage - you need to provide your Notion integration token
    # Get your token from: https://www.notion.so/my-integrations
    # Make sure to share your pages with the integration
    backup_notion(
        notion_token="your_notion_integration_token_here",  # Replace with your token
        max_pages=None,  # Set to a number to limit pages, or None for all
    )

