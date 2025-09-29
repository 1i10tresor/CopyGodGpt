# fortune_parser.py
"""Parser specifically for Fortune trading signals"""

import re
import logging
from typing import List, Optional, Dict, Tuple
import config

logger = logging.getLogger(__name__)


class FortuneSignalParser:
    """Specialized parser for Fortune signals with multiple entries support"""
    
    def __init__(self):
        self.traded_symbols = [symbol.upper() for symbol in config.TRADED_SYMBOLS]
    
    @staticmethod
    def extract_numbers(text: str) -> List[float]:
        """Extract all numbers from text (handles decimals with . or , and spaces)"""
        # First, remove spaces within numbers (3 600 -> 3600)
        text_normalized = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
        
        # Pattern to match numbers with either . or , as decimal separator
        pattern = r'\d+(?:[.,]\d+)?'
        matches = re.findall(pattern, text_normalized)
        numbers = []
        for match in matches:
            try:
                # Replace comma with dot for float conversion
                normalized = match.replace(',', '.')
                number = float(normalized)
                numbers.append(number)
            except ValueError:
                continue
        return numbers
    
    def get_direction(self, text: str) -> Optional[int]:
        """Determine trade direction from text"""
        text_upper = text.upper()
        if 'BUY' in text_upper:
            return 0
        elif 'SELL' in text_upper:
            return 1
        return None
    
    def get_symbol(self, text: str) -> Optional[str]:
        """Find which traded symbol is mentioned in the text"""
        text_upper = text.upper()
        
        for symbol in self.traded_symbols:
            # Look for symbol with word boundaries to avoid false matches
            pattern = r'\b' + re.escape(symbol) + r'\b'
            if re.search(pattern, text_upper):
                # Return standardized symbol (e.g., "GOLD" -> "XAUUSD")
                if symbol == "GOLD":
                    return "XAUUSD"
                elif symbol == "SILVER":
                    return "XAGUSD"
                else:
                    return symbol
        
        return None
    
    def get_entries(self, text: str) -> List[float]:
        """
        Extract entry prices from first line
        Can be single entry: "Sell Gold 3654.50"
        Or range: "BUY GBPCAD FROM 1.8745 - 1.8755"
        """
        lines = text.split('\n')
        if not lines:
            return []
        
        first_line = lines[0]
        entries = []
        
        # Check for "FROM x - y" pattern (range entry)
        range_pattern = r'FROM\s+(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)'
        range_match = re.search(range_pattern, first_line.upper())
        
        if range_match:
            # Range entry found
            entry1 = float(range_match.group(1).replace(',', '.'))
            entry2 = float(range_match.group(2).replace(',', '.'))
            entries = [entry1, entry2]
            logger.debug(f"Fortune: Found range entries: {entries}")
        else:
            # Single entry - get first number in first line
            numbers = self.extract_numbers(first_line)
            if numbers:
                entries = [numbers[0]]
                logger.debug(f"Fortune: Found single entry: {entries}")
        
        return entries
    
    def get_stop_loss(self, text: str) -> Optional[float]:
        """Find stop loss value from line containing 'SL'"""
        # Look for SL pattern with various separators
        sl_pattern = r'SL\s*[-–:]?\s*(\d+(?:[.,]\d+)?)'
        sl_match = re.search(sl_pattern, text.upper())
        
        if sl_match:
            sl = float(sl_match.group(1).replace(',', '.'))
            logger.debug(f"Fortune: Found SL: {sl}")
            return sl
        
        return None
    
    def get_take_profits(self, text: str, entries: List[float], sl: float) -> List[float]:
        """
        Extract all remaining numbers as TPs
        Excluding entries and SL already identified
        """
        # Look specifically for TP patterns first
        # This pattern captures TP, TP1, TP2, etc. followed by separators and the number
        tp_patterns = [
            r'TP\s*[-–:]\s*(\d+(?:[.,]\d+)?)',     # TP - 1.7733
            r'TP\d+\s*[-–:]\s*(\d+(?:[.,]\d+)?)',   # TP2- 1.7720
            r'TP\s+(\d+(?:[.,]\d+)?)',              # TP 1.7733
            r'TP\d+\s+(\d+(?:[.,]\d+)?)',           # TP2 1.7720
        ]
        
        tps = []
        text_upper = text.upper()
        
        # Try each pattern to find all TPs
        for pattern in tp_patterns:
            matches = re.findall(pattern, text_upper)
            for match in matches:
                tp_value = float(match.replace(',', '.'))
                if tp_value not in tps:  # Avoid duplicates
                    tps.append(tp_value)
        
        # Sort TPs to maintain order
        tps.sort()
        
        if tps:
            logger.debug(f"Fortune: Found explicit TPs: {tps}")
        else:
            # Fallback: extract all numbers except entries and SL
            all_numbers = self.extract_numbers(text)
            
            # Create set of numbers to exclude (entries and SL)
            exclude = set(entries)
            if sl:
                exclude.add(sl)
            
            # Filter out excluded numbers (with small tolerance for float comparison)
            for num in all_numbers:
                is_excluded = False
                for excl in exclude:
                    if abs(num - excl) < 0.01:  # Tolerance for float comparison
                        is_excluded = True
                        break
                
                if not is_excluded:
                    tps.append(num)
        
        logger.debug(f"Fortune: Final TPs: {tps}")
        return tps
    
    def parse(self, text: str, message_id: int) -> Optional[Dict]:
        """
        Parse a Fortune signal and return structured data
        Returns dict with: direction, entries, sl, tps, symbol, message_id
        """
        # Check basic requirements
        text_upper = text.upper()
        if 'TP' not in text_upper or 'SL' not in text_upper:
            return None
        
        # Get direction
        direction = self.get_direction(text)
        if direction is None:
            logger.warning(f"Fortune: Could not determine direction for signal {message_id}")
            return None
        
        # Get symbol - REQUIRED for Fortune
        symbol = self.get_symbol(text)
        if symbol is None:
            logger.warning(f"Fortune: No recognized symbol found in signal {message_id}, ignoring signal")
            return None
        
        # Get entries (1 or 2)
        entries = self.get_entries(text)
        if not entries:
            logger.warning(f"Fortune: No entry price found in signal {message_id}")
            return None
        
        # Get stop loss
        sl = self.get_stop_loss(text)
        if sl is None:
            logger.warning(f"Fortune: No stop loss found in signal {message_id}")
            return None
        
        # Get take profits
        tps = self.get_take_profits(text, entries, sl)
        if not tps:
            logger.warning(f"Fortune: No take profits found in signal {message_id}")
            return None
        
        # Add "open" as last TP if not already 4 TPs
        if len(tps) < 4:
            tps.append("open")
        
        # Create signal dictionary
        signal_data = {
            "direction": direction,
            "entries": entries,
            "sl": sl,
            "tps": tps[:4],  # Limit to 4 TPs
            "symbol": symbol,
            "message_id": message_id,
            "author": "Fortune"
        }
        
        logger.info(f"Fortune Signal parsed - Symbol: {symbol}, Entries: {entries}, SL: {sl}, TPs: {tps[:4]}")
        
        return signal_data