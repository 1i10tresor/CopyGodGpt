#!/usr/bin/env python3
"""
Trading Signal Copier - Main Application
Copies trading signals from Telegram to MetaTrader 5
"""

import asyncio
import logging
import sys
import io
from mt5_manager import MT5Manager
from order_manager import OrderManager
from telegram_listener import TelegramListener
from symbol_mapper import get_broker_symbol
import config
import MetaTrader5 as mt5

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
        self.mt5_manager = MT5Manager(
            login=config.ACCOUNT['login'],
            password=config.ACCOUNT['password'],
            server=config.ACCOUNT['server'],
            broker_name=config.ACCOUNT['broker_name'],
            mt5_path=config.ACCOUNT.get('mt5_path')
        )
        self.order_manager = OrderManager(self.mt5_manager)
        self.telegram_listener = TelegramListener(self.order_manager, config.ACCOUNT)
        self.tasks = []
    
    async def start(self):
        """Initialize and start all components"""
        logger.info("=" * 50)
        logger.info("Starting Trading Signal Copier")
        logger.info("=" * 50)
        
        # Connect to MT5 account
        logger.info(f"Connecting to MetaTrader 5 account {config.ACCOUNT['login']}...")
        if not self.mt5_manager.connect():
            logger.error("Failed to connect to MT5 account. Exiting.")
            logger.error("Please check:")
            logger.error("1. MT5 terminal is installed and running")
            logger.error("2. Login credentials in ACCOUNT config are correct")
            logger.error("3. Server name is correct")
            logger.error("4. Algorithm trading is enabled in MT5")
            return False
        logger.info("✅ MT5 account connected successfully")
        
        # Add traded symbols to Market Watch
        self.add_traded_symbols_to_market_watch()
        
        # Start Telegram client
        logger.info("Connecting to Telegram...")
        if not await self.telegram_listener.start():
            logger.error("Failed to connect to Telegram. Exiting.")
            logger.error("Please check:")
            logger.error("1. API_ID and API_HASH in config.py")
            logger.error("2. Phone number is correct")
            logger.error("3. Internet connection is stable")
            self.mt5_manager.disconnect()
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
                self.monitor_break_even(),
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
        self.mt5_manager.disconnect()
        
        logger.info("✅ Cleanup complete")
        logger.info("Goodbye!")

    def add_traded_symbols_to_market_watch(self):
        """Add all traded symbols to Market Watch"""
        logger.info("Adding traded symbols to Market Watch...")
        
        failed_symbols = 0
        for symbol in config.TRADED_SYMBOLS:
            try:
                # Get broker-specific symbol
                broker_symbol = get_broker_symbol(symbol, config.ACCOUNT['broker_name'], config.SYMBOL_MAPPING)
                
                # Add to Market Watch
                if not mt5.symbol_select(broker_symbol, True):
                    logger.warning(f"Could not add symbol {broker_symbol} (from {symbol}) to Market Watch")
                    failed_symbols += 1
                else:
                    logger.debug(f"Added {symbol} -> {broker_symbol} to Market Watch")
                    
            except Exception as e:
                logger.error(f"Error adding symbol {symbol} -> {broker_symbol if 'broker_symbol' in locals() else 'unknown'}: {e}")
                failed_symbols += 1
        
        if failed_symbols > 0:
            logger.warning(f"Failed to add {failed_symbols} symbols")
        else:
            logger.info("All symbols added successfully")
    
    async def monitor_break_even(self):
        """Monitor break-even and apply modifications"""
        logger.info("Starting break-even monitoring")
        
        try:
            while True:
                # Monitor and apply break-even modifications
                self.order_manager.monitor_and_apply_break_even()
                
                # Wait before next check
                await asyncio.sleep(config.BE_CHECK_INTERVAL)
                
        except asyncio.CancelledError:
            logger.info("Break-even monitoring cancelled")
        except Exception as e:
            logger.error(f"Error in break-even monitoring: {e}", exc_info=True)


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