#!/usr/bin/env python3
"""
Script to connect to Synology NAS and list directories.
Uses credentials from .env file.
"""

import os
from dotenv import load_dotenv
from synology_api import filestation

def main():
    # Load environment variables
    load_dotenv()

    username = os.getenv('SYNOLOGY_USERNAME')
    password = os.getenv('SYNOLOGY_PASSWORD')
    port = int(os.getenv('SYNOLOGY_PORT'))

    if not username or not password:
        print("Error: SYNOLOGY_USERNAME and SYNOLOGY_PASSWORD must be set in .env")
        return

    # Connect to Synology FileStation
    # Note: You'll need to provide your Synology NAS IP address or hostname
    synology_host = os.getenv('SYNOLOGY_IP_ADDR')

    print(f"\nConnecting to {synology_host}:{port}...")

    try:
        # Create FileStation API instance
        fs = filestation.FileStation(
            ip_address=synology_host,
            port=port,
            username=username,
            password=password,
            # Set to True if using HTTPS
            secure=False,
            # Set to True if you want to verify SSL certificates
            cert_verify=False,
            # Adjust based on your DSM version (6 or 7)
            dsm_version=7,
            # Set to True to enable debug logging
            debug=True,
            # Set to None if you don't want to use OTP code
            otp_code=None,
        )

        print("Successfully connected to Synology NAS!")
        print("\nListing directories in root share folders...")

        # List shared folders
        shared_folders = fs.get_list_share()

        if shared_folders.get('success'):
            shares = shared_folders['data']['shares']
            print(f"\nFound {len(shares)} shared folders:")
            print("-" * 60)

            for share in shares:
                share_name = share['name']
                share_path = share['path']
                print(f"\n📁 {share_name} ({share_path})")

                # List contents of each shared folder
                try:
                    contents = fs.get_file_list(folder_path=share_path)
                    if contents.get('success'):
                        files = contents['data']['files']
                        if files:
                            for item in files:
                                item_type = "📂" if item['isdir'] else "📄"
                                print(f"  {item_type} {item['name']}")
                        else:
                            print("  (empty)")
                except Exception as e:
                    print(f"  Error listing contents: {e}")
        else:
            print(f"Error getting shared folders: {shared_folders}")

    except Exception as e:
        print(f"Error connecting to Synology NAS: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure your Synology NAS is accessible on the network")
        print("2. Check that the IP address/hostname is correct")
        print("3. Verify that DSM is running and accessible")
        print("4. Check firewall settings on your NAS")
        print("5. Try using HTTPS (port 5001) if HTTP doesn't work")

if __name__ == "__main__":
    main()
