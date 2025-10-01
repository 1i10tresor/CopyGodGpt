# order_manager.py
"""Order placement and management for trading signals"""

import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import List, Dict, Any
from models import Signal
from symbol_mapper import get_broker_symbol
import config

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages order placement and monitoring"""
    
    def __init__(self, mt5_manager):
        self.mt5 = mt5_manager
    
    def determine_order_type_and_price(self, signal: Signal, current_price: float) -> tuple:
        """
        Determine order type and price based on signal and current market price
        
        Returns:
            tuple: (order_type, price)
        """
        entry = signal.entry
        sl = signal.sl
        direction = signal.direction
        
        # Calculate tolerance based on entry price
        tolerance = entry * config.MARKET_ORDER_TOLERANCE_FACTOR
        
        logger.debug(f"Price analysis - Entry: {entry}, Current: {current_price}, SL: {sl}, Tolerance: {tolerance:.2f}")
        
        if direction == 0:  # BUY
            if current_price <= sl:
                logger.info(f"BUY signal cancelled - Current price {current_price} <= SL {sl}")
                return None, None
            elif sl < current_price < entry + tolerance:
                logger.info(f"BUY market order - Price {current_price} in range ({sl}, {entry + tolerance})")
                return mt5.ORDER_TYPE_BUY, current_price
            elif current_price >= entry + tolerance:
                logger.info(f"BUY limit order - Price {current_price} >= {entry + tolerance}")
                return mt5.ORDER_TYPE_BUY_LIMIT, entry
            else:
                logger.warning(f"BUY signal - Unexpected price condition")
                return None, None
        
        else:  # SELL
            if current_price >= sl:
                logger.info(f"SELL signal cancelled - Current price {current_price} >= SL {sl}")
                return None, None
            elif entry - tolerance < current_price < sl:
                logger.info(f"SELL market order - Price {current_price} in range ({entry - tolerance}, {sl})")
                return mt5.ORDER_TYPE_SELL, current_price
            elif current_price <= entry - tolerance:
                logger.info(f"SELL limit order - Price {current_price} <= {entry - tolerance}")
                return mt5.ORDER_TYPE_SELL_LIMIT, entry
            else:
                logger.warning(f"SELL signal - Unexpected price condition")
                return None, None
    
    def place_orders(self, signal: Signal, account_config: Dict[str, Any]) -> List[int]:
        """
        Place orders for a trading signal
        
        Args:
            signal: The trading signal
            account_config: Account configuration
            
        Returns:
            List of placed order tickets
        """
        logger.info(f"Processing signal {signal.message_id} for {account_config['broker_name']}")
        
        # Get broker-specific symbol
        broker_symbol = get_broker_symbol(signal.symbol, account_config['broker_name'], config.SYMBOL_MAPPING)
        logger.info(f"Symbol mapping: {signal.symbol} -> {broker_symbol}")
        
        # Get symbol info
        symbol_info = self.mt5.get_symbol_info(broker_symbol)
        if symbol_info is None:
            logger.error(f"Symbol {broker_symbol} not found or not available")
            return []
        
        # Get current market price
        current_price = self.mt5.get_market_price(broker_symbol, signal.direction)
        if current_price is None:
            logger.error(f"Could not get current price for {broker_symbol}")
            return []
        
        logger.info(f"Current market price for {broker_symbol}: {current_price}")
        
        # Determine order type and price
        order_type, price = self.determine_order_type_and_price(signal, current_price)
        if order_type is None:
            logger.warning(f"Signal {signal.message_id} cancelled or invalid")
            return []
        
        # Get symbol precision for rounding
        digits = symbol_info.digits
        rounded_sl = round(signal.sl, digits)
        
        placed_tickets = []
        
        # Get TP1 value for comment (first non-"open" TP)
        tp1_value = None
        for tp in signal.tps:
            if tp != "open":
                tp1_value = tp
                break
        
        # Fallback if no valid TP found
        if tp1_value is None:
            tp1_value = signal.entry + 2 if signal.direction == 0 else signal.entry - 2
        
        # Place an order for each TP
        for i, tp in enumerate(signal.tps, 1):
            # Skip "open" TPs for now
            if tp == "open":
                logger.info(f"Skipping 'open' TP{i} for signal {signal.message_id}")
                continue
            
            # Round TP to symbol precision
            rounded_tp = round(tp, digits)
            
            # Format comment: MessageID/TP1_value (shortened for 16 char limit)
            comment = f"{signal.message_id}/{tp1_value}"
            
            # Prepare order request
            request = {
                "action": mt5.TRADE_ACTION_DEAL if order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL] else mt5.TRADE_ACTION_PENDING,
                "symbol": broker_symbol,
                "volume": account_config['lot_size'],
                "type": order_type,
                "sl": rounded_sl,
                "tp": rounded_tp,
                "deviation": config.MAX_SLIPPAGE,
                "magic": config.MAGIC_NUMBER,
                "comment": comment,
            }
            
            # Add price and expiration for pending orders
            if order_type not in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
                request["price"] = round(price, digits)
                
                # Add expiration for pending orders only
                if signal.expiration_minutes:
                    # Get current server time and add expiration duration
                    server_time = self.mt5.get_server_time_utc()
                    if server_time is None:
                        logger.error("Could not get MT5 server time for expiration calculation")
                        # Fallback: use system time with offset
                        base_expiration_minutes = signal.expiration_minutes
                        total_expiration_minutes = base_expiration_minutes + self.mt5.calculated_time_offset_minutes
                        expiration_time = datetime.utcnow() + timedelta(minutes=total_expiration_minutes, seconds=10)
                        logger.warning(f"Using fallback expiration calculation: {expiration_time} UTC")
                    else:
                        # Calculate expiration based on server time
                        expiration_time = server_time + timedelta(minutes=signal.expiration_minutes, seconds=10)
                        logger.info(f"Expiration calculated from server time: Server={server_time}, Expiration={expiration_time} UTC ({signal.expiration_minutes}min + 10s buffer)")
                    
                    request["expiration"] = int(expiration_time.timestamp())
                    request["type_time"] = mt5.ORDER_TIME_SPECIFIED
                else:
                    # Fallback to default expiration time if not specified
                    server_time = self.mt5.get_server_time_utc()
                    if server_time is None:
                        logger.error("Could not get MT5 server time for default expiration calculation")
                        # Fallback: use system time with offset
                        base_expiration_minutes = config.EXPIRATION_TIMES["DEFAULT"]
                        total_expiration_minutes = base_expiration_minutes + self.mt5.calculated_time_offset_minutes
                        expiration_time = datetime.utcnow() + timedelta(minutes=total_expiration_minutes, seconds=10)
                        logger.warning(f"Using fallback default expiration calculation: {expiration_time} UTC")
                    else:
                        # Calculate expiration based on server time
                        default_minutes = config.EXPIRATION_TIMES["DEFAULT"]
                        expiration_time = server_time + timedelta(minutes=default_minutes, seconds=10)
                        logger.info(f"Default expiration calculated from server time: Server={server_time}, Expiration={expiration_time} UTC ({default_minutes}min + 10s buffer)")
                    
                    request["expiration"] = int(expiration_time.timestamp())
                    request["type_time"] = mt5.ORDER_TIME_SPECIFIED
            else:
                # Market orders don't need expiration
                request["type_time"] = mt5.ORDER_TIME_GTC
            
            # For market orders, we need to specify the filling type
            if order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
                request["type_filling"] = mt5.ORDER_FILLING_IOC
            else:
                request["type_filling"] = mt5.ORDER_FILLING_RETURN
            
            # Send order
            try:
                logger.info(f"Sending order request for TP{i}: {request}")
                result = mt5.order_send(request)
                
                if result is None:
                    logger.error(f"Order send returned None for TP{i}")
                    continue
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"✅ Order placed: TP{i}, ticket {result.order}, comment: {comment}")
                    placed_tickets.append(result.order)
                else:
                    error_msg = f"❌ Failed TP{i}: Code {result.retcode}"
                    if hasattr(result, 'comment') and result.comment:
                        error_msg += f" - {result.comment}"
                    logger.error(error_msg)
                    
            except Exception as e:
                logger.error(f"Exception placing TP{i}: {e}", exc_info=True)
                continue
        
        if placed_tickets:
            logger.info(f"Summary: {len(placed_tickets)} orders placed for signal {signal.message_id} on {account_config['broker_name']}")
        else:
            logger.warning(f"No orders placed for signal {signal.message_id} on {account_config['broker_name']}")
        
        return placed_tickets
    
    def monitor_and_apply_break_even(self):
        """
        Monitor positions for break-even modification and apply them directly
        """
        logger.debug("Starting break-even monitoring check...")
        
        try:
            # Get all positions with our magic number
            positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
            
            if positions is None:
                logger.debug("No positions found (positions_get returned None)")
                return
            
            logger.debug(f"Found {len(positions)} positions with magic number {config.MAGIC_NUMBER}")
            
            if positions:
                for position in positions:
                    logger.debug(f"Processing position {position.ticket} - Symbol: {position.symbol}, Comment: '{position.comment}', Type: {position.type}")
                    
                    # Parse comment to get TP1 value, direction, and original symbol
                    try:
                        if not position.comment:
                            logger.debug(f"Position {position.ticket}: No comment found, skipping")
                            continue
                            
                        parts = position.comment.split('/')
                        if len(parts) < 2:
                            logger.debug(f"Position {position.ticket}: Comment format invalid ('{position.comment}'), expected 'messageId/tp1Value'")
                            continue
                            
                        message_id = int(parts[0])
                        tp1_value = float(parts[1])
                        direction = position.type  # Get direction from position type (0=BUY, 1=SELL)
                        
                        logger.debug(f"Position {position.ticket}: Parsed - MessageID: {message_id}, TP1: {tp1_value}, Direction: {'BUY' if direction == 0 else 'SELL'}")
                        
                        # Get current price for the position's symbol
                        current_price = self.mt5.get_market_price(position.symbol, direction)
                        if current_price is None:
                            logger.warning(f"Position {position.ticket}: Could not get current price for symbol {position.symbol}")
                            continue
                        
                        logger.debug(f"Position {position.ticket}: Current price: {current_price}, Entry price: {position.price_open}, Current SL: {position.sl}")
                        
                        # Check if TP1 reached
                        tp1_reached = False
                        entry_price = position.price_open
                        
                        if direction == 0:  # Buy
                            if current_price >= tp1_value:
                                tp1_reached = True
                                logger.debug(f"Buy position {position.ticket}: TP1 REACHED - Current {current_price:.2f} >= TP1 {tp1_value:.2f}")
                            else:
                                logger.debug(f"Buy position {position.ticket}: TP1 NOT reached - Current {current_price:.2f} < TP1 {tp1_value:.2f}")
                        else:  # Sell
                            if current_price <= tp1_value:
                                tp1_reached = True
                                logger.debug(f"Sell position {position.ticket}: TP1 REACHED - Current {current_price:.2f} <= TP1 {tp1_value:.2f}")
                            else:
                                logger.debug(f"Sell position {position.ticket}: TP1 NOT reached - Current {current_price:.2f} > TP1 {tp1_value:.2f}")
                        
                        # Add to modifications if TP1 reached and SL not already at BE
                        sl_distance_from_entry = abs(position.sl - entry_price)
                        logger.debug(f"Position {position.ticket}: SL distance from entry: {sl_distance_from_entry:.2f}")
                        
                        if tp1_reached and sl_distance_from_entry > 0.5:
                            new_sl = entry_price + config.BE_OFFSET
                            logger.info(f"Position {position.ticket}: BREAK-EVEN NEEDED - New SL will be {new_sl:.2f} (entry: {entry_price:.2f}, offset: {config.BE_OFFSET})")
                            
                            # Apply break-even modification directly
                            success = self.mt5.modify_sl_for_position(
                                ticket=position.ticket,
                                new_sl=new_sl,
                                current_tp=position.tp
                            )
                            
                            if success:
                                logger.info(f"✅ Break-even applied to position {position.ticket}")
                            else:
                                logger.error(f"❌ Failed to apply break-even to position {position.ticket}")
                        elif tp1_reached:
                            logger.debug(f"Position {position.ticket}: TP1 reached but SL already at break-even (distance: {sl_distance_from_entry:.2f})")
                        else:
                            logger.debug(f"Position {position.ticket}: No break-even action needed")
                            
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Position {position.ticket}: Could not parse comment '{position.comment}': {e}")
                    except Exception as e:
                        logger.error(f"Error processing position {position.ticket}: {e}")
            else:
                logger.debug("No positions found with our magic number")
        
        except Exception as e:
            logger.error(f"Break-even monitor error: {e}", exc_info=True)