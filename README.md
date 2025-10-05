# Trading Signal Copier

Robot de trading automatisé qui copie les signaux Telegram vers MetaTrader 5 en temps réel.

## Comment fonctionne le robot ?

Ce robot de trading automatisé transforme votre expérience de trading en copiant instantanément les signaux de vos canaux Telegram préférés directement sur votre compte MetaTrader 5. Voici exactement ce qui se passe lorsque vous l'activez :

**Surveillance continue de vos canaux Telegram**
Dès que le robot est lancé, il se connecte à vos canaux Telegram configurés et reste en écoute permanente. Il analyse chaque message entrant pour détecter automatiquement les signaux de trading valides. Le robot reconnaît différents formats de signaux : ceux d'ICM avec leurs take profits fixes, les signaux Fortune qui couvrent plusieurs symboles, et les signaux standards avec leurs configurations personnalisées.

**Analyse intelligente et placement d'ordres**
Lorsqu'un signal valide est détecté, le robot effectue immédiatement une analyse du marché. Il compare le prix d'entrée du signal avec le prix actuel du marché pour déterminer la meilleure stratégie d'exécution. Si le prix actuel est proche du prix d'entrée (dans une tolérance dynamique calculée comme un pourcentage du prix d'entrée - par exemple 0.7 points pour un prix de 3600 sur le XAUUSD), le robot place un ordre au marché pour une exécution immédiate. Si le prix est éloigné, il place un ordre limite au prix d'entrée spécifié. Cette logique garantit que vous ne manquez jamais une opportunité tout en respectant les paramètres du signal.

**Gestion multi-positions pour maximiser les profits**
Pour chaque signal reçu, le robot ne place pas un seul ordre, mais crée une position séparée pour chaque take profit mentionné dans le signal. Par exemple, si un signal contient 4 take profits, vous aurez 4 positions distinctes, chacune avec son propre objectif de profit. Cette approche vous permet de sécuriser des gains progressifs : vous pouvez prendre des bénéfices au premier TP tout en laissant les autres positions courir vers des profits plus importants. Chaque position est étiquetée avec un commentaire unique contenant l'ID du signal original, permettant un suivi parfait.

**Protection automatique avec le break-even**
Le robot surveille en permanence vos positions ouvertes. Dès que le prix atteint votre premier take profit (TP1), il modifie automatiquement le stop loss de toutes vos positions liées à ce signal pour le placer au point d'entrée. Cette fonctionnalité révolutionnaire garantit que vous ne perdrez jamais d'argent une fois que le marché a bougé en votre faveur. Vos profits sont sécurisés automatiquement sans aucune intervention de votre part.

**Contrôle interactif via Telegram**
Le robot vous offre un contrôle total sur vos positions directement depuis Telegram. Vous pouvez répondre à n'importe quel signal avec des commandes simples : "Cloturez now" ferme immédiatement toutes les positions liées à ce signal, "breakeven" force le déplacement du stop loss au point d'entrée, et "prendre tp1 now" ferme uniquement la position du premier take profit. Cette interactivité vous permet de réagir rapidement aux conditions de marché changeantes.

**Gestion intelligente des expirations**
Tous les ordres en attente sont automatiquement configurés avec des temps d'expiration appropriés. Les ordres ICM et standards expirent après 12 minutes, tandis que les signaux Fortune suivent leur propre temporisation. Le robot calcule automatiquement le décalage horaire entre votre système et le serveur MetaTrader 5 pour garantir une synchronisation parfaite des expirations.

**Sécurité et fiabilité**
Le robot intègre de nombreuses protections : vérification de la validité des prix, annulation automatique des ordres si le stop loss est déjà atteint, gestion complète des erreurs avec logs détaillés, et compatibilité avec tous les brokers MetaTrader 5. Chaque action est tracée et documentée pour un suivi transparent de toutes les opérations.

En résumé, ce robot transforme votre trading en automatisant complètement le processus de copie des signaux tout en vous laissant le contrôle final sur vos positions. Il combine la rapidité d'exécution automatique avec la flexibilité du contrôle manuel, vous offrant le meilleur des deux mondes pour optimiser vos performances de trading.

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
