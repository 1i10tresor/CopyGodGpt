# models.py
"""Data models for trading signals"""

from dataclasses import dataclass
from typing import List, Union, Optional


@dataclass
class Signal:
    """Trading signal data structure"""
    direction: int  # 0 for buy, 1 for sell
    entry: float
    sl: Union[float, str]  # Can be float or "open"
    tps: List[Union[float, str]]  # Can contain floats or "open"
    message_id: int
    author: str
    symbol: str = "XAUUSD"  # Default to XAUUSD
    
    def __str__(self):
        direction_str = "BUY" if self.direction == 0 else "SELL"