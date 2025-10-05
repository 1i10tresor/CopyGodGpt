# config.py
"""Configuration file for the trading signal copier"""

# Multi-Account Configuration
# Single Account Configuration
ACCOUNT = {
    "login": 11164735,
    "password": "J&P2n8y%",
    "server": "VantageInternational-Demo",
    "broker_name": "VantageDemo",
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
            "BTC": "BTCUSD.sc",
            "bitcoin": "BTCUSD.sc",
        },
    },
    "VantageDemo": {
        "suffix": "+",
        "symbols": {
            "xauusd": "XAUUSD+",
            "gold": "XAUUSD+",
            "xagusd": "XAGUSD+",
            "silver": "XAGUSD+",
            "nas100": "NAS100",
            "nas 100": "NAS100",
            "NAS 100": "NAS100",
            "NAS100": "NAS100",
            "us100": "NAS100",
            "us30": "DJ30",
            "dj30": "DJ30",
            "dj 30": "DJ30",
            "us 30": "DJ30",
            "usoil": "CL-OIL",
            "cloil": "CL-OIL",
            "cl oil": "CL-OIL",
            "cl/oil": "CL-OIL",
            "btcusd": "BTCUSD",
            "btc usd": "BTCUSD",
            "btc": "BTCUSD",
            "BTC": "BTCUSD",
            "bitcoin": "BTCUSD",
            "SP500": "SP500",
            "US500": "SP500",
        },
    },
}

# Telegram Configuration
API_ID = 22757187  # Your Telegram API ID
API_HASH = "4b8c65f754c80ee53a55c162d141042d"  # Your Telegram API Hash
PHONE_NUMBER = "+33760110785"  # Your phone number with country code
CHANNEL_ID_1 =  -1003138138214
CHANNEL_ID_2 =  -1001946597047

GEMINI_API_KEY = "AIzaSyCtqNS9XJ_F_6H7kW9XrH-HtypS-zOSHSU"

# Trading Configuration
MAGIC_NUMBER = 20241211  # Magic number for identifying bot's orders
MAX_SLIPPAGE = 0  # Maximum slippage in points

# Risk Management Configuration
RISK_PERCENTAGE = 0.1  # Risk percentage per signal (0.1% = 0.1)
SYMBOLS_MIN_LOT_0_1 = [DJ30, NAS100, SP500
]

# Price Validation
MIN_PRICE = 3500  # Minimum valid entry price
MAX_PRICE = 3900  # Maximum valid entry price

# Break Even Configuration
BE_CHECK_INTERVAL = 0.2  # Interval in seconds for break-even checks
BE_OFFSET = 0  # Points to add to entry for break-even (0 = exact entry)
BE_SL_DISTANCE_PERCENTAGE = 0.01316  # Percentage of entry price for SL distance threshold (0.01316%)
MARKET_ORDER_TOLERANCE_FACTOR = 0.00019444  # Tolerance = price * factor (e.g., 3600 * 0.00019444 = 0.7)

# Logging Configuration
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "trading_copier.log"
LOG_ENCODING = "utf-8"  # UTF-8 encoding for proper emoji support


# Traded Symbols (for Fortune parser and future multi-symbol support)
TRADED_SYMBOLS = [
    # ---- MAJORS ----
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "USDCAD",
    "AUDUSD",
    "NZDUSD",

    # ---- MINORS ----
    # EUR crosses
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURNZD", "EURCAD",

    # GBP crosses
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPNZD", "GBPCAD",

    # JPY crosses
    "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY",

    # AUD & NZD crosses
    "AUDNZD", "AUDCHF", "AUDCAD", "NZDCHF", "NZDCAD",

    # CAD & CHF cross
    "CADCHF",

    # ---- COMMODITIES ----
    "XAUUSD",  # Or
    "USOIL",   # Pétrole brut (WTI)

    # ---- INDICES ----
    "US30",   # Dow Jones 30
    "US100",  # Nasdaq 100
    "US500",  # S&P 500
]