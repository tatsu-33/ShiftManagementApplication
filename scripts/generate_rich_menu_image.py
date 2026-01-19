#!/usr/bin/env python3
"""
Script to generate a simple Rich Menu image.

This script creates a basic Rich Menu image (2500x843 pixels) with:
- Left half: "申請" (Application) button
- Right half: "一覧" (List) button

Requirements:
    pip install Pillow

Usage:
    python scripts/generate_rich_menu_image.py [--output PATH]
"""
import argparse
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow library is required")
    print("Install it with: pip install Pillow")
    sys.exit(1)


def create_rich_menu_image(output_path: str = "rich_menu.png"):
    """
    Create a Rich Menu image.
    
    Args:
        output_path: Path to save the image
    """
    # Rich Menu dimensions
    width = 2500
    height = 843
    
    # Create image with white background
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Define colors
    left_color = '#17c950'  # LINE green
    right_color = '#00b900'  # Darker green
    text_color = 'white'
    border_color = '#cccccc'
    
    # Draw left button background (申請)
    draw.rectangle([(0, 0), (width // 2 - 1, height)], fill=left_color)
    
    # Draw right button background (一覧)
    draw.rectangle([(width // 2, 0), (width, height)], fill=right_color)
    
    # Draw center divider
    draw.line([(width // 2, 0), (width // 2, height)], fill=border_color, width=2)
    
    # Try to use a font that supports Japanese characters
    font_size = 120
    try:
        # Try common Japanese font paths
        font_paths = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",  # macOS
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",  # Linux
            "C:\\Windows\\Fonts\\msgothic.ttc",  # Windows
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux Noto
        ]
        
        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue
        
        if font is None:
            # Fallback to default font
            font = ImageFont.load_default()
            print("Warning: Could not load Japanese font, using default font")
    except Exception as e:
        font = ImageFont.load_default()
        print(f"Warning: Error loading font: {e}")
    
    # Draw text for left button (申請)
    left_text = "申請"
    # Get text bounding box
    try:
        left_bbox = draw.textbbox((0, 0), left_text, font=font)
        left_text_width = left_bbox[2] - left_bbox[0]
        left_text_height = left_bbox[3] - left_bbox[1]
    except:
        # Fallback for older Pillow versions
        left_text_width, left_text_height = draw.textsize(left_text, font=font)
    
    left_x = (width // 4) - (left_text_width // 2)
    left_y = (height // 2) - (left_text_height // 2)
    draw.text((left_x, left_y), left_text, fill=text_color, font=font)
    
    # Draw text for right button (一覧)
    right_text = "一覧"
    try:
        right_bbox = draw.textbbox((0, 0), right_text, font=font)
        right_text_width = right_bbox[2] - right_bbox[0]
        right_text_height = right_bbox[3] - right_bbox[1]
    except:
        right_text_width, right_text_height = draw.textsize(right_text, font=font)
    
    right_x = (width * 3 // 4) - (right_text_width // 2)
    right_y = (height // 2) - (right_text_height // 2)
    draw.text((right_x, right_y), right_text, fill=text_color, font=font)
    
    # Save image
    img.save(output_path, 'PNG')
    print(f"Rich Menu image created: {output_path}")
    print(f"Dimensions: {width}x{height} pixels")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Generate Rich Menu image for LINE bot'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='rich_menu.png',
        help='Output path for the image (default: rich_menu.png)'
    )
    
    args = parser.parse_args()
    
    try:
        create_rich_menu_image(args.output)
        print("\nYou can now use this image with:")
        print(f"  python scripts/setup_rich_menu.py --image-path {args.output}")
        return 0
    except Exception as e:
        print(f"Error creating image: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
