# parser.py
"""Signal parsing logic for different message formats"""

import re
import logging
from typing import List, Optional
from models import Signal
from fortune_parser import FortuneSignalParser
from ai_parser import AISignalParser
import config

logger = logging.getLogger(__name__)


class SignalParser:
    """Parses trading signals from Telegram messages"""
    
    def __init__(self):
        self.fortune_parser = FortuneSignalParser()
        self.traded_symbols = [symbol.upper() for symbol in config.TRADED_SYMBOLS]
        # Initialize AI parser if API key is configured
        if hasattr(config, 'GEMINI_API_KEY') and config.GEMINI_API_KEY != "your_gemini_api_key_here":
            self.ai_parser = AISignalParser(config.GEMINI_API_KEY)
        else:
            self.ai_parser = None
            logger.warning("Gemini API key not configured - AI parsing disabled")
    
    def get_symbol_from_text(self, text: str) -> Optional[str]:
        """Find which traded symbol is mentioned in the text"""
        logger.debug(f"get_symbol_from_text: Analyzing text: '{text}'")
        text_upper = text.upper()
        
        for symbol in self.traded_symbols:
            logger.debug(f"get_symbol_from_text: Checking symbol '{symbol}'")
            # Look for symbol with word boundaries to avoid false matches
            pattern = r'\b' + re.escape(symbol) + r'\b'
            if re.search(pattern, text_upper):
                # Return standardized symbol
                if symbol == "GOLD":
                    logger.debug(f"get_symbol_from_text: Found GOLD, returning XAUUSD")
                    return "XAUUSD"
                elif symbol == "SILVER":
                    logger.debug(f"get_symbol_from_text: Found SILVER, returning XAGUSD")
                    return "XAGUSD"
                else:
                    logger.debug(f"get_symbol_from_text: Found symbol '{symbol}', returning as-is")
                    return symbol
        
        logger.debug(f"get_symbol_from_text: No symbol found in text, returning None")
        return None
    
    @staticmethod
    def extract_numbers(text: str) -> List[float]:
        """Extract all numbers from text (formats: 3600 or 3600.5 or 3600,5 or 3 600 or 3 600.50)"""
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
    
    @staticmethod
    def get_direction(text: str) -> Optional[int]:
        """Determine trade direction from text"""
        text_lower = text.lower()
        if 'buy' in text_lower:
            return 0
        elif 'sell' in text_lower:
            return 1
        return None
    
    def parse_icm_signal(self, text: str, message_id: int) -> Optional[Signal]:
        """
        Parse signals from ICM author
        Logic: If first number is between 3500-3900, treat as XAUUSD with fixed TPs
        Otherwise, return None to trigger AI parsing
        """
        direction = self.get_direction(text)
        if direction is None:
            logger.warning(f"Could not determine direction for ICM signal {message_id}")
            return None
        
        # Extract first number from first line as potential entry
        lines = text.split('\n')
        first_line = lines[0] if lines else text
        numbers = self.extract_numbers(text)
        if not numbers:
            logger.warning(f"No numbers found in ICM signal {message_id}")
            return None
        
        # First number is potential entry
        entry = numbers[0]
        logger.debug(f"ICM: First number found: {entry}")
        
        # Check if price is in XAUUSD range (3500-3900)
        if not (config.MIN_PRICE <= entry <= config.MAX_PRICE):
            logger.info(f"ICM: Price {entry} not in XAUUSD range ({config.MIN_PRICE}-{config.MAX_PRICE}), will use AI parser")
            return None
        else:
            logger.debug(f"ICM: Price {entry} in XAUUSD range, using XAUUSD with fixed TPs")
            symbol = "XAUUSD"
        
        # Find SL - number after "SL"
        text_upper = text.upper()
        sl = None
        
        # Find number immediately after SL
        sl_match = re.search(r'SL\s*(\d+(?:[.,]\d+)*)', text_upper)
        if sl_match:
            sl_str = sl_match.group(1).replace(',', '.')
            sl = float(sl_str)
            logger.debug(f"ICM: Found SL = {sl}")
        else:
            # Fallback: get next number after SL
            sl_pos = text_upper.find('SL')
            if sl_pos != -1:
                text_after_sl = text[sl_pos+2:]
                sl_numbers = self.extract_numbers(text_after_sl)
                if sl_numbers:
                    sl = sl_numbers[0]
                    logger.debug(f"ICM: Found SL (fallback) = {sl}")
        
        if sl is None:
            logger.warning(f"Could not find SL in ICM signal {message_id}")
            return None
        
        # ICM XAUUSD: Fixed TPs based on direction
        if direction == 0:  # BUY
            tps = [entry + 2, entry + 5, entry + 8, entry + 20]
        else:  # SELL
            tps = [entry - 2, entry - 5, entry - 8, entry - 20]
        
        logger.info(f"ICM XAUUSD Signal parsed - Entry: {entry}, SL: {sl}, TPs: {tps}")
        
        return Signal(
            direction=direction,
            entry=entry,
            sl=sl,
            tps=tps,
            message_id=message_id,
            author="ICM",
            symbol=symbol,
        )
    
    def parse_default_signal(self, text: str, message_id: int, author: str) -> Optional[Signal]:
        """
        Parse signals from default authors (like RDL)
        Logic: Extract first number from first line as entry, calculate fixed SL and TPs
        Symbol is always XAUUSD
        """
        direction = self.get_direction(text)
        if direction is None:
            logger.warning(f"Could not determine direction for signal {message_id}")
            return None
        
        # Extract first number from first line only
        lines = text.split('\n')
        first_line = lines[0] if lines else text
        numbers = self.extract_numbers(first_line)
        if not numbers:
            logger.warning(f"No numbers found in signal {message_id}")
            return None
        
        # First number from first line is the entry point
        entry = numbers[0]
        logger.debug(f"RDL: Entry from first line: {entry}")
        
        # RDL always trades XAUUSD
        symbol = "XAUUSD"
        
        # Calculate SL and TPs based on direction
        if direction == 0:  # Buy
            sl = entry - 8
            tps = [entry + 2, entry + 4, entry + 6, "open"]
        else:  # Sell
            sl = entry + 8
            tps = [entry - 2, entry - 4, entry - 6, "open"]
        
        logger.info(f"RDL Signal parsed - Entry: {entry}, SL: {sl}, TPs: {tps}")
        
        return Signal(
            direction=direction,
            entry=entry,
            sl=sl,
            tps=tps,
            message_id=message_id,
            author=author,
            symbol=symbol,
        )
    
    def parse(self, text: str, author: str, message_id: int) -> Optional[Signal]:
        """Parse a trading signal from message text"""
        # Check if message contains required keywords
        text_upper = text.upper()
        if 'TP' not in text_upper or 'SL' not in text_upper:
            return None
        
        # Also check for BUY or SELL
        if 'BUY' not in text_upper and 'SELL' not in text_upper:
            return None
        
        author_lower = author.lower() if author else ""
        
        # Normalize author name by removing non-alphanumeric characters for comparison
        import re
        author_normalized = re.sub(r'[^a-zA-Z0-9]', '', author).lower() if author else ""
        logger.debug(f"parse: Author normalized from '{author}' to '{author_normalized}'")
        
        # Try regex parsing first for appropriate cases
        if 'icm' in author_normalized:
            # Always try ICM regex parser first
            icm_signal = self.parse_icm_signal(text, message_id)
            logger.debug(f"parse: ICM regex parser result: {icm_signal}")
            if icm_signal:
                return icm_signal
            
            # If ICM regex parsing failed, use AI if available
            if self.ai_parser:
                logger.info(f"ICM regex parsing failed for signal {message_id}, using AI parser")
                logger.debug(f"parse: Calling AI parser for ICM signal")
                ai_result = self.ai_parser.parse_with_ai(text, author)
                logger.debug(f"parse: AI parser result: {ai_result}")
                if ai_result:
                    logger.debug(f"parse: AI identified symbol as '{ai_result['symbol']}'")
                    # Convert AI result to Signal
                    entry = ai_result["entries"][0] if ai_result["entries"] else None
                    if entry:
                        return Signal(
                            direction=ai_result["direction"],
                            entry=entry,
                            sl=ai_result["sl"],
                            tps=ai_result["tps"],
                            message_id=message_id,
                            author=author,
                            symbol=ai_result["symbol"],
                        )
                else:
                    logger.warning(f"parse: AI parser also failed for ICM signal {message_id}")
            return None
            
        elif 'fortune' in author_normalized:
            # Always use AI for Fortune if available
            if self.ai_parser:
                logger.info(f"Using AI parser for Fortune signal {message_id}")
                logger.debug(f"parse: Calling AI parser for Fortune signal")
                ai_result = self.ai_parser.parse_with_ai(text, author)
                logger.debug(f"parse: AI parser result for Fortune: {ai_result}")
                if ai_result:
                    logger.debug(f"parse: AI identified Fortune symbol as '{ai_result['symbol']}'")
                    # Convert AI result to Signal
                    entry = ai_result["entries"][0] if ai_result["entries"] else None
                    if entry:
                        signal = Signal(
                            direction=ai_result["direction"],
                            entry=entry,
                            sl=ai_result["sl"],
                            tps=ai_result["tps"],
                            message_id=message_id,
                            author=author,
                            symbol=ai_result["symbol"],
                        )
                        
                        # Log Fortune signal
                        direction_str = "BUY" if signal.direction == 0 else "SELL"
                        logger.info(f"📊 Valid Fortune signal detected: Signal({direction_str} {signal.symbol} @ {signal.entry}, "
                                  f"SL: {signal.sl}, TPs: {signal.tps}, ID: {message_id})")
                        
                        return signal
                else:
                    logger.warning(f"AI parsing failed for Fortune signal {message_id}")
            else:
                logger.warning(f"AI parser not available for Fortune signal {message_id}")
            return None
        
        elif 'dweb' in author_normalized:
            # DWEB signals - currently in monitoring mode
            logger.info(f"DWEB signal detected from {author} - currently ignoring (monitoring mode)")
            return None
        
        else:
            # Default authors (like RDL) - use default parsing logic
            logger.info(f"Using default parser for author: {author}")
            return self.parse_default_signal(text, message_id, author)