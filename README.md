# Trading Signal Copier

Automated trading bot that copies signals from Telegram to MetaTrader 5.

## Features

- ✅ Automatic signal detection from Telegram channels
- ✅ Multi-author signal parsing (ICM, default formats)
- ✅ Smart order placement (market/pending)
- ✅ Automatic break-even management
- ✅ Comprehensive error handling and logging

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure `config.py` with your credentials:
   - MT5 login credentials
   - Telegram API credentials (get from https://my.telegram.org)
   - Channel ID to monitor

4. Run the bot:
   ```bash
   python main.py
   ```

## Signal Formats

### ICM Format
- Entry: First number in message
- SL: Number on line containing "SL"
- TPs: Entry + 2.5, +5, +8

### Default Format
- Entry: First number in message
- SL: Entry ±8 (based on direction)
- TPs: Entry ±2, ±4, ±6, "open"

## Order Logic

### BUY Orders
- Price ≤ SL: Order cancelled
- SL < Price < Entry+0.75: Market order
- Price ≥ Entry+0.75: Buy Limit

### SELL Orders
- Price ≥ SL: Order cancelled
- Entry-0.75 < Price < SL: Market order
- Price ≤ Entry-0.75: Sell Limit

## Files Structure

- `config.py` - Configuration settings
- `models.py` - Data models
- `parser.py` - Signal parsing logic
- `mt5_manager.py` - MT5 connection management
- `order_manager.py` - Order placement and monitoring
- `telegram_listener.py` - Telegram message handling
- `main.py` - Main application

## Support

For issues or questions, check the logs in `trading_copier.log`.
