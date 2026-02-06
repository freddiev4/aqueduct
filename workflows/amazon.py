"""
Amazon Orders Backup Workflow

Downloads Amazon order history with metadata. Supports:
- Full order history with optional year filtering
- Session-based authentication via amazon-orders library
- Idempotent backups using snapshot dates
- Metadata preservation for each order

Requirements:
- amazon-orders library (pip install amazon-orders)
- Valid Amazon credentials (US .com site only)

Note: This uses web scraping (no official API) so it may break if Amazon changes their site.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.logging import get_run_logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.amazon_block import AmazonBlock

try:
    from amazon_orders import AmazonSession, AmazonOrders
except ImportError:
    AmazonSession = None
    AmazonOrders = None


BACKUP_DIR = Path("./backups/local/amazon")


@task(cache_policy=NO_CACHE)
def create_amazon_session(
    amazon_credentials: AmazonBlock,
) -> "AmazonSession":
    """
    Create and authenticate an Amazon session.

    Args:
        amazon_credentials: Amazon credentials block

    Returns:
        Authenticated AmazonSession instance
    """
    logger = get_run_logger()

    if AmazonSession is None:
        raise ImportError(
            "amazon-orders library is not installed. "
            "Run: pip install amazon-orders"
        )

    username = amazon_credentials.username.get_secret_value()
    password = amazon_credentials.password.get_secret_value()

    # Optional OTP secret for 2FA
    otp_secret = None
    if amazon_credentials.otp_secret_key:
        otp_secret = amazon_credentials.otp_secret_key.get_secret_value()

    logger.info(f"Creating Amazon session for user: {username[:3]}***")

    try:
        session = AmazonSession(
            username=username,
            password=password,
            otp_secret_key=otp_secret,
        )

        logger.info("Logging in to Amazon...")
        session.login()

        logger.info("Successfully authenticated with Amazon")
        return session

    except Exception as e:
        logger.error(f"Failed to authenticate with Amazon: {e}")
        raise


@task(cache_policy=NO_CACHE)
def fetch_order_history(
    amazon_session: "AmazonSession",
    year: Optional[int] = None,
    full_details: bool = True,
) -> list[dict]:
    """
    Fetch order history from Amazon.

    Args:
        amazon_session: Authenticated Amazon session
        year: Optional year to filter orders (e.g., 2023, 2024)
        full_details: Whether to fetch full order details (slower but more complete)

    Returns:
        List of order dictionaries
    """
    logger = get_run_logger()

    if AmazonOrders is None:
        raise ImportError(
            "amazon-orders library is not installed. "
            "Run: pip install amazon-orders"
        )

    amazon_orders = AmazonOrders(amazon_session)

    if year:
        logger.info(f"Fetching orders for year {year} (full_details={full_details})...")
    else:
        logger.info(f"Fetching all orders (full_details={full_details})...")

    try:
        # Fetch orders with optional year filter
        if year:
            orders = amazon_orders.get_order_history(
                year=year,
                full_details=full_details,
            )
        else:
            orders = amazon_orders.get_order_history(
                full_details=full_details,
            )

        # Convert Order objects to dictionaries
        orders_data = []
        for order in orders:
            # Extract available attributes
            order_dict = {
                "order_number": getattr(order, "order_number", None),
                "grand_total": getattr(order, "grand_total", None),
                "order_placed_date": getattr(order, "order_placed_date", None),
                "shipment_status": getattr(order, "shipment_status", None),
                "recipient": getattr(order, "recipient", None),
                "items": [],
            }

            # Extract items if available
            if hasattr(order, "items"):
                for item in order.items:
                    item_dict = {
                        "title": getattr(item, "title", None),
                        "link": getattr(item, "link", None),
                        "price": getattr(item, "price", None),
                        "quantity": getattr(item, "quantity", None),
                        "item_number": getattr(item, "item_number", None),
                        "return_eligible": getattr(item, "return_eligible", None),
                    }
                    order_dict["items"].append(item_dict)

            # Add additional fields if full_details was used
            if full_details:
                order_dict.update({
                    "order_details_link": getattr(order, "order_details_link", None),
                    "payment_method": getattr(order, "payment_method", None),
                    "payment_method_last_4": getattr(order, "payment_method_last_4", None),
                    "subtotal": getattr(order, "subtotal", None),
                    "shipping_cost": getattr(order, "shipping_cost", None),
                    "total_before_tax": getattr(order, "total_before_tax", None),
                    "estimated_tax": getattr(order, "estimated_tax", None),
                    "refund_total": getattr(order, "refund_total", None),
                    "refund_completed_date": getattr(order, "refund_completed_date", None),
                })

            orders_data.append(order_dict)

        # Sort orders deterministically for idempotency
        # Sort by order_placed_date (descending), then order_number for stability
        orders_data.sort(
            key=lambda x: (
                x.get("order_placed_date") or "",
                x.get("order_number") or ""
            ),
            reverse=True
        )

        logger.info(f"Successfully fetched {len(orders_data)} orders")
        return orders_data

    except Exception as e:
        logger.error(f"Failed to fetch order history: {e}")
        raise


@task(cache_policy=NO_CACHE)
def save_orders_to_disk(
    orders: list[dict],
    username: str,
    snapshot_date: datetime,
    year: Optional[int] = None,
    output_dir: Path = BACKUP_DIR,
) -> dict:
    """
    Save orders to disk with metadata.

    Args:
        orders: List of order dictionaries
        username: Amazon account username (for directory structure)
        snapshot_date: Date for this backup snapshot
        year: Optional year filter used
        output_dir: Base backup directory

    Returns:
        Dictionary with save statistics
    """
    logger = get_run_logger()

    # Ensure snapshot_date is UTC-aware
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    # Create directory structure: amazon/{username}/orders/{snapshot_date}/
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    orders_dir = output_dir / username / "orders" / snapshot_str
    orders_dir.mkdir(parents=True, exist_ok=True)

    # Check if orders file already exists (idempotency)
    orders_file = orders_dir / "orders.json"
    if orders_file.exists():
        logger.info(f"Orders file already exists at {orders_file}, skipping save...")
        with open(orders_file, "r") as f:
            existing_data = json.load(f)
        return {
            "orders_saved": len(existing_data.get("orders", [])),
            "orders_file": str(orders_file),
            "already_existed": True,
        }

    # Save all orders to a single JSON file
    orders_data = {
        "snapshot_date": snapshot_date.isoformat(),
        "snapshot_date_str": snapshot_str,
        "backup_timestamp": snapshot_date.isoformat(),
        "username": username,
        "year_filter": year,
        "order_count": len(orders),
        "orders": orders,
    }

    with open(orders_file, "w") as f:
        json.dump(orders_data, f, indent=2, sort_keys=True, default=str)

    logger.info(f"Saved {len(orders)} orders to {orders_file}")

    # Create per-order files for easier searching
    for order in orders:
        order_number = order.get("order_number")
        if order_number:
            order_file = orders_dir / f"order_{order_number}.json"
            with open(order_file, "w") as f:
                json.dump(order, f, indent=2, sort_keys=True, default=str)

    logger.info(f"Created {len(orders)} individual order files")

    return {
        "orders_saved": len(orders),
        "orders_file": str(orders_file),
        "individual_files": len(orders),
        "already_existed": False,
    }


@task()
def check_snapshot_exists(
    username: str,
    snapshot_date: datetime,
    output_dir: Path = BACKUP_DIR,
) -> bool:
    """
    Check if a snapshot already exists for the given date.
    Returns True if the snapshot directory and orders.json exist.
    """
    logger = get_run_logger()
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    snapshot_dir = output_dir / username / "orders" / snapshot_str
    orders_file = snapshot_dir / "orders.json"

    if snapshot_dir.exists() and orders_file.exists():
        logger.info(f"Snapshot for {snapshot_str} already exists at {snapshot_dir}")
        return True
    return False


@task()
def save_backup_manifest(
    username: str,
    snapshot_date: datetime,
    save_result: dict,
    year: Optional[int],
    workflow_start: float,
    output_dir: Path = BACKUP_DIR,
) -> Path:
    """
    Save a manifest file with backup metadata.

    Args:
        username: Amazon account username
        snapshot_date: Date for this backup snapshot
        save_result: Result from save_orders_to_disk
        year: Optional year filter used
        workflow_start: Workflow start timestamp
        output_dir: Base backup directory

    Returns:
        Path to manifest file
    """
    logger = get_run_logger()

    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    manifest_path = output_dir / username / "orders" / f"backup_manifest_{snapshot_str}.json"

    manifest = {
        "snapshot_date": snapshot_date.isoformat(),
        "snapshot_date_str": snapshot_str,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_version": "1.0.0",
        "python_version": sys.version,
        "username": username,
        "year_filter": year,
        "order_count": save_result.get("orders_saved", 0),
        "processing_duration_seconds": time.time() - workflow_start,
        "already_existed": save_result.get("already_existed", False),
        "orders_file": save_result.get("orders_file"),
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    logger.info(f"Saved backup manifest to {manifest_path}")
    return manifest_path


@flow(name="backup-amazon-orders")
def backup_amazon_orders(
    snapshot_date: datetime,
    credentials_block_name: str = "amazon-credentials",
    year: Optional[int] = None,
    full_details: bool = True,
    output_dir: Path = BACKUP_DIR,
) -> dict:
    """
    Main flow to backup Amazon order history.

    Args:
        snapshot_date: Date for this backup snapshot (for idempotency)
        credentials_block_name: Name of the Prefect Amazon credentials block
        year: Optional year to filter orders (e.g., 2023, 2024)
        full_details: Whether to fetch full order details (slower but more complete)
        output_dir: Base directory for backups

    Returns:
        Dictionary with backup results
    """
    logger = get_run_logger()
    workflow_start = time.time()

    # Ensure snapshot_date is timezone-aware
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    logger.info(f"Starting Amazon orders backup (snapshot date: {snapshot_date.isoformat()})")
    if year:
        logger.info(f"Filtering orders for year: {year}")

    # Load credentials
    logger.info(f"Loading Amazon credentials from block: {credentials_block_name}")
    amazon_credentials = AmazonBlock.load(credentials_block_name)
    username = amazon_credentials.username.get_secret_value()

    # Check if snapshot already exists (idempotency)
    if check_snapshot_exists(username, snapshot_date, output_dir):
        logger.info(f"Snapshot already exists and is complete. Skipping backup.")
        return {
            "success": True,
            "message": "Snapshot already exists",
            "snapshot_date": snapshot_date.isoformat(),
        }

    # Create authenticated session
    amazon_session = create_amazon_session(amazon_credentials)

    # Fetch order history
    orders = fetch_order_history(
        amazon_session=amazon_session,
        year=year,
        full_details=full_details,
    )

    if not orders:
        logger.warning("No orders found")
        return {
            "success": False,
            "message": "No orders found",
            "snapshot_date": snapshot_date.isoformat(),
        }

    # Save orders to disk
    save_result = save_orders_to_disk(
        orders=orders,
        username=username,
        snapshot_date=snapshot_date,
        year=year,
        output_dir=output_dir,
    )

    # Save backup manifest
    manifest_path = save_backup_manifest(
        username=username,
        snapshot_date=snapshot_date,
        save_result=save_result,
        year=year,
        workflow_start=workflow_start,
        output_dir=output_dir,
    )

    logger.info(f"Successfully backed up {save_result['orders_saved']} orders")
    logger.info(f"Manifest saved to {manifest_path}")

    return {
        "success": True,
        "order_count": save_result["orders_saved"],
        "orders_file": save_result["orders_file"],
        "manifest_file": str(manifest_path),
        "snapshot_date": snapshot_date.isoformat(),
        "year_filter": year,
    }


if __name__ == "__main__":
    # Example usage - backup all orders from 2024
    backup_amazon_orders(
        snapshot_date=datetime.now(timezone.utc),
        credentials_block_name="amazon-credentials",
        year=2024,
        full_details=True,
    )
