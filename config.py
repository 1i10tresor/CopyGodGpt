# config.py
"""Configuration file for the trading signal copier"""

# Multi-Account Configuration
ACCOUNTS = [
    {
        "login": 207528,
        "password": "A.4G3Rv0w2",
        "server": "FusionMarkets-Demo",
        "broker_name": "FusionMarkets",
        "lot_size": 0.01,
        "is_master": True,
        "mt5_path": r"C:\Program Files\MetaTrader 5 - master\\terminal64.exe"
    },
    # {
    #     "login": 211205,
    #     "password": "_28iH5fO18",
    #     "server": "FusionMarkets-Demo",
    #     "broker_name": "FusionMarkets",
    #     "lot_size": 0.02,
    #     "is_master": False,
    #     "mt5_path": r"C:\Program Files\MetaTrader 5 - 1\\terminal64.exe"
    # },
    # {
    #     "login": 16564214,
    #     "password": "a7*Xi&RS",
    #     "server": "VantageInternational-Live 11",
    #     "broker_name": "VantageCent",
    #     "lot_size": 0.02,
    #     "is_master": False,
    #     "mt5_path": r"C:\Program Files\MetaTrader 5 - 2\\terminal64.exe"
    # },
    {
        "login": 17279826,
        "password": "5eA%*2Av",
        "server": "VantageInternational-Live 3",
        "broker_name": "VantageCent",
        "lot_size": 0.01,
        "is_master": False,
        "mt5_path": r"C:\Program Files\MetaTrader 5 - 3\\terminal64.exe"
    },
    # {
    #     "login": 16569381,
    #     "password": "2U$D6Oq&",
    #     "server": "VantageInternational-Live 11",
    #     "broker_name": "VantageCent",
    #     "lot_size": 0.01,
    #     "is_master": False,
    #     "mt5_path": r"C:\Program Files\MetaTrader 5 - 4\\terminal64.exe"
    # },
    # {
    #     "login": 18091608,
    #     "password": "^V69o%b3",
    #     "server": "PUPrime-Live2",
    #     "broker_name": "Puprime",
    #     "lot_size": 0.01,
    #     "is_master": False,
    #     "mt5_path": r"C:\Program Files\MetaTrader 5 - 5\\terminal64.exe"
    # },
    # {
    #     "login": 16618114,
    #     "password": "^lNm6R*r",
    #     "server": "PUPrime-Live2",
    #     "broker_name": "Puprime",
    #     "lot_size": 0.01,
    #     "is_master": False,
    #     "mt5_path": r"C:\Program Files\MetaTrader 5 - 6\\terminal64.exe"
    # },
    # {
    #     "login": 18162256,
    #     "password": "#fosR4xa",
    #     "server": "VantageInternational-Live",
    #     "broker_name": "VantageCent",
    #     "lot_size": 0.01,
    #     "is_master": False,
    #     "mt5_path": r"C:\Program Files\MetaTrader 5 - 7\\terminal64.exe"
    # },
    {
        "login": 16159831,
        "password": "^Su7u0%k",
        "server": "PUPrime-Live2",
        "broker_name": "PuprimeCent",
        "lot_size": 0.01,
        "is_master": False,
        "mt5_path": r"C:\Program Files\MetaTrader 5 - 8\\terminal64.exe"
    },
    
]

# Symbol Mapping Configuration
SYMBOL_MAPPING = {
    "FusionMarkets": {
        "suffix": "",
        "symbols": {
            "gold": "XAUUSD.sc",
            "btc": "BTCUSD",
        }
    },
    "VantageCent": {
        "suffix": ".pc",
        "symbols": {
            "NAS100": "US100",
            "US30": "DJ30.r",
            "DJ30": "DJ30.r",
            "DJ 30": "DJ30.r",
            "US 30": "DJ30.r",
            "USOIL": "CL-OIL.pc",
            "CLOIL": "CL-OIL.pc",
            "CL OIL": "CL-OIL.pc",
            "CL/OIL": "CL-OIL.pc",
            "BTCUSD": "BTCUSD.sc",
            "BTC USD": "BTCUSD.sc",
            "BTC": "BTCUSD.sc",
            "bitcoin": "BTCUSD.sc",
            "gold": "XAUUSD.sc",
        }
    },
    "PuprimeCent": {
        "suffix": ".sc",
        "symbols": {
            "gold": "XAUUSD.sc",
            "btc": "BTCUSD",
            "BTCUSD": "BTCUSD",
            "bitcoin": "BTCUSD",
            "dj30": "DJ30.s",
            "us100": "NAS100.s",
            "us 100": "NAS100.s",
            "nas100": "NAS100.s",
            "nasdaq100": "NAS100.s",
            "USOIL": "CL-OIL.sc",
            "CLOIL": "CL-OIL.sc",
            "CL OIL": "CL-OIL.sc",
            "CL/OIL": "CL-OIL.sc",
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
    "CL-OIL",
]