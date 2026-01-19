"""Unit tests for Rich Menu functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from linebot.models import RichMenu, RichMenuSize, RichMenuArea, RichMenuBounds, MessageAction
from linebot.exceptions import LineBotApiError

from app.line_bot.webhook import (
    create_rich_menu,
    set_default_rich_menu,
    link_rich_menu_to_user,
    get_rich_menu_list,
    delete_rich_menu,
    setup_rich_menu
)


class TestRichMenuCreation:
    """Test Rich Menu creation functionality."""
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_create_rich_menu_success(self, mock_api):
        """Test successful Rich Menu creation."""
        # Arrange
        mock_api.create_rich_menu.return_value = "richmenu-test-id-123"
        
        # Act
        result = create_rich_menu()
        
        # Assert
        assert result == "richmenu-test-id-123"
        mock_api.create_rich_menu.assert_called_once()
        
        # Verify the Rich Menu structure
        call_args = mock_api.create_rich_menu.call_args
        rich_menu = call_args.kwargs['rich_menu']
        
        assert rich_menu.size.width == 2500
        assert rich_menu.size.height == 843
        assert rich_menu.selected is True
        assert rich_menu.name == "シフト申請メニュー"
        assert rich_menu.chat_bar_text == "メニュー"
        assert len(rich_menu.areas) == 2
        
        # Verify left button (申請)
        left_area = rich_menu.areas[0]
        assert left_area.bounds.x == 0
        assert left_area.bounds.y == 0
        assert left_area.bounds.width == 1250
        assert left_area.bounds.height == 843
        assert left_area.action.label == "申請"
        assert left_area.action.text == "申請"
        
        # Verify right button (一覧)
        right_area = rich_menu.areas[1]
        assert right_area.bounds.x == 1250
        assert right_area.bounds.y == 0
        assert right_area.bounds.width == 1250
        assert right_area.bounds.height == 843
        assert right_area.action.label == "一覧"
        assert right_area.action.text == "一覧"
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_create_rich_menu_api_error(self, mock_api):
        """Test Rich Menu creation with API error."""
        # Arrange
        mock_api.create_rich_menu.side_effect = Exception("API Error")
        
        # Act
        result = create_rich_menu()
        
        # Assert
        assert result is None


class TestRichMenuManagement:
    """Test Rich Menu management functions."""
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_set_default_rich_menu_success(self, mock_api):
        """Test setting default Rich Menu."""
        # Arrange
        rich_menu_id = "richmenu-test-id"
        
        # Act
        result = set_default_rich_menu(rich_menu_id)
        
        # Assert
        assert result is True
        mock_api.set_default_rich_menu.assert_called_once_with(rich_menu_id)
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_set_default_rich_menu_error(self, mock_api):
        """Test setting default Rich Menu with error."""
        # Arrange
        mock_api.set_default_rich_menu.side_effect = Exception("API Error")
        
        # Act
        result = set_default_rich_menu("test-id")
        
        # Assert
        assert result is False
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_link_rich_menu_to_user_success(self, mock_api):
        """Test linking Rich Menu to user."""
        # Arrange
        user_id = "U1234567890"
        rich_menu_id = "richmenu-test-id"
        
        # Act
        result = link_rich_menu_to_user(user_id, rich_menu_id)
        
        # Assert
        assert result is True
        mock_api.link_rich_menu_to_user.assert_called_once_with(user_id, rich_menu_id)
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_get_rich_menu_list_success(self, mock_api):
        """Test getting Rich Menu list."""
        # Arrange
        mock_menu1 = Mock()
        mock_menu1.rich_menu_id = "richmenu-1"
        mock_menu2 = Mock()
        mock_menu2.rich_menu_id = "richmenu-2"
        mock_api.get_rich_menu_list.return_value = [mock_menu1, mock_menu2]
        
        # Act
        result = get_rich_menu_list()
        
        # Assert
        assert result == ["richmenu-1", "richmenu-2"]
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_get_rich_menu_list_error(self, mock_api):
        """Test getting Rich Menu list with error."""
        # Arrange
        mock_api.get_rich_menu_list.side_effect = Exception("API Error")
        
        # Act
        result = get_rich_menu_list()
        
        # Assert
        assert result == []
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_delete_rich_menu_success(self, mock_api):
        """Test deleting Rich Menu."""
        # Arrange
        rich_menu_id = "richmenu-test-id"
        
        # Act
        result = delete_rich_menu(rich_menu_id)
        
        # Assert
        assert result is True
        mock_api.delete_rich_menu.assert_called_once_with(rich_menu_id)


class TestRichMenuSetup:
    """Test Rich Menu setup convenience function."""
    
    @patch('app.line_bot.webhook.delete_rich_menu')
    @patch('app.line_bot.webhook.set_default_rich_menu')
    @patch('app.line_bot.webhook.create_rich_menu')
    def test_setup_rich_menu_success(self, mock_create, mock_set_default, mock_delete):
        """Test successful Rich Menu setup."""
        # Arrange
        mock_create.return_value = "richmenu-new-id"
        mock_set_default.return_value = True
        
        # Act
        result = setup_rich_menu()
        
        # Assert
        assert result == "richmenu-new-id"
        mock_create.assert_called_once()
        mock_set_default.assert_called_once_with("richmenu-new-id")
        mock_delete.assert_not_called()
    
    @patch('app.line_bot.webhook.create_rich_menu')
    def test_setup_rich_menu_create_fails(self, mock_create):
        """Test Rich Menu setup when creation fails."""
        # Arrange
        mock_create.return_value = None
        
        # Act
        result = setup_rich_menu()
        
        # Assert
        assert result is None
    
    @patch('app.line_bot.webhook.delete_rich_menu')
    @patch('app.line_bot.webhook.set_default_rich_menu')
    @patch('app.line_bot.webhook.create_rich_menu')
    def test_setup_rich_menu_set_default_fails(self, mock_create, mock_set_default, mock_delete):
        """Test Rich Menu setup when setting default fails."""
        # Arrange
        mock_create.return_value = "richmenu-new-id"
        mock_set_default.return_value = False
        
        # Act
        result = setup_rich_menu()
        
        # Assert
        assert result is None
        mock_delete.assert_called_once_with("richmenu-new-id")


class TestRichMenuIntegration:
    """Test Rich Menu integration with webhook handlers."""
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_rich_menu_buttons_trigger_correct_actions(self, mock_api):
        """Test that Rich Menu buttons trigger the correct text messages."""
        # This test verifies that the Rich Menu is configured to send
        # the correct text messages that will be handled by the webhook
        
        # The Rich Menu should be configured so that:
        # - Left button sends "申請" which triggers calendar display
        # - Right button sends "一覧" which triggers request list display
        
        # Create Rich Menu
        mock_api.create_rich_menu.return_value = "richmenu-test"
        rich_menu_id = create_rich_menu()
        
        # Verify the actions are MessageAction with correct text
        call_args = mock_api.create_rich_menu.call_args
        rich_menu = call_args.kwargs['rich_menu']
        
        # Left button should send "申請"
        assert isinstance(rich_menu.areas[0].action, MessageAction)
        assert rich_menu.areas[0].action.text == "申請"
        
        # Right button should send "一覧"
        assert isinstance(rich_menu.areas[1].action, MessageAction)
        assert rich_menu.areas[1].action.text == "一覧"


# Validates: Requirements 1.1, 3.1
