# telegram_listener.py
"""Telegram connection and message listening"""

import logging
from telethon import TelegramClient, events
from telethon.tl.types import User, Channel, Chat
from parser import SignalParser
from order_manager import OrderManager
import config

logger = logging.getLogger(__name__)


class TelegramListener:
    """Manages Telegram connection and message listening"""
    
    def __init__(self, order_manager: OrderManager, account_config: dict):
        self.client = TelegramClient('trading_copier', config.API_ID, config.API_HASH)
        self.order_manager = order_manager
        self.account_config = account_config
        self.parser = SignalParser()
    
    async def start(self):
        """Start Telegram client"""
        try:
            await self.client.start(phone=config.PHONE_NUMBER)
            logger.info("✅ Telegram client started successfully")
            
            # Get channel info
            try:
                entity = await self.client.get_entity(config.CHANNEL_ID)
                if hasattr(entity, 'title'):
                    logger.info(f"Connected to channel: {entity.title}")
                else:
                    logger.info(f"Connected to channel ID: {config.CHANNEL_ID}")
            except Exception as e:
                logger.warning(f"Could not get channel info: {e}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram client: {e}")
            return False
    
    async def listen_for_signals(self):
        """Listen for new messages in the channel"""
        
        @self.client.on(events.NewMessage(chats=config.CHANNEL_ID))
        async def message_handler(event):
            """Handle new messages from the channel"""
            try:
                message = event.message
                
                # Extract author information based on sender type
                author = "Unknown"
                if message.sender:
                    if isinstance(message.sender, User):
                        # It's a user
                        author = message.sender.username or message.sender.first_name or f"User{message.sender.id}"
                    elif isinstance(message.sender, Channel):
                        # It's a channel
                        author = message.sender.title or message.sender.username or f"Channel{message.sender.id}"
                    elif isinstance(message.sender, Chat):
                        # It's a chat/group
                        author = message.sender.title or f"Chat{message.sender.id}"
                    else:
                        # Unknown type
                        author = str(type(message.sender).__name__)
                
                # For channels, if no sender info, use channel name
                if author == "Unknown" and message.peer_id:
                    try:
                        entity = await event.get_chat()
                        if hasattr(entity, 'title'):
                            author = entity.title
                        elif hasattr(entity, 'username'):
                            author = entity.username
                        else:
                            author = "Channel"
                    except:
                        author = "Channel"
                
                text = message.text or ""
                
                # Skip empty messages
                if not text:
                    logger.debug("Skipping empty message")
                    return
                
                # Log message receipt
                preview = text[:100] + "..." if len(text) > 100 else text
                preview = preview.replace('\n', ' ')  # Single line for log
                logger.info(f"📩 New message from {author}: {preview}")
                
                # Parse signal
                signal = self.parser.parse(text, author, message.id)
                
                if signal:
                    logger.info(f"📊 Valid signal detected: {signal}")
                    
                    # Place orders on the account
                    placed_tickets = self.order_manager.place_orders(signal, self.account_config)
                    
                    if len(placed_tickets) > 0:
                        logger.info(f"✅ Successfully placed {len(placed_tickets)} orders for signal #{signal.message_id}")
                    else:
                        logger.warning(f"⚠️ No orders placed for signal #{signal.message_id}")
                else:
                    logger.debug(f"Not a valid trading signal from {author}")
                
            except Exception as e:
                logger.error(f"❌ Error processing message: {e}", exc_info=True)
        
        logger.info(f"👂 Listening for signals in channel {config.CHANNEL_ID}")
        logger.info("Bot is running. Press Ctrl+C to stop.")
        
        # Keep the client running
        await self.client.run_until_disconnected()
    
    async def stop(self):
        """Stop Telegram client"""
        await self.client.disconnect()
        logger.info("Telegram client disconnected")