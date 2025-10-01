Round prices to symbol precision
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
            }
            
            # Add price for pending orders
            if order_type not in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
                request["price"] = round(price, digits)
                
                # Add expiration for pending orders only
                if signal.expiration_minutes:
                    expiration_time = datetime.now() + timedelta(minutes=signal.expiration_minutes, seconds=10)
                    request["expiration"] = int(expiration_time.timestamp())
                    request["type_time"] = mt5.ORDER_TIME_SPECIFIED
                    logger.debug(f"Setting expiration for pending order: {expiration_time} (with 10s buffer)")
                else:
                    request["type_time"] = mt5.ORDER_TIME_GTC
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
        