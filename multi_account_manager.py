"""
Multi-account manager for copy trading
"""

import logging
import asyncio
import multiprocessing as mp
from typing import List, Dict, Any, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import MetaTrader5 as mt5

from mt5_manager import MT5Manager
from order_manager import OrderManager
from models import Signal
from symbol_mapper import get_broker_symbol
import config

logger = logging.getLogger(__name__)


def place_orders_worker(signal_data: Dict, account_config: Dict) -> Dict[str, Any]:
    """
    Worker function for placing orders in a separate process
    
    Args:
        signal_data: Serialized signal data
        account_config: Account configuration
        
    Returns:
        Result dictionary with success status and details
    """
    try:
        # Recreate Signal object from data
        signal = Signal(
            direction=signal_data['direction'],
            entry=signal_data['entry'],
            sl=signal_data['sl'],
            tps=signal_data['tps'],
            message_id=signal_data['message_id'],
            author=signal_data['author'],
            symbol=signal_data['symbol']
        )
        
        # Create MT5Manager and OrderManager for this process
        mt5_manager = MT5Manager(
            login=account_config['login'],
            password=account_config['password'],
            server=account_config['server'],
            broker_name=account_config['broker_name'],
            mt5_path=account_config['mt5_path']
        )
        
        # Connect to MT5
        if not mt5_manager.connect():
            return {
                'success': False,
                'account': account_config['login'],
                'broker': account_config['broker_name'],
                'error': 'Failed to connect to MT5',
                'tickets': []
            }
        
        # Create order manager and place orders
        order_manager = OrderManager(mt5_manager)
        tickets = order_manager.place_orders(signal, account_config)
        
        # Disconnect
        mt5_manager.disconnect()
        
        return {
            'success': True,
            'account': account_config['login'],
            'broker': account_config['broker_name'],
            'tickets': tickets,
            'orders_placed': len(tickets)
        }
        
    except Exception as e:
        logger.error(f"Error in place_orders_worker for account {account_config.get('login', 'unknown')}: {e}")
        return {
            'success': False,
            'account': account_config.get('login', 'unknown'),
            'broker': account_config.get('broker_name', 'unknown'),
            'error': str(e),
            'tickets': []
        }


class MultiAccountManager:
    """Manages multiple MT5 accounts for copy trading"""
    
    def __init__(self, accounts_config: List[Dict[str, Any]]):
        self.accounts_config = accounts_config
        self.mt5_managers = {}
        self.order_managers = {}
        self.master_account = None
        
        # Initialize managers for each account
        for account in accounts_config:
            login = account['login']
            
            # Create MT5Manager
            mt5_manager = MT5Manager(
                login=account['login'],
                password=account['password'],
                server=account['server'],
                broker_name=account['broker_name'],
                mt5_path=account['mt5_path']
            )
            
            # Create OrderManager
            order_manager = OrderManager(mt5_manager)
            
            self.mt5_managers[login] = mt5_manager
            self.order_managers[login] = order_manager
            
            # Identify master account
            if account.get('is_master', False):
                if self.master_account is not None:
                    logger.warning(f"Multiple master accounts found. Using account {login} as master.")
                self.master_account = login
        
        if self.master_account is None:
            logger.error("No master account found in configuration!")
        else:
            logger.info(f"Master account set to: {self.master_account}")
    
    def add_traded_symbols_to_market_watch(self):
        """Add all traded symbols to Market Watch for each connected account"""
        logger.info("Adding traded symbols to Market Watch for all accounts...")
        
        for login, mt5_manager in self.mt5_managers.items():
            if not mt5_manager.connected:
                logger.debug(f"Account {login} not connected, skipping Market Watch update")
                continue
            
            broker_name = None
            for account in self.accounts_config:
                if account['login'] == login:
                    broker_name = account.get('broker_name', 'unknown')
                    break
            
            logger.info(f"Adding symbols to Market Watch for account {login} ({broker_name})")
            
            symbols_added = 0
            symbols_failed = 0
            
            for symbol in config.TRADED_SYMBOLS:
                try:
                    # Get broker-specific symbol name
                    broker_symbol = get_broker_symbol(symbol, broker_name)
                    
                    # Check if symbol exists
                    symbol_info = mt5.symbol_info(broker_symbol)
                    
                    if symbol_info is None:
                        logger.debug(f"Account {login}: Symbol {broker_symbol} not found")
                        symbols_failed += 1
                        continue
                    
                    # Add to Market Watch if not visible
                    if not symbol_info.visible:
                        if mt5.symbol_select(broker_symbol, True):
                            logger.debug(f"Account {login}: Added {broker_symbol} to Market Watch")
                            symbols_added += 1
                        else:
                            logger.warning(f"Account {login}: Failed to add {broker_symbol} to Market Watch")
                            symbols_failed += 1
                    else:
                        logger.debug(f"Account {login}: {broker_symbol} already in Market Watch")
                        
                except Exception as e:
                    logger.error(f"Account {login}: Error adding symbol {symbol}: {e}")
                    symbols_failed += 1
            
            if symbols_added > 0:
                logger.info(f"Account {login}: Added {symbols_added} symbols to Market Watch")
            if symbols_failed > 0:
                logger.warning(f"Account {login}: Failed to add {symbols_failed} symbols")
    
    def connect_all_accounts(self) -> bool:
        """Connect to all MT5 accounts"""
        success_count = 0
        
        for login, mt5_manager in self.mt5_managers.items():
            logger.info(f"Connecting to account {login}...")
            if mt5_manager.connect():
                logger.info(f"✅ Account {login} connected successfully")
                success_count += 1
            else:
                logger.error(f"❌ Failed to connect to account {login}")
        
        logger.info(f"Connected to {success_count}/{len(self.mt5_managers)} accounts")
        
        # Add traded symbols to Market Watch after all connections are established
        self.add_traded_symbols_to_market_watch()
        
        # Add traded symbols to Market Watch after all connections are established
        self.add_traded_symbols_to_market_watch()
        
        return success_count > 0
    
    def disconnect_all_accounts(self):
        """Disconnect from all MT5 accounts"""
        for login, mt5_manager in self.mt5_managers.items():
            logger.info(f"Disconnecting from account {login}...")
            mt5_manager.disconnect()
        logger.info("All accounts disconnected")
    
    def place_signal_on_all_accounts(self, signal: Signal) -> Dict[str, Any]:
        """
        Place signal on all accounts using multiprocessing
        
        Args:
            signal: The trading signal to place
            
        Returns:
            Summary of results from all accounts
        """
        logger.info(f"Placing signal {signal.message_id} on all accounts...")
        
        # Serialize signal data for multiprocessing
        signal_data = {
            'direction': signal.direction,
            'entry': signal.entry,
            'sl': signal.sl,
            'tps': signal.tps,
            'message_id': signal.message_id,
            'author': signal.author,
            'symbol': signal.symbol
        }
        
        results = []
        
        # Use ProcessPoolExecutor for parallel execution
        with ProcessPoolExecutor(max_workers=len(self.accounts_config)) as executor:
            # Submit tasks
            future_to_account = {}
            for account_config in self.accounts_config:
                future = executor.submit(place_orders_worker, signal_data, account_config)
                future_to_account[future] = account_config['login']
            
            # Collect results
            for future in as_completed(future_to_account):
                account_login = future_to_account[future]
                try:
                    result = future.result(timeout=30)  # 30 second timeout
                    results.append(result)
                    
                    if result['success']:
                        logger.info(f"✅ Account {account_login}: {result['orders_placed']} orders placed")
                    else:
                        logger.error(f"❌ Account {account_login}: {result['error']}")
                        
                except Exception as e:
                    logger.error(f"❌ Account {account_login}: Exception occurred - {e}")
                    results.append({
                        'success': False,
                        'account': account_login,
                        'error': str(e),
                        'tickets': []
                    })
        
        # Summary
        successful_accounts = sum(1 for r in results if r['success'])
        total_orders = sum(r['orders_placed'] for r in results if r['success'])
        
        logger.info(f"Signal {signal.message_id} placement summary: "
                   f"{successful_accounts}/{len(self.accounts_config)} accounts successful, "
                   f"{total_orders} total orders placed")
        
        return {
            'signal_id': signal.message_id,
            'successful_accounts': successful_accounts,
            'total_accounts': len(self.accounts_config),
            'total_orders': total_orders,
            'results': results
        }
    
    async def monitor_and_propagate_break_even(self):
        """Monitor master account for break-even and propagate to slave accounts"""
        if self.master_account is None:
            logger.error("No master account configured for break-even monitoring")
            return
        
        logger.info(f"Starting break-even monitoring on master account {self.master_account}")
        
        master_order_manager = self.order_managers[self.master_account]
        
        while True:
            try:
                logger.debug(f"Checking break-even on master account {self.master_account}...")
                # Check for break-even modifications needed on master account
                modifications = master_order_manager.monitor_break_even()
                
                if modifications:
                    logger.info(f"Break-even triggered for {len(modifications)} positions on master account")
                    
                    for mod in modifications:
                        logger.info(f"Processing break-even for position {mod['ticket']} (signal {mod['message_id']})")
                        
                        # Apply break-even on master account
                        master_mt5 = self.mt5_managers[self.master_account]
                        success = master_mt5.modify_sl_for_position(
                            mod['ticket'], 
                            mod['new_sl'], 
                            mod['current_tp']
                        )
                        
                        if success:
                            logger.info(f"✅ Break-even applied on master account for position {mod['ticket']}")
                            
                            # Propagate to slave accounts
                            await self._propagate_break_even_to_slaves(mod)
                        else:
                            logger.error(f"❌ Failed to apply break-even on master account for position {mod['ticket']}")
                else:
                    logger.debug("No break-even modifications needed on master account")
                
            except Exception as e:
                logger.error(f"Error in break-even monitoring: {e}", exc_info=True)
            
            await asyncio.sleep(config.BE_CHECK_INTERVAL)
    
    async def _propagate_break_even_to_slaves(self, modification: Dict[str, Any]):
        """
        Propagate break-even modification to all slave accounts
        
        Args:
            modification: Break-even modification details from master account
        """
        message_id = modification['message_id']
        new_sl = modification['new_sl']
        
        logger.info(f"Propagating break-even for signal {message_id} to slave accounts...")
        logger.debug(f"Break-even details: message_id={message_id}, new_sl={new_sl}")
        
        # Iterate through all slave accounts
        for account_config in self.accounts_config:
            if account_config['login'] == self.master_account:
                logger.debug(f"Skipping master account {account_config['login']}")
                continue  # Skip master account
            
            try:
                login = account_config['login']
                logger.info(f"Processing break-even propagation for slave account {login} ({account_config['broker_name']})")
                
                mt5_manager = self.mt5_managers[login]
                broker_name = account_config['broker_name']
                
                # Check if MT5 manager is connected
                if not mt5_manager.connected:
                    logger.error(f"Account {login} is not connected to MT5, skipping break-even propagation")
                    continue
                
                # Find positions with matching criteria
                positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
                if positions is None:
                    logger.warning(f"Account {login}: positions_get returned None")
                    continue
                elif len(positions) == 0:
                    logger.debug(f"Account {login}: No positions found with magic number {config.MAGIC_NUMBER}")
                    continue
                
                logger.debug(f"Account {login}: Found {len(positions)} positions to check")
                
                # Track positions found for this signal
                positions_found = 0
                positions_modified = 0
                
                for position in positions:
                    logger.debug(f"Account {login}: Checking position {position.ticket} - Comment: '{position.comment}'")
                    
                    if not position.comment:
                        logger.debug(f"Account {login}: Position {position.ticket} has no comment, skipping")
                        continue
                    
                    # Parse comment to match signal
                    parts = position.comment.split('/')
                    if len(parts) < 2:
                        logger.debug(f"Account {login}: Position {position.ticket} comment format invalid: '{position.comment}'")
                        continue
                    
                    try:
                        pos_message_id = int(parts[0])
                    except ValueError:
                        logger.debug(f"Account {login}: Position {position.ticket} could not parse message ID from comment: '{position.comment}'")
                        continue
                    
                    # Check if this position matches our signal (by message ID only)
                    if pos_message_id == message_id:
                        positions_found += 1
                        logger.info(f"Account {login}: Found matching position {position.ticket} for signal {message_id}")
                        
                        # Check if position still exists (avoid 10036 error)
                        current_positions = mt5.positions_get(ticket=position.ticket)
                        if not current_positions:
                            logger.warning(f"Position {position.ticket} no longer exists on account {login}, skipping")
                            continue
                        
                        current_position = current_positions[0]
                        logger.debug(f"Account {login}: Position {position.ticket} current SL: {current_position.sl}, target SL: {new_sl}")
                        
                        # Get symbol info for minimum change calculation
                        symbol_info = mt5_manager.get_symbol_info(position.symbol)
                        if symbol_info is None:
                            logger.warning(f"Could not get symbol info for {position.symbol} on account {login}, skipping")
                            continue
                        
                        # Calculate minimum SL change threshold
                        min_sl_change = max(symbol_info.point * 2, symbol_info.trade_tick_size)
                        sl_change_amount = abs(current_position.sl - new_sl)
                        logger.debug(f"Account {login}: Position {position.ticket} - SL change amount: {sl_change_amount:.5f}, min required: {min_sl_change:.5f}")
                        
                        # Check if SL change is significant enough (avoid 10025 error)
                        if sl_change_amount <= min_sl_change:
                            logger.debug(f"Position {position.ticket} on account {login}: SL already at target level, skipping")
                            continue
                        
                        # Round new_sl to symbol precision
                        rounded_new_sl = round(new_sl, symbol_info.digits)
                        logger.debug(f"Account {login}: Position {position.ticket} - Rounded new SL: {rounded_new_sl}")
                        
                        # Apply break-even modification
                        success = mt5_manager.modify_sl_for_position(
                            position.ticket,
                            rounded_new_sl,
                            current_position.tp
                        )
                        
                        if success:
                            logger.info(f"✅ Break-even propagated to account {login}, position {position.ticket}")
                            positions_modified += 1
                        else:
                            logger.error(f"❌ Failed to propagate break-even to account {login}, position {position.ticket}")
                    else:
                        logger.debug(f"Account {login}: Position {position.ticket} message ID {pos_message_id} doesn't match target {message_id}")
                
                if positions_found == 0:
                    logger.warning(f"No positions found for signal {message_id} on account {login}")
                else:
                    logger.info(f"Account {login}: Found {positions_found} positions for signal {message_id}, modified {positions_modified}")
                        
            except Exception as e:
                logger.error(f"Error propagating break-even to account {account_config['login']}: {e}")
        
        logger.info(f"Break-even propagation completed for signal {message_id}")