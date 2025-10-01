# config.py
"""Configuration file for the trading signal copier"""

# Multi-Account Configuration
# Single Account Configuration
ACCOUNT = {
    "login": 16563439,
    "password": "2iuZW^K%",
    "server": "VantageInternational-Live 11",
    "broker_name": "VantageCent",
    "lot_size": 0.01,
    "mt5_path": r"C:\Program Files\MetaTrader 5 - master\\terminal64.exe"
}

# Symbol Mapping Configuration
SYMBOL_MAPPING = {
    "VantageCent": {
        "suffix": ".sc",
        "symbols": {
            "xauusd": "XAUUSD.sc",
            "gold": "XAUUSD.sc",
            "xagusd": "XAGUSD.sc",
            "silver": "XAGUSD.sc",
            "nas100": "US100",
            "us100": "US100",
            "us30": "DJ30.r",
            "dj30": "DJ30.r",
            "dj 30": "DJ30.r",
            "us 30": "DJ30.r",
            "usoil": "CL-OIL.sc",
            "cloil": "CL-OIL.sc",
            "cl oil": "CL-OIL.sc",
            "cl/oil": "CL-OIL.sc",
            "btcusd": "BTCUSD.sc",
            "btc usd": "BTCUSD.sc",
            "btc": "BTCUSD.sc",
            "bitcoin": "BTCUSD.sc",
        }
    },
    "PuprimeCent": {
        "suffix": ".sc",
        "symbols": {
            "xauusd": "XAUUSD.sc",
            "gold": "XAUUSD.sc",
            "xagusd": "XAGUSD.sc", 
            "silver": "XAGUSD.sc",
            "btcusd": "BTCUSD",
            "btc": "BTCUSD",
            "bitcoin": "BTCUSD",
            "dj30": "DJ30.s",
            "us30": "DJ30.s",
            "us100": "NAS100.s",
            "us 100": "NAS100.s",
            "nas100": "NAS100.s",
            "nasdaq100": "NAS100.s",
            "usoil": "CL-OIL.sc",
            "cloil": "CL-OIL.sc",
            "cl oil": "CL-OIL.sc",
            "cl/oil": "CL-OIL.sc",
        }
    },
    "Puprime": {
        "suffix": ".",
        "symbols": {}
    },
}

# Telegram Configuration
API_ID = 22757187  # Your Telegram API ID
API_HASH = "4b8c65f754c80ee53a55c162d141042d"  # Your Telegram API Hash
PHONE_NUMBER = "+33760110785"  # Your phone number with country code
CHANNEL_ID =  -1002925234012
# CHANNEL_ID =  -1001946597047

GEMINI_API_KEY = "AIzaSyCtqNS9XJ_F_6H7kW9XrH-HtypS-zOSHSU"

# Trading Configuration
MAGIC_NUMBER = 20241211  # Magic number for identifying bot's orders
MAX_SLIPPAGE = 0  # Maximum slippage in points

# Price Validation
MIN_PRICE = 3500  # Minimum valid entry price
MAX_PRICE = 3900  # Maximum valid entry price

# Break Even Configuration
BE_CHECK_INTERVAL = 0.2  # Interval in seconds for break-even checks
BE_OFFSET = 0  # Points to add to entry for break-even (0 = exact entry)
MARKET_ORDER_TOLERANCE_FACTOR = 0.00019444  # Tolerance = price * factor (e.g., 3600 * 0.00019444 = 0.7)

# Trade Expiration Configuration (in minutes)
EXPIRATION_TIMES = {
    "DEFAULT": 5,    # 5 minutes for default authors (like RDL)
    "ICM": 5,        # 5 minutes for ICM
    "FORTUNE": 720,  # 12 hours (720 minutes) for Fortune
}

# MT5 Time Offset Configuration
MT5_TIME_OFFSET_MINUTES = 60  # Terminal MT5 is 60 minutes ahead of system time

# Logging Configuration
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "trading_copier.log"
LOG_ENCODING = "utf-8"  # UTF-8 encoding for proper emoji support


# Traded Symbols (for Fortune parser and future multi-symbol support)
TRADED_SYMBOLS = [
    "XAUUSD",
    "XAGUSD",
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "GBPCAD", "EURCAD",
    "BTCUSD",
    "US30", "US100", "US500",
    "USOIL",
]