# Rich Menu Setup Guide

This guide explains how to set up the Rich Menu for the LINE bot.

## What is a Rich Menu?

A Rich Menu is a persistent menu that appears at the bottom of the LINE chat interface. It provides quick access to key functions without requiring users to type commands.

## Our Rich Menu Design

The Rich Menu has two buttons:

| 申請 (Application) | 一覧 (List) |
|-------------------|------------|
| Shows calendar for NG day requests | Shows user's request list |

## Setup Methods

### Method 1: Automatic Setup with Generated Image

This is the easiest method. It generates a simple Rich Menu image and sets it up automatically.

1. **Generate the Rich Menu image:**
   ```bash
   python scripts/generate_rich_menu_image.py --output rich_menu.png
   ```
   
   Note: This requires the Pillow library:
   ```bash
   pip install Pillow
   ```

2. **Setup the Rich Menu:**
   ```bash
   python scripts/setup_rich_menu.py --image-path rich_menu.png
   ```

3. **Done!** The Rich Menu is now active for all users.

### Method 2: Setup with Custom Image

If you want to use a custom-designed image:

1. **Create your Rich Menu image:**
   - Dimensions: 2500 x 843 pixels
   - Format: PNG or JPEG
   - Design:
     - Left half (0-1250px): "申請" button
     - Right half (1250-2500px): "一覧" button

2. **Setup the Rich Menu:**
   ```bash
   python scripts/setup_rich_menu.py --image-path path/to/your/image.png
   ```

### Method 3: Manual Setup via Python

You can also set up the Rich Menu programmatically:

```python
from app.line_bot.webhook import setup_rich_menu, set_rich_menu_image

# Create and set as default
rich_menu_id = setup_rich_menu()

# Set the image
set_rich_menu_image(rich_menu_id, 'path/to/image.png')
```

## Managing Rich Menus

### List Existing Rich Menus

```python
from app.line_bot.webhook import get_rich_menu_list

menu_ids = get_rich_menu_list()
print(f"Existing Rich Menus: {menu_ids}")
```

### Delete a Rich Menu

```python
from app.line_bot.webhook import delete_rich_menu

delete_rich_menu('rich-menu-id-here')
```

### Clean Up and Recreate

To delete all existing Rich Menus and create a new one:

```bash
python scripts/setup_rich_menu.py --clean --image-path rich_menu.png
```

## How It Works

### Button Actions

When users tap the Rich Menu buttons, they send text messages:

- **申請 button** → Sends "申請" → Shows calendar
- **一覧 button** → Sends "一覧" → Shows request list

These messages are handled by the `handle_text_message` function in `app/line_bot/webhook.py`.

### New Users

When a user adds the bot as a friend (Follow event), the default Rich Menu is automatically displayed. The welcome message also explains how to use the menu.

## Troubleshooting

### Rich Menu Not Appearing

1. Check if the Rich Menu is set as default:
   ```python
   from app.line_bot.webhook import get_rich_menu_list
   print(get_rich_menu_list())
   ```

2. Verify the LINE Bot API credentials in `.env`:
   ```
   LINE_CHANNEL_ACCESS_TOKEN=your_token_here
   LINE_CHANNEL_SECRET=your_secret_here
   ```

3. Try unlinking and re-adding the bot as a friend.

### Image Not Displaying

1. Verify image dimensions: Must be exactly 2500 x 843 pixels
2. Check file format: PNG or JPEG only
3. Ensure file size is under 1MB

### Buttons Not Working

1. Check the webhook handler logs for errors
2. Verify the text message handlers in `webhook.py` are working
3. Test by sending "申請" or "一覧" as text messages

## Requirements Validation

This Rich Menu implementation validates:

- **Requirement 1.1**: LINE interface for NG day requests
- **Requirement 3.1**: Access to request list via LINE

## Technical Details

### Rich Menu Structure

```python
RichMenu(
    size=RichMenuSize(width=2500, height=843),
    selected=True,
    name="シフト申請メニュー",
    chat_bar_text="メニュー",
    areas=[
        # Left button (0, 0) to (1250, 843)
        RichMenuArea(
            bounds=RichMenuBounds(x=0, y=0, width=1250, height=843),
            action=MessageAction(label="申請", text="申請")
        ),
        # Right button (1250, 0) to (2500, 843)
        RichMenuArea(
            bounds=RichMenuBounds(x=1250, y=0, width=1250, height=843),
            action=MessageAction(label="一覧", text="一覧")
        )
    ]
)
```

### API Functions

The following functions are available in `app/line_bot/webhook.py`:

- `create_rich_menu()` - Create a new Rich Menu
- `set_rich_menu_image(rich_menu_id, image_path)` - Set the image
- `set_default_rich_menu(rich_menu_id)` - Set as default for all users
- `link_rich_menu_to_user(user_id, rich_menu_id)` - Link to specific user
- `get_rich_menu_list()` - List all Rich Menus
- `delete_rich_menu(rich_menu_id)` - Delete a Rich Menu
- `setup_rich_menu()` - Convenience function to create and set as default

## References

- [LINE Messaging API - Rich Menu](https://developers.line.biz/en/docs/messaging-api/using-rich-menus/)
- [Rich Menu Design Guidelines](https://developers.line.biz/en/docs/messaging-api/rich-menu-design-guidelines/)
