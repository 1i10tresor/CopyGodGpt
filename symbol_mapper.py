"""
Symbol mapping utility for different brokers
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


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
            # Create a case-insensitive lookup dictionary
            symbols_lower = {key.lower(): value for key, value in broker_config["symbols"].items()}
            
            if standard_symbol.lower() in symbols_lower:
                mapped_symbol = symbols_lower[standard_symbol.lower()]
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