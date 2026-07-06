import os
import time
import random
import pandas as pd
from polygon import RESTClient
import telepot

# --- CONFIGURACIÓN ---
POLYGON_KEY = os.environ.get("POLYGON_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = RESTClient(POLYGON_KEY)
bot = telepot.Bot(TELEGRAM_TOKEN)

class GestorFrancotirador:
    def __init__(self):
        self.posiciones = {}
        bot.sendMessage(TELEGRAM_CHAT_ID, "🚀 BOT AUTOMÁTICO: Escaneando Mercado en Tiempo Real")

    def tiene_noticias_negativas(self, ticker):
        try:
            news = list(client.list_ticker_news(ticker, limit=3))
            palabras_negativas = ['lawsuit', 'investigation', 'fda rejection', 'layoff', 'down', 'loss', 'warning']
            for item in news:
                if any(word in item.title.lower() for word in palabras_negativas):
                    return True
            return False
        except: return False

    def calcular_atr(self, ticker):
        try:
            aggs = list(client.get_aggs(ticker, 1, "day", (pd.Timestamp.now() - pd.Timedelta(days=15)), pd.Timestamp.now()))
            if len(aggs) < 5: return 0.5
            df = pd.DataFrame(aggs)
            tr = df['high'] - df['low']
            return tr.tail(5).mean()
        except: return 0.5

    def ejecutar(self):
        # 1. GESTIÓN DE POSICIONES
        for ticker in list(self.posiciones.keys()):
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

        # 2. ESCÁNER AUTOMÁTICO (Solo si tenemos menos de 3 posiciones)
        if len(self.posiciones) < 3:
            try:
                # Obtener tickers activos (ajusta a la lista de tu interés o sectores específicos)
                tickers = [t.ticker for t in client.list_tickers(market="stocks", limit=50)]
                muestra = random.sample(tickers, min(len(tickers), 20))
                
                for ticker in muestra:
                    if ticker in self.posiciones or ticker.endswith('W'): continue
                    
                    quote = client.get_last_quote(ticker)
                    heat = quote.bid_size / (quote.bid_size + quote.ask_size + 1e-9)
                    
                    if heat > 0.85 and 2.00 <= quote.bid_price <= 20.00 and not self.tiene_noticias_negativas(ticker):
                        atr = self.calcular_atr(ticker)
                        self.posiciones[ticker] = {
                            'entrada': quote.bid_price,
                            'sl': quote.bid_price - (atr * 1.5),
                            'max_price': quote.bid_price
                        }
                        bot.sendMessage(TELEGRAM_CHAT_ID, f"🔥 OPORTUNIDAD AUTOMÁTICA: {ticker}\nPrecio: ${quote.bid_price:.2f}\nHeat Score: {heat:.2f}")
                        break
            except Exception as e: print(f"Error escaneo: {e}")

if __name__ == "__main__":
    gestor = GestorFrancotirador()
    while True:
        gestor.ejecutar()
        time.sleep(15) # Pausa para no saturar los límites de la API
