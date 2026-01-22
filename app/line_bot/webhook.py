"""LINE Bot webhook handler."""
from fastapi import Request, HTTPException, Header
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent,
    TextMessage,
    PostbackEvent,
    FollowEvent,
    TextSendMessage,
    FlexSendMessage,
    RichMenu,
    RichMenuSize,
    RichMenuArea,
    RichMenuBounds,
    MessageAction
)
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import calendar
import logging

from app.config import settings
from app.services.auth_service import AuthService
from app.services.request_service import RequestService
from app.models.request import RequestStatus
from app.exceptions import ValidationError, format_error_for_line

# Initialize LINE Bot API and Webhook Handler
line_bot_api = LineBotApi(settings.line_channel_access_token)
webhook_handler = WebhookHandler(settings.line_channel_secret)

# Configure logging
logger = logging.getLogger(__name__)


async def handle_webhook(
    request: Request,
    db: Session,
    x_line_signature: str = Header(None)
) -> dict:
    """
    Handle LINE webhook requests.
    
    This function validates the webhook signature and processes LINE events.
    
    Args:
        request: FastAPI request object
        db: Database session
        x_line_signature: LINE signature header for verification
        
    Returns:
        Success response dictionary
        
    Raises:
        HTTPException: If signature validation fails
        
    Validates: Requirements 1.1
    """
    # Get request body
    body = await request.body()
    body_str = body.decode('utf-8')
    
    # Validate signature
    if not x_line_signature:
        logger.error("Missing X-Line-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature header")
    
    try:
        # Store db session in a way handlers can access it
        # We'll use a context variable or pass it through event handling
        global _current_db_session
        _current_db_session = db
        
        # Verify webhook signature and parse events
        webhook_handler.handle(body_str, x_line_signature)
    except InvalidSignatureError:
        logger.error("Invalid LINE webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        _current_db_session = None
    
    return {"status": "ok"}


# Global variable to store current db session (will be set per request)
_current_db_session: Optional[Session] = None


@webhook_handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    """
    Handle follow event when user adds the bot as friend.
    
    Args:
        event: LINE FollowEvent object
    """
    user_id = event.source.user_id
    logger.info(f"New follower: {user_id}")
    
    try:
        if _current_db_session is None:
            logger.error("No database session available")
            return
        
        # Get user profile from LINE
        try:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except LineBotApiError:
            display_name = f"ユーザー_{user_id[-8:]}"
        
        # Register new worker
        auth_service = AuthService(_current_db_session)
        worker, created = auth_service.get_or_create_worker(user_id, display_name)
        
        if created:
            logger.info(f"New worker registered on follow: {worker.name} (ID: {worker.id})")
        
        # Send welcome message
        welcome_message = TextSendMessage(
            text=f"こんにちは、{display_name}さん！\n"
                 f"シフト申請システムへようこそ。\n\n"
                 f"利用可能なコマンド:\n"
                 f"・申請 - NG日を申請\n"
                 f"・一覧 - 申請一覧を表示\n\n"
                 f"何かメッセージを送信してください。"
        )
        line_bot_api.reply_message(event.reply_token, welcome_message)
        
    except Exception as e:
        logger.error(f"Error in handle_follow: {str(e)}")


@webhook_handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event: MessageEvent):
    """
    Handle text message events from LINE.
    
    This function processes text messages sent by users and routes them
    to appropriate handlers based on message content.
    
    Args:
        event: LINE MessageEvent object
        
    Validates: Requirements 1.1
    """
    user_id = event.source.user_id
    message_text = event.message.text
    
    logger.info(f"Received text message from {user_id}: {message_text}")
    
    try:
        # Check if we have a database session
        if _current_db_session is None:
            logger.error("No database session available")
            reply_message = TextSendMessage(
                text="システムエラーが発生しました。後でもう一度お試しください。"
            )
            line_bot_api.reply_message(event.reply_token, reply_message)
            return
        
        # Get or create user (auto-registration)
        auth_service = AuthService(_current_db_session)
        
        try:
            # Get user profile from LINE
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except LineBotApiError:
            display_name = f"ユーザー_{user_id[-8:]}"  # Use last 8 chars of user_id as fallback
        
        # Get or create worker
        worker, created = auth_service.get_or_create_worker(user_id, display_name)
        
        if created:
            logger.info(f"New worker registered: {worker.name} (ID: {worker.id})")
            welcome_message = TextSendMessage(
                text=f"こんにちは、{display_name}さん！\n"
                     f"シフト申請システムへようこそ。\n\n"
                     f"利用可能なコマンド:\n"
                     f"・申請 - NG日を申請\n"
                     f"・一覧 - 申請一覧を表示"
            )
            line_bot_api.reply_message(event.reply_token, welcome_message)
            return
        
        # Handle calendar request
        if message_text in ["申請", "カレンダー", "NG日申請"]:
            success = show_calendar(user_id, event.reply_token, _current_db_session)
            if not success:
                reply_message = TextSendMessage(
                    text="カレンダーの表示に失敗しました。後でもう一度お試しください。"
                )
                line_bot_api.reply_message(event.reply_token, reply_message)
        # Handle request list request
        elif message_text in ["一覧", "申請一覧", "リスト"]:
            success = show_request_list(user_id, event.reply_token, _current_db_session)
            if not success:
                reply_message = TextSendMessage(
                    text="申請一覧の表示に失敗しました。後でもう一度お試しください。"
                )
                line_bot_api.reply_message(event.reply_token, reply_message)
        else:
            reply_message = TextSendMessage(
                text=f"メッセージを受信しました: {message_text}\n\n"
                     f"利用可能なコマンド:\n"
                     f"・申請 - NG日を申請\n"
                     f"・一覧 - 申請一覧を表示"
            )
            line_bot_api.reply_message(event.reply_token, reply_message)
    except LineBotApiError as e:
        logger.error(f"Error sending reply: {str(e)}")
    except Exception as e:
        logger.error(f"Error in handle_text_message: {str(e)}")
        reply_message = TextSendMessage(
            text="システムエラーが発生しました。後でもう一度お試しください。"
        )
        try:
            line_bot_api.reply_message(event.reply_token, reply_message)
        except:
            pass


@webhook_handler.add(PostbackEvent)
def handle_postback(event: PostbackEvent):
    """
    Handle postback events from LINE (e.g., button clicks, date selections).
    
    This function processes postback actions from interactive elements
    like buttons and date pickers in Flex Messages.
    
    Args:
        event: LINE PostbackEvent object
        
    Validates: Requirements 1.1
    """
    user_id = event.source.user_id
    postback_data = event.postback.data
    
    logger.info(f"Received postback from {user_id}: {postback_data}")
    
    try:
        # Check if we have a database session
        if _current_db_session is None:
            logger.error("No database session available")
            reply_message = TextSendMessage(
                text="システムエラーが発生しました。後でもう一度お試しください。"
            )
            line_bot_api.reply_message(event.reply_token, reply_message)
            return
        
        # Parse postback data
        params = {}
        for param in postback_data.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value
        
        action = params.get('action')
        
        if action == 'request_date':
            # Handle date selection for NG day request
            date_str = params.get('date')
            try:
                request_date = date.fromisoformat(date_str)
                
                # Get worker by LINE ID
                auth_service = AuthService(_current_db_session)
                worker = auth_service.get_worker_by_line_id(user_id)
                
                if not worker:
                    reply_message = TextSendMessage(
                        text="ユーザー情報が見つかりません。\n"
                             "システム管理者にお問い合わせください。"
                    )
                    line_bot_api.reply_message(event.reply_token, reply_message)
                    return
                
                # Create the request
                request_service = RequestService(_current_db_session)
                new_request = request_service.create_request(
                    worker_id=worker.id,
                    request_date=request_date
                )
                
                # Send success message
                reply_message = TextSendMessage(
                    text=f"✅ {request_date.strftime('%Y年%m月%d日')}のNG日申請を受け付けました。\n"
                         f"申請ID: {new_request.id[:8]}...\n"
                         f"ステータス: 保留中"
                )
                line_bot_api.reply_message(event.reply_token, reply_message)
                
            except ValidationError as e:
                # Send user-friendly error message
                logger.error(f"Validation error creating request: {str(e)}")
                error_message = format_error_for_line(e)
                reply_message = TextSendMessage(text=error_message)
                line_bot_api.reply_message(event.reply_token, reply_message)
                
            except Exception as e:
                logger.error(f"Error creating request: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"User ID: {user_id}")
                logger.error(f"Request date: {date_str}")
                reply_message = TextSendMessage(
                    text="申請の作成中にエラーが発生しました。\n"
                         "後でもう一度お試しください。"
                )
                line_bot_api.reply_message(event.reply_token, reply_message)
            
        elif action == 'request_disabled':
            # User clicked on an already requested date
            date_str = params.get('date')
            reply_message = TextSendMessage(
                text=f"この日付は既に申請済みです: {date_str}"
            )
            line_bot_api.reply_message(event.reply_token, reply_message)
            
        else:
            # Unknown action
            reply_message = TextSendMessage(
                text="アクションを受信しました。\n"
                     "申請機能は現在実装中です。"
            )
            line_bot_api.reply_message(event.reply_token, reply_message)
            
    except LineBotApiError as e:
        logger.error(f"Error sending reply: {str(e)}")





def get_user_profile(user_id: str) -> Optional[dict]:
    """
    Get LINE user profile information.
    
    Args:
        user_id: LINE user ID
        
    Returns:
        Dictionary containing user profile (displayName, userId, pictureUrl, statusMessage)
        or None if profile cannot be retrieved
    """
    try:
        profile = line_bot_api.get_profile(user_id)
        return {
            "display_name": profile.display_name,
            "user_id": profile.user_id,
            "picture_url": profile.picture_url,
            "status_message": profile.status_message
        }
    except Exception as e:
        logger.error(f"Error getting user profile for {user_id}: {str(e)}")
        return None


def send_message(user_id: str, message: str) -> bool:
    """
    Send a push message to a LINE user.
    
    Args:
        user_id: LINE user ID
        message: Message text to send
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text=message)
        )
        logger.info(f"Message sent to {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending message to {user_id}: {str(e)}")
        return False


def generate_calendar_flex_message(
    user_id: str,
    db: Session,
    current_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Generate a Flex Message calendar for the next month.
    
    This function creates an interactive calendar showing only next month's dates.
    Dates that have already been requested by the user are disabled.
    
    Args:
        user_id: LINE user ID
        db: Database session
        current_date: Current date (defaults to today if not provided)
        
    Returns:
        Flex Message JSON structure
        
    Validates: Requirements 1.1, 1.2
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting calendar generation for user: {user_id}")
        
        if current_date is None:
            current_date = date.today()
        
        logger.info(f"Current date: {current_date}")
        
        # Calculate next month
        next_month_date = current_date + relativedelta(months=1)
        year = next_month_date.year
        month = next_month_date.month
        
        logger.info(f"Target month: {year}-{month}")
        
        # Get month name in Japanese
        month_names_ja = [
            "1月", "2月", "3月", "4月", "5月", "6月",
            "7月", "8月", "9月", "10月", "11月", "12月"
        ]
        month_name = month_names_ja[month - 1]
        
        logger.info(f"Month name: {month_name}")
        
        # Get existing requests for this user in the next month
        request_service = RequestService(db)
        auth_service = AuthService(db)
        
        logger.info(f"Getting worker by LINE ID: {user_id}")
        # Get worker by LINE ID
        worker = auth_service.get_worker_by_line_id(user_id)
        existing_requests = []
        if worker:
            logger.info(f"Worker found: {worker.name} (ID: {worker.id})")
            requests = request_service.get_requests_by_worker(worker.id)
            logger.info(f"Found {len(requests)} total requests for worker")
            # Filter for next month only
            existing_requests = [
                req.request_date for req in requests
                if req.request_date.year == year and req.request_date.month == month
            ]
            logger.info(f"Found {len(existing_requests)} requests for target month: {existing_requests}")
        else:
            logger.warning(f"Worker not found for LINE ID: {user_id}")
        
        # Get calendar data
        cal = calendar.monthcalendar(year, month)
        logger.info(f"Calendar data: {cal}")
        
        # Day of week headers
        day_headers = ["月", "火", "水", "木", "金", "土", "日"]
        
        # Build calendar rows
        calendar_rows = []
        
        # Header row with day names
        header_contents = []
        for day_name in day_headers:
            header_contents.append({
                "type": "text",
                "text": day_name,
                "size": "md",
                "color": "#666666",
                "align": "center",
                "flex": 1,
                "weight": "bold"
            })
        
        calendar_rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": header_contents,
            "spacing": "xs",
            "margin": "sm"
        })
        
        # Date rows
        for week in cal:
            week_contents = []
            for day in week:
                if day == 0:
                    # Empty cell for days outside the month
                    week_contents.append({
                        "type": "spacer",
                        "size": "md"
                    })
                else:
                    day_date = date(year, month, day)
                    is_requested = day_date in existing_requests
                    
                    # Create button for each day
                    button_style = "primary" if not is_requested else "secondary"
                    button_color = "#17c950" if not is_requested else "#aaaaaa"
                    
                    if is_requested:
                        # Disabled button for already requested dates
                        week_contents.append({
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": str(day),
                                "data": f"action=request_disabled&date={day_date.isoformat()}",
                                "displayText": f"{month_name}{day}日は既に申請済みです"
                            },
                            "style": button_style,
                            "color": button_color,
                            "height": "md",
                            "flex": 1,
                            "margin": "xs"
                        })
                    else:
                        # Active button for available dates
                        week_contents.append({
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": str(day),
                                "data": f"action=request_date&date={day_date.isoformat()}",
                                "displayText": f"{month_name}{day}日を申請します"
                            },
                            "style": button_style,
                            "color": button_color,
                            "height": "md",
                            "flex": 1,
                            "margin": "xs"
                        })
            
            calendar_rows.append({
                "type": "box",
                "layout": "horizontal",
                "contents": week_contents,
                "spacing": "xs",
                "margin": "xs"
            })
        
        # Build the complete Flex Message
        flex_message = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{year}年{month_name}",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#ffffff"
                    },
                    {
                        "type": "text",
                        "text": "NG日を選択してください",
                        "size": "sm",
                        "color": "#ffffff",
                        "margin": "sm"
                    }
                ],
                "backgroundColor": "#17c950"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": calendar_rows,
                "spacing": "sm",
                "paddingAll": "lg"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "緑: 選択可能 / 灰色: 申請済み",
                        "size": "xs",
                        "color": "#999999",
                        "align": "center"
                    }
                ]
            }
        }
        
        logger.info(f"Calendar flex message generated successfully for user: {user_id}")
        return flex_message
        
    except Exception as e:
        logger.error(f"Error generating calendar for user {user_id}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


def show_calendar(user_id: str, reply_token: str, db: Session) -> bool:
    """
    Show calendar to user via LINE.
    
    Args:
        user_id: LINE user ID
        reply_token: LINE reply token
        db: Database session
        
    Returns:
        True if calendar sent successfully, False otherwise
        
    Validates: Requirements 1.1, 1.2
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Generating calendar for user: {user_id}")
        flex_message_content = generate_calendar_flex_message(user_id, db)
        
        logger.info(f"Calendar content generated successfully for user: {user_id}")
        
        flex_message = FlexSendMessage(
            alt_text="NG日申請カレンダー",
            contents=flex_message_content
        )
        
        logger.info(f"Sending calendar message to user: {user_id}")
        line_bot_api.reply_message(reply_token, flex_message)
        logger.info(f"Calendar sent successfully to {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending calendar to {user_id}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def generate_request_list_flex_message(
    user_id: str,
    db: Session
) -> Dict[str, Any]:
    """
    Generate a Flex Message showing the user's request list.
    
    This function creates a list of all requests made by the user,
    showing date, status, and request date/time. Requests are sorted
    by date (newest first) and color-coded by status.
    
    Args:
        user_id: LINE user ID
        db: Database session
        
    Returns:
        Flex Message JSON structure
        
    Validates: Requirements 3.1, 3.2, 3.3
    """
    # Get worker by LINE ID
    auth_service = AuthService(db)
    worker = auth_service.get_worker_by_line_id(user_id)
    
    if not worker:
        # Return error message if worker not found
        return {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "ユーザー情報が見つかりません",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#ff0000"
                    },
                    {
                        "type": "text",
                        "text": "システム管理者にお問い合わせください。",
                        "size": "sm",
                        "color": "#999999",
                        "margin": "md"
                    }
                ]
            }
        }
    
    # Get all requests for this worker (sorted by date descending)
    request_service = RequestService(db)
    requests = request_service.get_requests_by_worker(worker.id)
    
    # Build request list items
    request_items = []
    
    if not requests:
        # No requests found
        request_items.append({
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "申請がありません",
                    "size": "md",
                    "color": "#999999",
                    "align": "center"
                }
            ],
            "paddingAll": "md"
        })
    else:
        # Create an item for each request
        for request in requests:
            # Determine status display and color
            status_text = ""
            status_color = ""
            
            if request.status == RequestStatus.PENDING:
                status_text = "保留中"
                status_color = "#FFA500"  # Orange
            elif request.status == RequestStatus.APPROVED:
                status_text = "承認済み"
                status_color = "#17c950"  # Green
            elif request.status == RequestStatus.REJECTED:
                status_text = "却下"
                status_color = "#ff0000"  # Red
            
            # Format dates
            request_date_str = request.request_date.strftime("%Y年%m月%d日")
            created_at_str = request.created_at.strftime("%Y/%m/%d %H:%M")
            
            # Create request item box
            request_item = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": request_date_str,
                                "weight": "bold",
                                "size": "lg",
                                "flex": 3
                            },
                            {
                                "type": "text",
                                "text": status_text,
                                "size": "sm",
                                "color": status_color,
                                "weight": "bold",
                                "align": "end",
                                "flex": 1
                            }
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"申請日時: {created_at_str}",
                        "size": "xs",
                        "color": "#999999",
                        "margin": "sm"
                    }
                ],
                "paddingAll": "md",
                "margin": "md",
                "backgroundColor": "#f5f5f5",
                "cornerRadius": "md"
            }
            
            request_items.append(request_item)
    
    # Build the complete Flex Message
    flex_message = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "申請一覧",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#ffffff"
                },
                {
                    "type": "text",
                    "text": f"全{len(requests)}件",
                    "size": "sm",
                    "color": "#ffffff",
                    "margin": "sm"
                }
            ],
            "backgroundColor": "#17c950"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": request_items,
            "spacing": "none",
            "paddingAll": "md"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🟢承認済み 🟠保留中 🔴却下",
                    "size": "xs",
                    "color": "#999999",
                    "align": "center"
                }
            ]
        }
    }
    
    return flex_message


def show_request_list(user_id: str, reply_token: str, db: Session) -> bool:
    """
    Show request list to user via LINE.
    
    Args:
        user_id: LINE user ID
        reply_token: LINE reply token
        db: Database session
        
    Returns:
        True if request list sent successfully, False otherwise
        
    Validates: Requirements 3.1, 3.2, 3.3
    """
    try:
        flex_message_content = generate_request_list_flex_message(user_id, db)
        
        flex_message = FlexSendMessage(
            alt_text="申請一覧",
            contents=flex_message_content
        )
        
        line_bot_api.reply_message(reply_token, flex_message)
        logger.info(f"Request list sent to {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending request list to {user_id}: {str(e)}")
        return False


def create_rich_menu() -> Optional[str]:
    """
    Create a Rich Menu for the LINE bot.
    
    This function creates a Rich Menu with two buttons:
    - 申請 (Application): Shows the calendar for NG day requests
    - 一覧 (List): Shows the user's request list
    
    Returns:
        Rich Menu ID if created successfully, None otherwise
        
    Validates: Requirements 1.1, 3.1
    """
    try:
        # Define Rich Menu structure
        rich_menu = RichMenu(
            size=RichMenuSize(width=2500, height=843),
            selected=True,
            name="シフト申請メニュー",
            chat_bar_text="メニュー",
            areas=[
                # Left button: 申請 (Application)
                RichMenuArea(
                    bounds=RichMenuBounds(x=0, y=0, width=1250, height=843),
                    action=MessageAction(label="申請", text="申請")
                ),
                # Right button: 一覧 (List)
                RichMenuArea(
                    bounds=RichMenuBounds(x=1250, y=0, width=1250, height=843),
                    action=MessageAction(label="一覧", text="一覧")
                )
            ]
        )
        
        # Create the Rich Menu
        rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu)
        logger.info(f"Rich Menu created with ID: {rich_menu_id}")
        
        return rich_menu_id
    except Exception as e:
        logger.error(f"Error creating Rich Menu: {str(e)}")
        return None


def set_rich_menu_image(rich_menu_id: str, image_path: str) -> bool:
    """
    Set the image for a Rich Menu.
    
    Args:
        rich_menu_id: Rich Menu ID
        image_path: Path to the Rich Menu image file
        
    Returns:
        True if image set successfully, False otherwise
        
    Note:
        The image should be 2500x843 pixels in PNG or JPEG format.
        For this implementation, you'll need to create an image with:
        - Left half: "申請" text/icon
        - Right half: "一覧" text/icon
    """
    try:
        with open(image_path, 'rb') as f:
            line_bot_api.set_rich_menu_image(rich_menu_id, 'image/png', f)
        logger.info(f"Rich Menu image set for ID: {rich_menu_id}")
        return True
    except Exception as e:
        logger.error(f"Error setting Rich Menu image: {str(e)}")
        return False


def set_default_rich_menu(rich_menu_id: str) -> bool:
    """
    Set a Rich Menu as the default for all users.
    
    Args:
        rich_menu_id: Rich Menu ID
        
    Returns:
        True if set successfully, False otherwise
        
    Validates: Requirements 1.1, 3.1
    """
    try:
        line_bot_api.set_default_rich_menu(rich_menu_id)
        logger.info(f"Rich Menu {rich_menu_id} set as default")
        return True
    except Exception as e:
        logger.error(f"Error setting default Rich Menu: {str(e)}")
        return False


def link_rich_menu_to_user(user_id: str, rich_menu_id: str) -> bool:
    """
    Link a Rich Menu to a specific user.
    
    Args:
        user_id: LINE user ID
        rich_menu_id: Rich Menu ID
        
    Returns:
        True if linked successfully, False otherwise
    """
    try:
        line_bot_api.link_rich_menu_to_user(user_id, rich_menu_id)
        logger.info(f"Rich Menu {rich_menu_id} linked to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error linking Rich Menu to user: {str(e)}")
        return False


def get_rich_menu_list() -> List[str]:
    """
    Get list of all Rich Menu IDs.
    
    Returns:
        List of Rich Menu IDs
    """
    try:
        rich_menu_list = line_bot_api.get_rich_menu_list()
        return [menu.rich_menu_id for menu in rich_menu_list]
    except Exception as e:
        logger.error(f"Error getting Rich Menu list: {str(e)}")
        return []


def delete_rich_menu(rich_menu_id: str) -> bool:
    """
    Delete a Rich Menu.
    
    Args:
        rich_menu_id: Rich Menu ID
        
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        line_bot_api.delete_rich_menu(rich_menu_id)
        logger.info(f"Rich Menu {rich_menu_id} deleted")
        return True
    except Exception as e:
        logger.error(f"Error deleting Rich Menu: {str(e)}")
        return False


def setup_rich_menu() -> Optional[str]:
    """
    Setup Rich Menu for the LINE bot.
    
    This is a convenience function that:
    1. Creates a new Rich Menu
    2. Sets it as the default for all users
    
    Note: You'll need to manually set the Rich Menu image using
    set_rich_menu_image() after calling this function.
    
    Returns:
        Rich Menu ID if setup successful, None otherwise
        
    Validates: Requirements 1.1, 3.1
    """
    # Create Rich Menu
    rich_menu_id = create_rich_menu()
    if not rich_menu_id:
        logger.error("Failed to create Rich Menu")
        return None
    
    # Set as default
    if not set_default_rich_menu(rich_menu_id):
        logger.error("Failed to set default Rich Menu")
        # Clean up by deleting the created menu
        delete_rich_menu(rich_menu_id)
        return None
    
    logger.info(f"Rich Menu setup complete. ID: {rich_menu_id}")
    logger.info("Note: You need to set the Rich Menu image using set_rich_menu_image()")
    
    return rich_menu_id
