#!/usr/bin/env python3
"""
Trading Signal Copier - Main Application
Copies trading signals from Telegram to MetaTrader 5
"""

import asyncio
import logging
import sys
import io
from multi_account_manager import MultiAccountManager
from telegram_listener import TelegramListener
import config

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Setup logging with UTF-8 encoding
class UTF8FileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding='utf-8', delay=False):
        super().__init__(filename, mode, encoding, delay)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        UTF8FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TradingCopier:
    """Main application orchestrator"""
    
    def __init__(self):
        self.multi_account_manager = MultiAccountManager(config.ACCOUNTS)
        self.telegram_listener = TelegramListener(self.multi_account_manager)
        self.tasks = []
    
    async def start(self):
        """Initialize and start all components"""
        logger.info("=" * 50)
        logger.info("Starting Trading Signal Copier")
        logger.info("=" * 50)
        
        # Connect to all MT5 accounts
        logger.info("Connecting to MetaTrader 5 accounts...")
        if not self.multi_account_manager.connect_all_accounts():
            logger.error("Failed to connect to any MT5 accounts. Exiting.")
            logger.error("Please check:")
            logger.error("1. MT5 terminals are installed and running")
            logger.error("2. Login credentials in ACCOUNTS config are correct")
            logger.error("3. Server name is correct")
            logger.error("4. Algorithm trading is enabled in MT5")
            return False
        logger.info("✅ MT5 accounts connected successfully")
        
        # Start Telegram client
        logger.info("Connecting to Telegram...")
        if not await self.telegram_listener.start():
            logger.error("Failed to connect to Telegram. Exiting.")
            logger.error("Please check:")
            logger.error("1. API_ID and API_HASH in config.py")
            logger.error("2. Phone number is correct")
            logger.error("3. Internet connection is stable")
            self.multi_account_manager.disconnect_all_accounts()
            return False
        logger.info("✅ Telegram connected successfully")
        
        return True
    
    async def run(self):
        """Run the main application loop"""
        try:
            # Initialize components
            if not await self.start():
                return
            
            # Create tasks
            logger.info("Starting background tasks...")
            
            # Break-even monitoring task
            be_task = asyncio.create_task(
                self.multi_account_manager.monitor_and_propagate_break_even(),
                name="break_even_monitor"
            )
            self.tasks.append(be_task)
            
            # Signal listening task (this will block until disconnected)
            listen_task = asyncio.create_task(
                self.telegram_listener.listen_for_signals(),
                name="signal_listener"
            )
            self.tasks.append(listen_task)
            
            logger.info("✅ All systems operational")
            logger.info("=" * 50)
            
            # Wait for tasks
            await asyncio.gather(*self.tasks)
            
        except KeyboardInterrupt:
            logger.info("\n⚠️ Shutdown signal received...")
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up...")
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Disconnect services
        await self.telegram_listener.stop()
        self.multi_account_manager.disconnect_all_accounts()
        
        logger.info("✅ Cleanup complete")
        logger.info("Goodbye!")


async def main():
    """Main entry point"""
    copier = TradingCopier()
    await copier.run()


if __name__ == "__main__":
    try:
        # Run on Windows with proper event loop
        if sys.platform == 'win32':
            # Set console code page to UTF-8
            import os
            os.system('chcp 65001 > nul')
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)