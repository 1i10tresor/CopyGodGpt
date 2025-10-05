# Trading Signal Copier

Robot de trading automatisé qui copie les signaux Telegram vers MetaTrader 5 en temps réel.

## 🚀 Fonctionnement du Robot

### 📱 Écoute des Signaux Telegram
Le robot surveille en permanence vos canaux Telegram configurés et détecte automatiquement :
- **Signaux ICM** : Format spécialisé avec TPs fixes (+2, +5, +8, +200)
- **Signaux Fortune** : Multi-symboles avec TPs variables + "open"
- **Signaux par défaut** : Format standard avec TPs calculés (+2, +4, +6, "open")

### 🎯 Placement Intelligent des Ordres
Le robot analyse le prix actuel vs le prix d'entrée du signal :
- **Ordre au marché** : Si le prix est proche de l'entrée (tolérance de 0.7 points)
- **Ordre limite** : Si le prix est éloigné de l'entrée
- **Annulation automatique** : Si le prix a dépassé le stop loss

### 📊 Gestion Multi-TP
Pour chaque signal, le robot place **un ordre séparé pour chaque Take Profit** :
- TP1, TP2, TP3 : Ordres avec prix fixes
- TP4 "open" : Ordre sans TP (profit illimité)
- **Commentaire unique** : Chaque ordre contient l'ID du signal + valeur TP1

### ⚡ Break-Even Automatique
Le robot surveille vos positions en continu :
- **Détection TP1** : Quand le prix atteint le premier Take Profit
- **Modification SL** : Déplace automatiquement le Stop Loss au point d'entrée
- **Protection garantie** : Aucune perte possible une fois TP1 atteint

### 🎮 Commandes de Gestion Interactive
Répondez directement aux signaux Telegram pour contrôler vos ordres :
- **"Cloturez now"** → Ferme tous les ordres du signal
- **"breakeven"** → Force le break-even sur toutes les positions
- **"prendre tp1 now"** → Ferme uniquement la position TP1

### 🔄 Expiration Intelligente
Les ordres en attente expirent automatiquement :
- **ICM & Défaut** : 12 minutes (720 secondes)
- **Fortune** : 12 minutes (720 secondes)
- **Synchronisation serveur** : Calcul automatique du décalage horaire MT5

## ✨ Avantages Clés

- ✅ Automatic signal detection from Telegram channels
- ✅ **Réaction instantanée** : Ordres placés en moins de 2 secondes
- ✅ **Gestion du risque** : Break-even automatique + expiration des ordres
- ✅ **Multi-symboles** : XAUUSD, EURUSD, indices, matières premières...
- ✅ **Contrôle total** : Commandes interactives via Telegram
- ✅ **Fiabilité** : Gestion d'erreurs complète + logs détaillés
- ✅ **Compatibilité** : Fonctionne avec tous les brokers MT5

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
