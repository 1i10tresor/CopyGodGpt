# mt5_manager.py
"""MetaTrader 5 connection and trading operations"""

import logging
import MetaTrader5 as mt5
from typing import Tuple, Optional
from datetime import datetime
from symbol_mapper import get_broker_symbol
import config

logger = logging.getLogger(__name__)


class MT5Manager:
    """Manages MetaTrader 5 connection and operations"""
    
    def __init__(self, login: int, password: str, server: str, broker_name: str, mt5_path: Optional[str] = None):
        self.login = login
        self.password = password
        self.server = server
        self.broker_name = broker_name
        self.mt5_path = mt5_path
        self.connected = False
        self.calculated_time_offset_minutes = 0
    
    def connect(self) -> bool:
        """Connect to MetaTrader 5"""
        try:
            # Initialize MT5 - use path if provided
            if self.mt5_path:
                init_result = mt5.initialize(self.mt5_path)
                logger.info(f"Initializing MT5 with path: {self.mt5_path}")
            else:
                init_result = mt5.initialize()
                logger.info("Initializing MT5 with default path")
            
            if not init_result:
                error = mt5.last_error()
                logger.error(f"MT5 initialization failed: {error}")
                return False
            
            # Login to account
            if not mt5.login(self.login, password=self.password, server=self.server):
                error = mt5.last_error()
                logger.error(f"MT5 login failed: {error}")
                mt5.shutdown()
                return False
            
            # Verify connection
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("Failed to get account info")
                mt5.shutdown()
                return False
            
            self.connected = True
            logger.info(f"Successfully connected to MT5 - Account: {account_info.login}, Server: {account_info.server}")
            
            return True
            
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False
    
    def get_server_time_utc(self) -> Optional[datetime]:
        """Get MT5 server time in UTC"""
        try:
            # Get broker-specific XAUUSD symbol
            broker_symbol = get_broker_symbol("XAUUSD", self.broker_name, config.SYMBOL_MAPPING)
            logger.debug(f"Using symbol {broker_symbol} to get server time")
            
            # Ensure symbol is in Market Watch
            if not mt5.symbol_select(broker_symbol, True):
                logger.warning(f"Could not add {broker_symbol} to Market Watch for time sync")
                return None
            
            # Get tick data which contains server timestamp
            tick = mt5.symbol_info_tick(broker_symbol)
            if tick is None:
                logger.error(f"Failed to get tick data for {broker_symbol}")
                return None
            
            # Get server time from tick timestamp (this is in UTC)
            server_time_timestamp = tick.time
            server_time_utc = datetime.utcfromtimestamp(server_time_timestamp)
            
            logger.debug(f"MT5 server time (UTC): {server_time_utc}")
            return server_time_utc
            
        except Exception as e:
            logger.error(f"Error getting MT5 server time: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from MetaTrader 5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")
            
    
    def get_symbol_info(self, symbol: str):
        """Get symbol information"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Failed to get symbol info for {symbol} - symbol may not exist or not be available")
            return symbol_info
        except Exception as e:
            logger.error(f"Error getting symbol info: {e}")
            return None
    
    def get_market_price(self, symbol: str, direction: int) -> Optional[float]:
        """Get current market price (ask for buy, bid for sell)"""
        try:
            logger.debug(f"Selecting symbol {symbol} for market watch")
            # Ensure symbol is in Market Watch
            if not mt5.symbol_select(symbol, True):
                error = mt5.last_error()
                logger.error(f"Could not add symbol {symbol} to Market Watch - MT5 Error: {error}")
                return None
            
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.error(f"Failed to get tick data for {symbol} - no price information available")
                return None
            
            # Return ask for buy (direction 0), bid for sell (direction 1)
            if direction == 0:  # Buy
                price = tick.ask
            else:  # Sell
                price = tick.bid
            
            if price == 0.0:
                logger.warning(f"Price is 0.0 for {symbol} - tick data: ask={tick.ask}, bid={tick.bid}, time={tick.time}")
                return None
            
            return price
                
        except Exception as e:
            logger.error(f"Error getting market price for {symbol}: {e}")
            return None
    
    def modify_sl_for_position(self, ticket: int, new_sl: float, current_tp: float) -> bool:
        """
        Modify stop loss for a specific position
        
        Args:
            ticket: Position ticket number
            new_sl: New stop loss value
            current_tp: Current take profit value
            
        Returns:
            True if modification successful, False otherwise
        """
        try:
            logger.debug(f"Modifying SL for position {ticket}: new_sl={new_sl}, current_tp={current_tp}")
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": new_sl,
                "tp": current_tp,
            }
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ SL modified for position {ticket} - New SL: {new_sl}")
                return True
            elif result:
                error_msg = f"Failed to modify SL for position {ticket}: {result.retcode}"
                if hasattr(result, 'comment') and result.comment:
                    error_msg += f" - {result.comment}"
                logger.error(error_msg)
                return False
            else:
                logger.error(f"Failed to modify SL for position {ticket}: No result returned")
                return False
                
        except Exception as e:
            logger.error(f"Exception modifying SL for position {ticket}: {e}")
            return False