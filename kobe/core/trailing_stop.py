import time
from kobe.execution.binance_spot import BinanceSpot
from kobe.core.executor import get_open_positions, update_position_stop

def process_trailing_stops():
    """
    Parcourt les positions ouvertes et ajuste dynamiquement le Stop Loss sur Binance
    si le prix évolue en notre faveur.
    """
    positions = get_open_positions()
    if not positions:
        return

    ex = BinanceSpot()

    for pos in positions:
        # On ignore le paper trading pour l'API Binance
        if pos.get("mode") != "live":
            continue

        symbol = pos["symbol"]
        side = pos["side"]
        entry = float(pos["entry"])
        current_stop = float(pos["stop"])
        take = float(pos.get("take", 0))
        qty = float(pos["qty"])

        # 1. Obtenir le prix actuel
        price_info = ex.get_price(symbol)
        if "error" in price_info:
            continue
        
        current_price = float(price_info["price"])
        new_stop = current_stop
        
        # 2. Règle mathématique : Activation à +1.5% de profit, stop suit à 1%
        if side == "long":
            profit_pct = (current_price - entry) / entry
            if profit_pct >= 0.015:
                calculated_stop = current_price * 0.99
                if calculated_stop > current_stop:
                    # Arrondi à 2 décimales pour respecter le format prix de Binance (BTC/ETH/SOL)
                    new_stop = round(calculated_stop, 2) 
        else: # short
            profit_pct = (entry - current_price) / entry
            if profit_pct >= 0.015:
                calculated_stop = current_price * 1.01
                if calculated_stop < current_stop or current_stop == 0:
                    new_stop = round(calculated_stop, 2)

        # 3. Application si le Stop doit être remonté
        if new_stop != current_stop:
            print(f"🔄 Trailing Stop {symbol} : Remontée du stop {current_stop} -> {new_stop} (Prix actuel: {current_price})")

            # A. Nettoyage : Annuler tous les anciens ordres liés à ce trade (TP et SL)
            ex._signed_delete("/api/v3/openOrders", {"symbol": symbol})
            
            # Pause de 500ms pour garantir que Binance a bien libéré le capital verrouillé
            time.sleep(0.5) 

            close_side = "SELL" if side == "long" else "BUY"

            # B. Replacer le Take Profit initial
            if take > 0:
                ex._signed_post("/api/v3/order", {
                    "symbol": symbol,
                    "side": close_side,
                    "type": "LIMIT",
                    "timeInForce": "GTC",
                    "quantity": qty,
                    "price": take
                })

            # C. Placer le nouveau Stop Loss actualisé
            ex._signed_post("/api/v3/order", {
                "symbol": symbol,
                "side": close_side,
                "type": "STOP_LOSS_LIMIT",
                "timeInForce": "GTC",
                "quantity": qty,
                "price": new_stop,
                "stopPrice": new_stop
            })

            # D. Sauvegarde dans le journal
            update_position_stop(pos["id"], new_stop)