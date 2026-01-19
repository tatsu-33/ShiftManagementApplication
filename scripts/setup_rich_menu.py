#!/usr/bin/env python3
"""
Script to setup Rich Menu for LINE bot.

This script creates and configures the Rich Menu with two buttons:
- 申請 (Application): Shows the calendar for NG day requests
- 一覧 (List): Shows the user's request list

Usage:
    python scripts/setup_rich_menu.py [--image-path PATH]

Note:
    If you provide an image path, make sure the image is 2500x843 pixels
    in PNG or JPEG format with:
    - Left half: "申請" text/icon
    - Right half: "一覧" text/icon
"""
import sys
import os
import argparse

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.line_bot.webhook import (
    setup_rich_menu,
    set_rich_menu_image,
    get_rich_menu_list,
    delete_rich_menu
)


def main():
    """Main function to setup Rich Menu."""
    parser = argparse.ArgumentParser(
        description='Setup Rich Menu for LINE bot'
    )
    parser.add_argument(
        '--image-path',
        type=str,
        help='Path to Rich Menu image (2500x843 pixels, PNG or JPEG)'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Delete all existing Rich Menus before creating new one'
    )
    
    args = parser.parse_args()
    
    # Clean up existing Rich Menus if requested
    if args.clean:
        print("Cleaning up existing Rich Menus...")
        existing_menus = get_rich_menu_list()
        for menu_id in existing_menus:
            if delete_rich_menu(menu_id):
                print(f"  Deleted Rich Menu: {menu_id}")
            else:
                print(f"  Failed to delete Rich Menu: {menu_id}")
    
    # Setup Rich Menu
    print("Creating Rich Menu...")
    rich_menu_id = setup_rich_menu()
    
    if not rich_menu_id:
        print("Failed to setup Rich Menu")
        return 1
    
    print(f"Rich Menu created successfully!")
    print(f"Rich Menu ID: {rich_menu_id}")
    
    # Set image if provided
    if args.image_path:
        if not os.path.exists(args.image_path):
            print(f"Error: Image file not found: {args.image_path}")
            return 1
        
        print(f"Setting Rich Menu image from: {args.image_path}")
        if set_rich_menu_image(rich_menu_id, args.image_path):
            print("Rich Menu image set successfully!")
        else:
            print("Failed to set Rich Menu image")
            return 1
    else:
        print("\nNote: No image provided. You need to set the Rich Menu image manually.")
        print("Create an image (2500x843 pixels) with:")
        print("  - Left half: '申請' text/icon")
        print("  - Right half: '一覧' text/icon")
        print(f"\nThen run:")
        print(f"  from app.line_bot.webhook import set_rich_menu_image")
        print(f"  set_rich_menu_image('{rich_menu_id}', 'path/to/image.png')")
    
    print("\nRich Menu setup complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
