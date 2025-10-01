# order_manager.py
"""Order management and execution logic"""

import logging
import MetaTrader5 as mt5
import asyncio
from typing import List, Tuple, Optional, Dict, Any
from models import Signal
from mt5_manager import MT5Manager
from symbol_mapper import get_broker_symbol
import config

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages order placement and monitoring"""
    
    def __init__(self, mt5_manager: MT5Manager):
        self.mt5 = mt5_manager
    
    def determine_order_type(self, signal: Signal, broker_name: str) -> Tuple[Optional[int], float]:
        """
        Determine order type based on current market price
        
        Market order tolerance = current_price * 0.00019444
        
        For BUY (direction=0):
        - Price <= SL: Cancel order
        - SL < Price < Entry + tolerance: Market order
        - Price >= Entry + tolerance: Buy Limit (pending)
        
        For SELL (direction=1):
        - Price >= SL: Cancel order
        - Entry - tolerance < Price < SL: Market order
        - Price <= Entry - tolerance: Sell Limit (pending)
        """
        # Get broker-specific symbol
        broker_symbol = get_broker_symbol(signal.symbol, broker_name, config.SYMBOL_MAPPING)
        
        # Ensure symbol is in Market Watch before getting price
        if not mt5.symbol_select(broker_symbol, True):
            logger.error(f"Could not add symbol {broker_symbol} to Market Watch")
            return None, None
        
        current_price = self.mt5.get_market_price(broker_symbol, signal.direction)
        if current_price is None:
            return None, None
        
        # Calculate dynamic tolerance based on current price
        tolerance = current_price * config.MARKET_ORDER_TOLERANCE_FACTOR
        logger.debug(f"Market order tolerance for price {current_price:.2f}: {tolerance:.2f}")
        
        if signal.direction == 0:  # Buy
            if current_price <= signal.sl:
                logger.info(f"Buy: Price {current_price:.2f} <= SL {signal.sl:.2f}, cancelling order")
                return None, None
            elif signal.sl < current_price < signal.entry + tolerance:
                logger.info(f"Buy: Market order (price {current_price:.2f}, entry {signal.entry:.2f}, tolerance {tolerance:.2f})")
                return mt5.ORDER_TYPE_BUY, 0
            else:  # current_price >= signal.entry + tolerance
                logger.info(f"Buy: Limit order (price {current_price:.2f} >= {signal.entry + tolerance:.2f})")
                return mt5.ORDER_TYPE_BUY_LIMIT, signal.entry
        
        else:  # Sell
            if current_price >= signal.sl:
                logger.info(f"Sell: Price {current_price:.2f} >= SL {signal.sl:.2f}, cancelling order")
                return None, None
            elif signal.entry - tolerance < current_price < signal.sl:
                logger.info(f"Sell: Market order (price {current_price:.2f}, entry {signal.entry:.2f}, tolerance {tolerance:.2f})")
                return mt5.ORDER_TYPE_SELL, 0
            else:  # current_price <= signal.entry - tolerance
                logger.info(f"Sell: Limit order (price {current_price:.2f} <= {signal.entry - tolerance:.2f})")
                return mt5.ORDER_TYPE_SELL_LIMIT, signal.entry
    
    def place_orders(self, signal: Signal, account_config: Dict[str, Any]) -> List[int]:
        """
        Place orders for a signal on a specific account
        
        Args:
            signal: The trading signal
            account_config: Account configuration containing lot_size and broker_name
        """
        # Determine order type
        order_type, price = self.determine_order_type(signal, account_config['broker_name'])
        if order_type is None:
            logger.info(f"Order cancelled for signal {signal.message_id}")
            return []
        
        # Get broker-specific symbol
        broker_symbol = get_broker_symbol(signal.symbol, account_config['broker_name'], config.SYMBOL_MAPPING)
        
        # Ensure symbol is in Market Watch (this also makes it visible)
        if not mt5.symbol_select(broker_symbol, True):
            logger.error(f"Could not add symbol {broker_symbol} to Market Watch")
            return []
        
        # Get symbol info for broker-specific symbol
        symbol_info = self.mt5.get_symbol_info(broker_symbol)
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {broker_symbol}")
            return []
        
        # Verify symbol is now visible for trading
        if not symbol_info.visible:
            logger.error(f"Symbol {broker_symbol} is still not visible after adding to Market Watch")
            return []
        
        # Round prices to symbol precision
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
            comment = f"{signal.message_id}/{int(tp1_value)}"
            
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
                "type_time": mt5.ORDER_TIME_GTC,
            }
            
            # Add price for pending orders
            if order_type not in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
                request["price"] = round(price, digits)
            
            # For market orders, we need to specify the filling type
            if order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
                request["type_filling"] = mt5.ORDER_FILLING_IOC
            else:
                request["type_filling"] = mt5.ORDER_FILLING_RETURN
            
            # Send order
            try:
                logger.debug(f"Sending order request for TP{i}: {request}")
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
                                logger.info(f"Buy position {position.ticket}: TP1 REACHED - Current {current_price:.2f} >= TP1 {tp1_value:.2f}")
                            else:
                                logger.debug(f"Buy position {position.ticket}: TP1 NOT reached - Current {current_price:.2f} < TP1 {tp1_value:.2f}")
                        else:  # Sell
                            if current_price <= tp1_value:
                                tp1_reached = True
                                logger.info(f"Sell position {position.ticket}: TP1 REACHED - Current {current_price:.2f} <= TP1 {tp1_value:.2f}")
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
                            logger.info(f"Position {position.ticket}: TP1 reached but SL already at break-even (distance: {sl_distance_from_entry:.2f})")
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
        