# multi_account_manager.py
"""Multi-account manager for handling multiple MT5 accounts"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from mt5_manager import MT5Manager
from order_manager import OrderManager
from models import Signal
from symbol_mapper import get_broker_symbol
import config

logger = logging.getLogger(__name__)


class MultiAccountManager:
    """Manages multiple MT5 accounts and coordinates trading operations"""
    
    def __init__(self, accounts_config: List[Dict[str, Any]]):
        self.accounts_config = accounts_config
        self.accounts = {}  # Dict[int, Dict] - login -> {mt5_manager, order_manager, config}
        self.master_account_login = None
        
        # Find master account
        for account_config in accounts_config:
            if account_config.get('is_master', False):
                self.master_account_login = account_config['login']
                break
        
        if self.master_account_login is None:
            logger.warning("No master account specified, using first account as master")
            self.master_account_login = accounts_config[0]['login']
    
    def connect_all_accounts(self) -> bool:
        """Connect to all MT5 accounts"""
        successful_connections = 0
        
        for account_config in self.accounts_config:
            login = account_config['login']
            logger.info(f"Connecting to account {login} ({account_config['broker_name']})...")
            
            # Create MT5 manager
            mt5_manager = MT5Manager(
                login=login,
                password=account_config['password'],
                server=account_config['server'],
                broker_name=account_config['broker_name'],
                mt5_path=account_config.get('mt5_path')
            )
            
            # Connect
            if mt5_manager.connect():
                # Create order manager
                order_manager = OrderManager(mt5_manager)
                
                # Store account info
                self.accounts[login] = {
                    'mt5_manager': mt5_manager,
                    'order_manager': order_manager,
                    'config': account_config
                }
                
                successful_connections += 1
                logger.info(f"✅ Account {login} connected successfully")
            else:
                logger.error(f"❌ Failed to connect to account {login}")
        
        logger.info(f"Connected to {successful_connections}/{len(self.accounts_config)} accounts")
        
        # Add traded symbols to Market Watch after all connections are established
        if successful_connections > 0:
            self.add_traded_symbols_to_market_watch()
        
        return successful_connections > 0
    
    def disconnect_all_accounts(self):
        """Disconnect from all MT5 accounts"""
        for login, account_info in self.accounts.items():
            account_info['mt5_manager'].disconnect()
            logger.info(f"Disconnected from account {login}")
        
        self.accounts.clear()
    
    def add_traded_symbols_to_market_watch(self):
        """Add all traded symbols to Market Watch for all accounts"""
        logger.info("Adding traded symbols to Market Watch for all accounts...")
        
        for login, account_info in self.accounts.items():
            mt5_manager = account_info['mt5_manager']
            broker_name = account_info['config']['broker_name']
            
            logger.info(f"Adding symbols to Market Watch for account {login} ({broker_name})")
            
            failed_symbols = 0
            for symbol in config.TRADED_SYMBOLS:
                try:
                    # Get broker-specific symbol with proper config parameter
                    broker_symbol = get_broker_symbol(symbol, broker_name, config.SYMBOL_MAPPING)
                    
                    # Add to Market Watch
                    import MetaTrader5 as mt5
                    if not mt5.symbol_select(broker_symbol, True):
                        logger.debug(f"Account {login}: Could not add symbol {broker_symbol} to Market Watch")
                        failed_symbols += 1
                    else:
                        logger.debug(f"Account {login}: Added {symbol} -> {broker_symbol} to Market Watch")
                        
                except Exception as e:
                    logger.error(f"Account {login}: Error adding symbol {symbol}: {e}")
                    failed_symbols += 1
            
            if failed_symbols > 0:
                logger.warning(f"Account {login}: Failed to add {failed_symbols} symbols")
            else:
                logger.info(f"Account {login}: All symbols added successfully")
    
    def place_signal_on_all_accounts(self, signal: Signal) -> Dict[str, Any]:
        """
        Place signal orders on all accounts
        
        Returns:
            Dict with 'successful_accounts', 'total_accounts', and 'results'
        """
        results = {}
        successful_accounts = 0
        
        for login, account_info in self.accounts.items():
            try:
                order_manager = account_info['order_manager']
                account_config = account_info['config']
                
                logger.info(f"Placing signal {signal.message_id} on account {login} ({account_config['broker_name']})")
                
                # Place orders
                placed_tickets = order_manager.place_orders(signal, account_config)
                
                results[login] = {
                    'success': len(placed_tickets) > 0,
                    'tickets': placed_tickets,
                    'broker': account_config['broker_name']
                }
                
                if len(placed_tickets) > 0:
                    successful_accounts += 1
                    logger.info(f"✅ Signal {signal.message_id} placed on account {login}: {len(placed_tickets)} orders")
                else:
                    logger.warning(f"⚠️ No orders placed for signal {signal.message_id} on account {login}")
                    
            except Exception as e:
                logger.error(f"❌ Error placing signal {signal.message_id} on account {login}: {e}")
                results[login] = {
                    'success': False,
                    'error': str(e),
                    'broker': account_info['config']['broker_name']
                }
        
        return {
            'successful_accounts': successful_accounts,
            'total_accounts': len(self.accounts),
            'results': results
        }
    
    async def monitor_and_propagate_break_even(self):
        """
        Monitor break-even on master account and propagate to all accounts
        """
        if self.master_account_login not in self.accounts:
            logger.error("Master account not connected, cannot monitor break-even")
            return
        
        master_account = self.accounts[self.master_account_login]
        master_order_manager = master_account['order_manager']
        
        logger.info(f"Starting break-even monitoring on master account {self.master_account_login}")
        
        try:
            while True:
                # Monitor break-even on master account
                modifications_needed = master_order_manager.monitor_break_even()
                
                if modifications_needed:
                    logger.info(f"Found {len(modifications_needed)} break-even modifications needed")
                    
                    # Apply modifications to all accounts
                    for modification in modifications_needed:
                        await self.apply_break_even_to_all_accounts(modification)
                
                # Wait before next check
                await asyncio.sleep(config.BE_CHECK_INTERVAL)
                
        except asyncio.CancelledError:
            logger.info("Break-even monitoring cancelled")
        except Exception as e:
            logger.error(f"Error in break-even monitoring: {e}", exc_info=True)
    
    async def apply_break_even_to_all_accounts(self, modification: Dict[str, Any]):
        """
        Apply break-even modification to all accounts
        
        Args:
            modification: Dict with 'message_id', 'new_sl', 'current_tp', 'position_symbol'
        """
        message_id = modification['message_id']
        new_sl = modification['new_sl']
        
        logger.info(f"Applying break-even for signal {message_id} to all accounts (SL: {new_sl})")
        
        successful_modifications = 0
        
        for login, account_info in self.accounts.items():
            try:
                mt5_manager = account_info['mt5_manager']
                
                # Find positions with matching message ID
                import MetaTrader5 as mt5
                positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
                
                if positions:
                    for position in positions:
                        if position.comment and position.comment.startswith(str(message_id)):
                            # Apply break-even modification
                            success = mt5_manager.modify_sl_for_position(
                                ticket=position.ticket,
                                new_sl=new_sl,
                                current_tp=position.tp
                            )
                            
                            if success:
                                successful_modifications += 1
                                logger.info(f"✅ Break-even applied to position {position.ticket} on account {login}")
                            else:
                                logger.error(f"❌ Failed to apply break-even to position {position.ticket} on account {login}")
                            
            except Exception as e:
                logger.error(f"Error applying break-even to account {login}: {e}")
        
        if successful_modifications > 0:
            logger.info(f"✅ Break-even applied to {successful_modifications} positions across all accounts")
        else:
            logger.warning(f"⚠️ No break-even modifications applied for signal {message_id}")