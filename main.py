import os
import time
import pandas as pd
from polygon import RESTClient
import telepot

# --- CONFIGURACIÓN ---
# Render leerá estas variables desde la sección "Environment Variables"
POLYGON_KEY = os.environ.get("POLYGON_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
WATCHLIST = ["IOVA", "CRDF", "HUMA", "ALT", "IREN"]

client = RESTClient(POLYGON_KEY)
bot = telepot.Bot(TELEGRAM_TOKEN)

class GestorFrancotirador:
    def __init__(self):
        self.posiciones = {}
        bot.sendMessage(TELEGRAM_CHAT_ID, "🚀 BOT REFINADO: Modo Institucional Activo")

    def tiene_noticias_negativas(self, ticker):
        try:
            news = list(client.list_ticker_news(ticker, limit=5))
            palabras_negativas = ['lawsuit', 'investigation', 'fda rejection', 'layoff', 'down', 'loss']
            for item in news:
                title = item.title.lower()
                if any(word in title for word in palabras_negativas):
                    return True
            return False
        except: return False

    def calcular_atr(self, ticker):
        aggs = list(client.get_aggs(ticker, 1, "day", (pd.Timestamp.now() - pd.Timedelta(days=15)), pd.Timestamp.now()))
        if len(aggs) < 5: return 0.5
        df = pd.DataFrame(aggs)
        tr = df['high'] - df['low']
        return tr.tail(5).mean()

    def ejecutar(self):
        for ticker in WATCHLIST:
            # --- LÓGICA DE ENTRADA ---
            if ticker not in self.posiciones:
                try:
                    quote = client.get_last_quote(ticker)
                    heat = quote.bid_size / (quote.bid_size + quote.ask_size + 1e-9)
                    
                    if heat > 0.75 and not self.tiene_noticias_negativas(ticker):
                        atr = self.calcular_atr(ticker)
                        precio = quote.bid_price
                        self.posiciones[ticker] = {
                            'entrada': precio,
                            'sl': precio - (atr * 1.5),
                            'max_price': precio
                        }
                        bot.sendMessage(TELEGRAM_CHAT_ID, f"🎯 ENTRADA: {ticker} @ {precio:.2f}\nSL Inicial: {self.posiciones[ticker]['sl']:.2f}")
                except Exception as e: print(f"Error entrada {ticker}: {e}")

            # --- LÓGICA DE SALIDA Y TRAILING STOP ---
            else:
                try:
                    trade = client.get_last_trade(ticker)
                    pos = self.posiciones[ticker]
                    
                    if trade.price > pos['max_price']:
                        pos['max_price'] = trade.price
                        atr = self.calcular_atr(ticker)
                        nuevo_sl = trade.price - (atr * 1.5)
                        if nuevo_sl > pos['sl']:
                            pos['sl'] = nuevo_sl
                            bot.sendMessage(TELEGRAM_CHAT_ID, f"📈 MOVIMIENTO SL: {ticker}\nNuevo SL: {pos['sl']:.2f}")

                    if trade.price <= pos['sl']:
                        rendimiento = ((trade.price - pos['entrada']) / pos['entrada']) * 100
                        bot.sendMessage(TELEGRAM_CHAT_ID, f"🛑 SALIDA: {ticker}\nRendimiento: {rendimiento:.2f}%")
                        del self.posiciones[ticker]
                except Exception as e: print(f"Error gestión {ticker}: {e}")

if __name__ == "__main__":
    gestor = GestorFrancotirador()
    while True:
        gestor.ejecutar()
        time.sleep(10)
          
