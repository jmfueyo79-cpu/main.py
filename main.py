import os
import time
import random
import threading
from flask import Flask
from polygon import RESTClient
import telepot
import pandas as pd

# --- CONFIGURACIÓN ---
POLYGON_KEY = os.environ.get("POLYGON_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = RESTClient(POLYGON_KEY)
bot = telepot.Bot(TELEGRAM_TOKEN)

# --- SERVIDOR FLASK (Para mantener activo en Render) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Activo"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))), daemon=True).start()

class GestorFrancotirador:
    def __init__(self):
        self.posiciones = {}
        self.candidatos_espera = {}
        bot.sendMessage(TELEGRAM_CHAT_ID, "🚀 BOT DEFINITIVO: RVOL + Confirmación 5min Activo")

    def es_volumen_inusual(self, ticker):
        try:
            aggs = list(client.get_aggs(ticker, 1, "day", (pd.Timestamp.now() - pd.Timedelta(days=15)), pd.Timestamp.now()))
            if len(aggs) < 6: return False
            df = pd.DataFrame(aggs)
            return df['volume'].iloc[-1] > (df['volume'].iloc[-6:-1].mean() * 3)
        except: return False

    def ejecutar(self):
        # 1. GESTIÓN DE POSICIONES ACTIVAS
        for ticker in list(self.posiciones.keys()):
            try:
                trade = client.get_last_trade(ticker)
                pos = self.posiciones[ticker]
                if trade.price > pos['max_price']: pos['max_price'] = trade.price
                if trade.price <= pos['sl']:
                    bot.sendMessage(TELEGRAM_CHAT_ID, f"🛑 SALIDA: {ticker} | Rendimiento: {((trade.price - pos['entrada']) / pos['entrada']) * 100:.2f}%")
                    del self.posiciones[ticker]
            except: pass

        # 2. CONFIRMACIÓN DE ENTRADAS (Vigilancia de 5 min)
        for ticker in list(self.candidatos_espera.keys()):
            try:
                trade = client.get_last_trade(ticker)
                info = self.candidatos_espera[ticker]
                # Si el precio supera el nivel detectado, entramos
                if trade.price > info['trigger_price']:
                    atr = 0.5 # Ajusta según tu lógica de volatilidad
                    self.posiciones[ticker] = {'entrada': trade.price, 'sl': trade.price - (atr * 1.5), 'max_price': trade.price}
                    bot.sendMessage(TELEGRAM_CHAT_ID, f"✅ ENTRADA CONFIRMADA: {ticker}\nPrecio: ${trade.price:.2f}")
                    del self.candidatos_espera[ticker]
                # Si expira el tiempo
                elif time.time() - info['timestamp'] > 300:
                    del self.candidatos_espera[ticker]
            except: pass

        # 3. ESCÁNER
        if len(self.posiciones) + len(self.candidatos_espera) < 3:
            try:
                tickers = [t.ticker for t in client.list_tickers(market="stocks", limit=50)]
                for ticker in random.sample(tickers, min(len(tickers), 10)):
                    if ticker in self.posiciones or ticker in self.candidatos_espera or ticker.endswith('W'): continue
                    if not self.es_volumen_inusual(ticker): continue
                    
                    quote = client.get_last_quote(ticker)
                    if 2.00 <= quote.bid_price <= 20.00:
                        self.candidatos_espera[ticker] = {'trigger_price': quote.bid_price, 'timestamp': time.time()}
                        bot.sendMessage(TELEGRAM_CHAT_ID, f"👀 VIGILANDO {ticker}\nEsperando rotura de ${quote.bid_price:.2f} (Confirmación 5min)")
            except: pass

if __name__ == "__main__":
    gestor = GestorFrancotirador()
    while True:
        gestor.ejecutar()
        time.sleep(15)
                    
