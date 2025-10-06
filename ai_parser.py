# ai_parser.py
"""AI-based signal parsing using Gemini Flash 2.0"""

import json
import logging
import google.generativeai as genai
from typing import Optional, Dict, List
import config

logger = logging.getLogger(__name__)


class AISignalParser:
    """Parse trading signals using Gemini AI"""
    
    def __init__(self, api_key: str):
        """
        Initialize Gemini AI parser
        
        Args:
            api_key: Google AI API key for Gemini
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Prompt template - to be filled by user
        self.prompt_template = """
        Transformez ce message de trading en un signal normalisé au format JSON. Extrayez UNIQUEMENT les éléments présents dans le message, sans calcul ni modification.
        
        Règles d'extraction :
        1. Pour l'AUTEUR :
           - Extraire le nom/pseudo de la personne qui a écrit le message s'il est explicitement mentionné
           - Rechercher spécifiquement "𝐈𝐂𝐌 𝐏𝐑𝐎", "ICM PRO", "Fortune Admin", "FORTUNE ADMIN", "Fortune", "FORTUNE"
           - Si aucun auteur spécifique n'est identifiable, retourner "DEFAULT_AUTHOR"
        
        2. Pour le SYMBOL :
           - Extraire le symbole de trading (ex: XAUUSD, EURUSD, GBPUSD, etc.)
        
        3. Pour le SENS :
           - Doit être "BUY" ou "SELL" en majuscules
           - Identifié à partir des mots-clés : buy, long, achat → "BUY" | sell, short, vente → "SELL"
           - Si aucun sens n'est identifiable, déduire le sens par rapport aux prix d'entrée, TPs et SL. Si ce n'est pas identifiable, retourner "None".
        
        4. Pour les PRIX D'ENTRÉE :
           - Si fourchette (ex: "3279-76", "3385-87", "3355 3357") : extraire min et max
             ATTENTION : "3279-76" signifie min=3276, max=3279 (pas 76!)
             Retourner [min, max] dans l'ordre croissant
           - Si prix unique : retourner [prix]
        
        5. Pour le STOP LOSS :
           - Extraire la valeur du SL telle qu'elle est donnée
           - IMPORTANT: La valeur du SL doit TOUJOURS être un nombre positif (ignorer tout signe négatif)
           - Si partielle (ex: "sl 70"), il faut partir du principe que c'est les dizaines, et il faut donc reconstruire le SL avec le nombre le plus proche du prix d'entrée. Ainsi ici le nombre le plus proche avec 70 si 3279 est l'entrée est 3270
           - Si complète (ex: "sl 3270.5"), la retourner telle quelle
        
        6. Pour les TAKE PROFITS :
           - Extraire TOUS les TPs mentionnés dans l'ordre
           - IMPORTANT: Les valeurs des TPs doivent TOUJOURS être des nombres positifs (ignorer tout signe négatif)
           - Si un TP est "open", le retourner comme string "open"
           - Sinon retourner comme valeur numérique
           - Si partiels (ex: "tp1 88", "tp2 04"), les reconstruire de la même manière que le SL vis à vis du point d'entrée. Donc si point entrée est 3279, le nombre le plus proche avec 88 est 3288
           -Si les TP sont données sous cette forme "TP 20 40 60 80 100 200 500 PIPS OPEN" ou "TP 20 40 60 80 100 200 PIPS OPEN", il faut ignoré et calculer à la place 4 tp :tp1 = prix d'entrée + distance du SL/2, prix d'entrée + distance du SL, prix d'entrée + distance du SL*1.5 et enfin prix d'entrée + distance du sl*3. Et bien sur en - pour un sell, en + pour un buy. Distance du SL est = valeur aboslue (Prix entrée - SL)
        
        Format de sortie STRICT :
        {{
          "author": "string",
          "symbol": "string", 
          "sens": "BUY"|"SELL",
          "entries": [float, ...],
          "sl": float|string,
          "tps": [float|string, ...]
        }}
        Ne renvoyez QUE le JSON, sans explication ni texte supplémentaire.
        
        Message à analyser :
        {message}
        
        Auteur du message : {author}
        """
    
    def parse_with_ai(self, text: str, author: str) -> Optional[Dict]:
        """
        Parse signal using Gemini AI
        
        Args:
            text: The message text to parse
            author: The author of the message
            
        Returns:
            Parsed signal data or None if parsing fails
        """
        try:
            # Prepare the prompt
            prompt = self.prompt_template.format(
                message=text,
                author=author
            )
            
            # Call Gemini API
            logger.debug(f"Calling Gemini AI for signal parsing")
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Clean response if needed (remove markdown code blocks)
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Parse JSON
            signal_data = json.loads(response_text)
            
            # Validate required fields
            required_fields = ['author', 'symbol', 'sens', 'entries', 'sl', 'tps']
            for field in required_fields:
                if field not in signal_data:
                    logger.error(f"Missing required field '{field}' in AI response")
                    return None
            
            # Convert direction
            direction = 0 if signal_data['sens'].upper() == 'BUY' else 1
            
            # Ensure entries is a list
            entries = signal_data['entries']
            if not isinstance(entries, list):
                entries = [entries]
            
            # Convert string numbers to float where possible
            processed_entries = []
            for entry in entries:
                if isinstance(entry, str):
                    if entry.lower() == 'open':
                        processed_entries.append('open')
                    else:
                        try:
                            processed_entries.append(float(entry))
                        except ValueError:
                            processed_entries.append(entry)
                else:
                    processed_entries.append(float(entry))
            
            # Process SL
            sl = signal_data['sl']
            if isinstance(sl, str) and sl.lower() != 'open':
                try:
                    sl = float(sl)
                except ValueError:
                    pass
            elif isinstance(sl, (int, float)):
                sl = float(sl)
            
            # Process TPs
            processed_tps = []
            for tp in signal_data['tps']:
                if isinstance(tp, str):
                    if tp.lower() == 'open':
                        processed_tps.append('open')
                    else:
                        try:
                            processed_tps.append(float(tp))
                        except ValueError:
                            processed_tps.append(tp)
                else:
                    processed_tps.append(float(tp))
            
            # Return formatted data
            result = {
                "direction": direction,
                "entries": processed_entries,
                "sl": sl,
                "tps": processed_tps,
                "symbol": signal_data['symbol'].upper(),
                "author": author,
                "ai_parsed": True
            }
            
            logger.info(f"AI parsed signal - Symbol: {result['symbol']}, "
                       f"Direction: {signal_data['sens']}, Entries: {result['entries']}, "
                       f"SL: {result['sl']}, TPs: {result['tps']}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"AI response was: {response_text if 'response_text' in locals() else 'No response'}")
            return None
        except Exception as e:
            logger.error(f"Error in AI signal parsing: {e}")
            return None
    
    def should_use_ai(self, author: str, symbol: Optional[str], entry_price: Optional[float]) -> bool:
        """
        Determine if AI parsing should be used
        
        Rules:
        - All Fortune signals use AI
        - ICM signals that are not XAUUSD use AI
        
        Args:
            author: Message author
            symbol: Detected symbol (if any)
            entry_price: Entry price (if detected)
            
        Returns:
            True if AI should be used, False otherwise
        """
        author_lower = author.lower() if author else ""
        
        # All Fortune signals use AI
        if 'fortune' in author_lower:
            logger.debug("Using AI for Fortune signal")
            return True
        
        # ICM signals
        if 'icm' in author_lower:
            # If symbol found and it's not XAUUSD, use AI
            if symbol and symbol != "XAUUSD":
                logger.debug(f"Using AI for ICM signal with symbol {symbol}")
                return True
            
            # If no symbol found and price not in XAUUSD range, use AI
            if not symbol and entry_price:
                if not (3000 <= entry_price <= 4000):
                    logger.debug(f"Using AI for ICM signal with price {entry_price} outside XAUUSD range")
                    return True
        
        return False