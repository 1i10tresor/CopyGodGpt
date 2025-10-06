"""
Symbol mapping utility for different brokers
"""

import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)


def normalize_symbol(symbol: str) -> str:
    """
    Normalize a symbol by removing spaces, hyphens, slashes and converting to lowercase
    
    Args:
        symbol: The symbol to normalize
        
    Returns:
        The normalized symbol
    """
    if not symbol:
        return ""
    
    # Remove spaces, hyphens, and slashes, then convert to lowercase
    normalized = re.sub(r'[\s\-/]', '', symbol).lower()
    return normalized


def get_broker_symbol(standard_symbol: str, broker_name: str, symbol_mapping_config: Dict[str, Any]) -> str:
    """
    Convert a standard symbol to broker-specific symbol
    
    Args:
        standard_symbol: The standard symbol (e.g., "XAUUSD")
        broker_name: The broker name (e.g., "VantageCent")
        symbol_mapping_config: The SYMBOL_MAPPING configuration
        
    Returns:
        The broker-specific symbol
    """
    try:
        # Check if broker exists in mapping
        if broker_name not in symbol_mapping_config:
            logger.warning(f"Broker '{broker_name}' not found in symbol mapping, using standard symbol")
            return standard_symbol
        
        broker_config = symbol_mapping_config[broker_name]
        
        # Check for explicit symbol mapping
        if "symbols" in broker_config:
            # Create a normalized lookup dictionary (remove spaces, hyphens, slashes, lowercase)
            symbols_normalized = {normalize_symbol(key): value for key, value in broker_config["symbols"].items()}
            
            # Normalize the input symbol for comparison
            normalized_input = normalize_symbol(standard_symbol)
            
            logger.debug(f"Symbol normalization: '{standard_symbol}' -> '{normalized_input}'")
            logger.debug(f"Available normalized symbols: {list(symbols_normalized.keys())}")
            
            if normalized_input in symbols_normalized:
                mapped_symbol = symbols_normalized[normalized_input]
                logger.debug(f"Symbol mapping: {standard_symbol} -> {mapped_symbol} for {broker_name}")
                return mapped_symbol
        
        # Apply suffix if no explicit mapping
        suffix = broker_config.get("suffix", "")
        mapped_symbol = standard_symbol + suffix
        
        if suffix:
            logger.debug(f"Symbol suffix applied: {standard_symbol} -> {mapped_symbol} for {broker_name}")
        else:
            logger.debug(f"No mapping needed: {standard_symbol} for {broker_name}")
        
        return mapped_symbol
        
    except Exception as e:
        logger.error(f"Error mapping symbol {standard_symbol} for broker {broker_name}: {e}")
        return standard_symbol