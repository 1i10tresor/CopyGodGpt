# order_manager.py
"""Order placement and management for trading signals"""

import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
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
        
        # Security check 1: Entry price deviation from market price
        entry_deviation = abs(signal.entry - current_price) / current_price * 100
        if entry_deviation > config.ENTRY_PRICE_MAX_DEVIATION_PERCENTAGE:
            logger.warning(f"Signal {signal.message_id} ignored - Entry price deviation too high: "
                         f"{entry_deviation:.2f}% (max: {config.ENTRY_PRICE_MAX_DEVIATION_PERCENTAGE}%) - "
                         f"Entry: {signal.entry}, Market: {current_price}")
            return []
        
        # Security check 2: TP/SL deviation from entry price
        # Check SL deviation
        if isinstance(signal.sl, (int, float)):
            sl_deviation = abs(signal.sl - signal.entry) / signal.entry * 100
            if sl_deviation > config.TP_SL_MAX_DEVIATION_PERCENTAGE:
                logger.warning(f"Signal {signal.message_id} ignored - SL deviation too high: "
                             f"{sl_deviation:.2f}% (max: {config.TP_SL_MAX_DEVIATION_PERCENTAGE}%) - "
                             f"Entry: {signal.entry}, SL: {signal.sl}")
                return []
        
        # Check TP deviations
        for i, tp in enumerate(signal.tps, 1):
            if tp != "open" and isinstance(tp, (int, float)):
                tp_deviation = abs(tp - signal.entry) / signal.entry * 100
                if tp_deviation > config.TP_SL_MAX_DEVIATION_PERCENTAGE:
                    logger.warning(f"Signal {signal.message_id} ignored - TP{i} deviation too high: "
                                 f"{tp_deviation:.2f}% (max: {config.TP_SL_MAX_DEVIATION_PERCENTAGE}%) - "
                                 f"Entry: {signal.entry}, TP{i}: {tp}")
                    return []
        
        logger.debug(f"Signal {signal.message_id} passed security checks - "
                    f"Entry deviation: {entry_deviation:.2f}%")
        
        # Determine order type and price
        order_type, price = self.determine_order_type_and_price(signal, current_price)
        if order_type is None:
            logger.warning(f"Signal {signal.message_id} cancelled or invalid")
            return []
        
        # Get symbol precision for rounding
        digits = symbol_info.digits
        rounded_sl = round(signal.sl, digits)
        
        # Calculate lot size based on risk management (once per signal)
        lot_size = self.calculate_lot_size(signal, broker_symbol)
        if lot_size is None:
            logger.error(f"Could not calculate lot size for signal {signal.message_id}")
            return []
        
        logger.info(f"Calculated lot size: {lot_size} for signal {signal.message_id}")
        
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
                "volume": lot_size,
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
    
    def calculate_lot_size(self, signal: Signal, broker_symbol: str) -> Optional[float]:
        """
        Calculate lot size based on risk percentage and signal parameters
        
        Args:
            signal: The trading signal
            broker_symbol: The broker-specific symbol
            
        Returns:
            Calculated lot size or None if calculation fails
        """
        try:
            # Get account balance
            balance = self.mt5.get_account_balance()
            if balance is None:
                logger.error("Could not get account balance for lot size calculation")
                return None
            
            # Get symbol trading properties
            symbol_props = self.mt5.get_symbol_trade_properties(broker_symbol)
            if symbol_props is None:
                logger.error(f"Could not get symbol properties for {broker_symbol}")
                return None
            
            # Calculate total risk amount for the signal
            total_risk_amount = balance * (config.RISK_PERCENTAGE / 100)
            logger.debug(f"Total risk amount: {total_risk_amount} ({config.RISK_PERCENTAGE}% of {balance})")
            
            # Count valid TPs (non-"open")
            valid_tps = [tp for tp in signal.tps if tp != "open"]
            num_orders = len(valid_tps)
            
            if num_orders == 0:
                logger.warning("No valid TPs found for lot size calculation")
                return None
            
            # Calculate risk per order
            risk_per_order = total_risk_amount / num_orders
            logger.debug(f"Risk per order: {risk_per_order} (total: {total_risk_amount} / {num_orders} orders)")
            
            # Calculate SL distance in points
            sl_points = abs(signal.entry - signal.sl) / symbol_props['point']
            logger.debug(f"SL distance: {sl_points} points")
            
            # Calculate value per point per lot
            if symbol_props['trade_tick_size'] == 0:
                logger.error(f"Invalid trade_tick_size (0) for {broker_symbol}")
                return None
            
            value_per_point_per_lot = symbol_props['trade_tick_value'] / symbol_props['trade_tick_size']
            logger.debug(f"Value per point per lot: {value_per_point_per_lot}")
            
            # Calculate theoretical lot size
            if sl_points == 0 or value_per_point_per_lot == 0:
                logger.error(f"Invalid calculation parameters: sl_points={sl_points}, value_per_point_per_lot={value_per_point_per_lot}")
                return None
            
            calculated_lot_size = risk_per_order / (sl_points * value_per_point_per_lot)
            logger.debug(f"Calculated lot size: {calculated_lot_size}")
            
            # Apply 100x multiplier to calculated lot size
            calculated_lot_size = calculated_lot_size * 100
            logger.debug(f"Calculated lot size after 100x multiplier: {calculated_lot_size}")
            
            # Double lot size for Fortune signals
            if hasattr(signal, 'author') and signal.author and 'fortune' in signal.author.lower():
                calculated_lot_size = calculated_lot_size * 2
                logger.debug(f"Calculated lot size after Fortune doubling: {calculated_lot_size}")
            
            # Determine minimum lot size based on symbol
            if broker_symbol in config.SYMBOLS_MIN_LOT_0_1:
                min_lot_size = 0.1
                logger.debug(f"Symbol {broker_symbol} requires minimum lot size of 0.1")
            else:
                min_lot_size = 0.01
                logger.debug(f"Symbol {broker_symbol} uses standard minimum lot size of 0.01")
            
            # Apply minimum lot size constraint
            adjusted_lot_size = max(calculated_lot_size, min_lot_size)
            
            # Ensure lot size respects symbol constraints
            volume_min = max(symbol_props['volume_min'], min_lot_size)
            volume_max = symbol_props['volume_max']
            volume_step = symbol_props['volume_step']
            
            # Round to nearest valid step
            if volume_step > 0:
                steps = int(adjusted_lot_size / volume_step)
                final_lot_size = steps * volume_step
                
                # Ensure it's at least the minimum
                if final_lot_size < volume_min:
                    final_lot_size = volume_min
                
                # Ensure it doesn't exceed maximum
                if final_lot_size > volume_max:
                    final_lot_size = volume_max
                    logger.warning(f"Lot size capped at maximum: {volume_max}")
            else:
                final_lot_size = max(adjusted_lot_size, volume_min)
                if final_lot_size > volume_max:
                    final_lot_size = volume_max
            
            logger.info(f"Final lot size: {final_lot_size} (calculated: {calculated_lot_size:.4f}, adjusted: {adjusted_lot_size:.4f})")
            
            return final_lot_size
            
        except Exception as e:
            logger.error(f"Error calculating lot size: {e}", exc_info=True)
            return None
    
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
                        # Calculate dynamic threshold based on entry price percentage
                        dynamic_threshold = entry_price * (config.BE_SL_DISTANCE_PERCENTAGE / 100)
                        logger.debug(f"Position {position.ticket}: SL distance from entry: {sl_distance_from_entry:.2f}")
                        logger.debug(f"Position {position.ticket}: Dynamic threshold (0.01316% of {entry_price:.2f}): {dynamic_threshold:.2f}")
                        
                        if tp1_reached and sl_distance_from_entry > dynamic_threshold:
                            new_sl = entry_price + config.BE_OFFSET
                            logger.info(f"Position {position.ticket}: BREAK-EVEN NEEDED - New SL will be {new_sl:.2f} (entry: {entry_price:.2f}, offset: {config.BE_OFFSET}, threshold: {dynamic_threshold:.2f})")
                            
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
                            logger.debug(f"Position {position.ticket}: TP1 reached but SL already at break-even (distance: {sl_distance_from_entry:.2f} <= threshold: {dynamic_threshold:.2f})")
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
    
    def handle_modification_command(self, original_message_id: int, command_text: str):
        """
        Handle modification commands for existing positions
        
        Args:
            original_message_id: ID of the original signal message
            command_text: The modification command text
        """
        logger.info(f"Processing modification command for message {original_message_id}: '{command_text}'")
        
        # Normalize command
        command_text_lower = command_text.lower().strip()
        
        # Get all positions with our magic number
        try:
            positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
            if positions is None:
                logger.warning(f"No positions found for modification command")
                return
            
            # Filter positions that belong to the original message
            target_positions = []
            for position in positions:
                if position.comment and position.comment.startswith(f"{original_message_id}/"):
                    target_positions.append(position)
            
            if not target_positions:
                logger.warning(f"No positions found for message ID {original_message_id}")
                return
            
            logger.info(f"Found {len(target_positions)} positions for message ID {original_message_id}")
            
            # Execute specific actions based on command
            if command_text_lower in ["cloturez now", "clôtuez now"]:
                self._close_positions(target_positions)
            elif command_text_lower in ["breakeven", "be", "b.e"]:
                self._apply_breakeven_to_positions(target_positions)
            elif command_text_lower == "prendre tp1 now":
                self._close_tp1_position(target_positions)
            else:
                logger.warning(f"Unrecognized modification command: '{command_text}'")
                
        except Exception as e:
            logger.error(f"Error handling modification command: {e}", exc_info=True)
    
    def _close_positions(self, positions: List[Any]):
        """Close all specified positions"""
        logger.info(f"Closing {len(positions)} positions")
        
        for position in positions:
            try:
                # Determine close order type (opposite of position type)
                if position.type == mt5.POSITION_TYPE_BUY:
                    close_type = mt5.ORDER_TYPE_SELL
                else:
                    close_type = mt5.ORDER_TYPE_BUY
                
                # Get current market price
                current_price = self.mt5.get_market_price(position.symbol, position.type)
                if current_price is None:
                    logger.error(f"Could not get market price for {position.symbol}")
                    continue
                
                # Prepare close request
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": position.symbol,
                    "volume": position.volume,
                    "type": close_type,
                    "position": position.ticket,
                    "price": current_price,
                    "deviation": config.MAX_SLIPPAGE,
                    "magic": config.MAGIC_NUMBER,
                    "comment": f"Close {position.comment}",
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                # Send close order
                result = mt5.order_send(request)
                
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"✅ Position {position.ticket} closed successfully")
                else:
                    error_msg = f"❌ Failed to close position {position.ticket}"
                    if result:
                        error_msg += f": {result.retcode}"
                        if hasattr(result, 'comment') and result.comment:
                            error_msg += f" - {result.comment}"
                    logger.error(error_msg)
                    
            except Exception as e:
                logger.error(f"Error closing position {position.ticket}: {e}")
    
    def _apply_breakeven_to_positions(self, positions: List[Any]):
        """Apply breakeven (move SL to entry) for all specified positions"""
        logger.info(f"Applying breakeven to {len(positions)} positions")
        
        for position in positions:
            try:
                new_sl = position.price_open + config.BE_OFFSET
                
                success = self.mt5.modify_sl_for_position(
                    ticket=position.ticket,
                    new_sl=new_sl,
                    current_tp=position.tp
                )
                
                if success:
                    logger.info(f"✅ Breakeven applied to position {position.ticket} - SL moved to {new_sl}")
                else:
                    logger.error(f"❌ Failed to apply breakeven to position {position.ticket}")
                    
            except Exception as e:
                logger.error(f"Error applying breakeven to position {position.ticket}: {e}")
    
    def _close_tp1_position(self, positions: List[Any]):
        """Close the TP1 position (position whose TP matches the TP1 value from comment)"""
        logger.info(f"Looking for TP1 position among {len(positions)} positions")
        
        for position in positions:
            try:
                # Extract TP1 value from comment (format: messageId/tp1Value)
                if not position.comment or '/' not in position.comment:
                    logger.warning(f"Position {position.ticket} has invalid comment format: '{position.comment}'")
                    continue
                
                comment_parts = position.comment.split('/')
                if len(comment_parts) < 2:
                    logger.warning(f"Position {position.ticket} comment missing TP1 value: '{position.comment}'")
                    continue
                
                try:
                    tp1_value = float(comment_parts[1])
                except ValueError:
                    logger.warning(f"Position {position.ticket} has invalid TP1 value in comment: '{comment_parts[1]}'")
                    continue
                
                # Check if this position's TP exactly matches the TP1 value
                if position.tp == tp1_value:
                    logger.info(f"Found TP1 position {position.ticket} with TP={position.tp} matching TP1={tp1_value}")
                    
                    # Close this specific position
                    self._close_positions([position])
                    return
                else:
                    logger.debug(f"Position {position.ticket} TP={position.tp} does not match TP1={tp1_value}")
                    
            except Exception as e:
                logger.error(f"Error processing position {position.ticket} for TP1 close: {e}")
        
        logger.warning("No TP1 position found to close")