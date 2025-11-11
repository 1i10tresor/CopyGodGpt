# telegram_listener.py
"""Telegram connection and message listening"""

import logging
import re
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
        # List of channels to monitor
        self.channels = [config.CHANNEL_ID_1, config.CHANNEL_ID_2]
    
    async def start(self):
        """Start Telegram client"""
        try:
            await self.client.start(phone=config.PHONE_NUMBER)
            logger.info("✅ Telegram client started successfully")
            
            # Get info for all channels
            for i, channel_id in enumerate(self.channels, 1):
                try:
                    entity = await self.client.get_entity(channel_id)
                    if hasattr(entity, 'title'):
                        logger.info(f"Connected to channel {i}: {entity.title} (ID: {channel_id})")
                    else:
                        logger.info(f"Connected to channel {i} ID: {channel_id}")
                except Exception as e:
                    logger.warning(f"Could not get info for channel {i} (ID: {channel_id}): {e}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram client: {e}")
            return False
    
    async def listen_for_signals(self):
        """Listen for new messages in the channel"""
        
        @self.client.on(events.NewMessage(chats=self.channels))
        async def message_handler(event):
            """Handle new messages from the channel"""
            try:
                message = event.message
                
                # Identify which channel the message came from
                channel_source = "Unknown"
                try:
                    chat = await event.get_chat()
                    if hasattr(chat, 'title'):
                        channel_source = chat.title
                    elif hasattr(chat, 'username'):
                        channel_source = chat.username
                    else:
                        channel_source = f"Channel {message.peer_id.channel_id if hasattr(message.peer_id, 'channel_id') else 'Unknown'}"
                except:
                    channel_source = f"Channel {message.peer_id.channel_id if hasattr(message.peer_id, 'channel_id') else 'Unknown'}"
                
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
                
                # Check for modification commands first
                text_lower = text.lower().strip()
                modification_commands_patterns = [
                    r'\bcloturez now\b',
                    r'\bclôturez now\b',
                    r'\bbreakeven\b',
                    r'\bbe\b',
                    r'\bb\.e\b',
                    r'\bprendre tp1 now\b',
                    r'\bmove sl\b'
                ]
                
                is_modification_command = any(re.search(pattern, text_lower) for pattern in modification_commands_patterns)
                
                if is_modification_command:
                    # Check if this is a reply to another message
                    if message.reply_to_msg_id:
                        original_message_id = message.reply_to_msg_id
                        logger.info(f"🔧 Modification command detected: '{text}' in reply to message {original_message_id}")
                        
                        # Handle the modification command
                        self.order_manager.handle_modification_command(original_message_id, text)
                        return
                    else:
                        logger.warning(f"⚠️ Modification command '{text}' ignored - not a reply to any message")
                        return
                
                # Log message receipt
                preview = text[:100] + "..." if len(text) > 100 else text
                preview = preview.replace('\n', ' ')  # Single line for log
                logger.info(f"📩 New message from {author} in {channel_source}: {preview}")
                
                # Parse signal
                signal = self.parser.parse(text, author, message.id)
                
                if signal:
                    logger.info(f"📊 Valid signal detected from {channel_source}: {signal}")
                    
                    # Place orders on the account
                    placed_tickets = self.order_manager.place_orders(signal, self.account_config)
                    
                    if len(placed_tickets) > 0:
                        logger.info(f"✅ Successfully placed {len(placed_tickets)} orders for signal #{signal.message_id}")
                    else:
                        logger.warning(f"⚠️ No orders placed for signal #{signal.message_id}")
                else:
                    logger.debug(f"Not a valid trading signal from {author} in {channel_source}")
                
            except Exception as e:
                logger.error(f"❌ Error processing message: {e}", exc_info=True)
        
        logger.info(f"👂 Listening for signals in {len(self.channels)} channels: {self.channels}")
        logger.info("Bot is running. Press Ctrl+C to stop.")
        
        # Keep the client running
        await self.client.run_until_disconnected()
    
    async def stop(self):
        """Stop Telegram client"""
        await self.client.disconnect()
        logger.info("Telegram client disconnected")