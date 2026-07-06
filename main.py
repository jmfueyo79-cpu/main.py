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

# --- SERVIDOR FLASK ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Activo"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))), daemon=True).start()

class GestorFrancotirador:
    def __init__(self):
        self.posiciones = {}
        self.candidatos_espera = {}
        bot.sendMessage(TELEGRAM_CHAT_ID, "🚀 BOT PROFESIONAL: Trailing Stop + Confirmación 5min Activo")

    def ejecutar(self):
        # 1. GESTIÓN DE POSICIONES (TRAILING STOP Y AVISOS)
        for ticker in list(self.posiciones.keys()):
            try:
                trade = client.get_last_trade(ticker)
                pos = self.posiciones[ticker]
                
                # Si el precio sube, actualizamos el Stop Loss dinámicamente
                if trade.price > pos['max_price']:
                    pos['max_price'] = trade.price
                    nuevo_sl = trade.price - (pos['atr'] * 1.5)
                    
                    if nuevo_sl > pos['sl']:
                        pos['sl'] = nuevo_sl
                        ganancia_latente = ((trade.price - pos['entrada']) / pos['entrada']) * 100
                        bot.sendMessage(TELEGRAM_CHAT_ID, 
                            f"📈 TRAILING STOP: {ticker}\n"
                            f"Nuevo SL: ${pos['sl']:.2f}\n"
                            f"Ganancia Latente: {ganancia_latente:.2f}%")

                # Salida por Stop Loss
                if trade.price <= pos['sl']:
                    rendimiento = ((trade.price - pos['entrada']) / pos['entrada']) * 100
                    bot.sendMessage(TELEGRAM_CHAT_ID, f"🛑 SALIDA: {ticker}\nRendimiento Final: {rendimiento:.2f}%")
                    del self.posiciones[ticker]
            except: pass

        # 2. CONFIRMACIÓN DE ENTRADAS (5 MIN)
        for ticker in list(self.candidatos_espera.keys()):
            try:
                trade = client.get_last_trade(ticker)
                info = self.candidatos_espera[ticker]
                if trade.price > info['trigger_price']:
                    # ATR simplificado para el cálculo
                    atr = 0.5 
                    self.posiciones[ticker] = {
                        'entrada': trade.price, 
                        'sl': trade.price - (atr * 1.5), 
                        'max_price': trade.price,
                        'atr': atr
                    }
                    bot.sendMessage(TELEGRAM_CHAT_ID, f"✅ ENTRADA CONFIRMADA: {ticker}\nPrecio: ${trade.price:.2f}")
                    del self.candidatos_espera[ticker]
                elif time.time() - info['timestamp'] > 300:
                    del self.candidatos_espera[ticker]
            except: pass

        # 3. ESCÁNER
        if len(self.posiciones) + len(self.candidatos_espera) < 3:
            try:
                tickers = [t.ticker for t in client.list_tickers(market="stocks", limit=50)]
                for ticker in random.sample(tickers, min(len(tickers), 10)):
                    if ticker in self.posiciones or ticker in self.candidatos_espera or ticker.endswith('W'): continue
                    
                    # Verificación RVOL simplificada
                    quote = client.get_last_quote(ticker)
                    if 2.00 <= quote.bid_price <= 20.00:
                        self.candidatos_espera[ticker] = {'trigger_price': quote.bid_price, 'timestamp': time.time()}
                        bot.sendMessage(TELEGRAM_CHAT_ID, f"👀 VIGILANDO {ticker}\nEsperando rotura de ${quote.bid_price:.2f}")
            except: pass

if __name__ == "__main__":
    gestor = GestorFrancotirador()
    while True:
        gestor.ejecutar()
        time.sleep(15)
                    
