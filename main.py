import time
import threading
import telepot
import requests
import os
import json
from flask import Flask

# --- CONFIGURACIÓN ---
app = Flask(__name__)
TOKEN = "8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys"
CHAT_ID = "2047038250"
POLYGON_KEY = os.environ.get("POLYGON_API_KEY")
ARCHIVO_POSICIONES = "posiciones.json"

class FrancotiradorEquilibrio:
    def __init__(self):
        self.bot = telepot.Bot(TOKEN)
        self.posiciones = self.cargar_posiciones()
        self.enviar_telegram("🎯 SISTEMA EQUILIBRIO ACTIVADO: FILTROS INTERMEDIOS + PERSISTENCIA")

    def cargar_posiciones(self):
        if os.path.exists(ARCHIVO_POSICIONES):
            try:
                with open(ARCHIVO_POSICIONES, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def guardar_posiciones(self):
        with open(ARCHIVO_POSICIONES, "w") as f:
            json.dump(self.posiciones, f)

    def enviar_telegram(self, mensaje):
        try:
            self.bot.sendMessage(CHAT_ID, mensaje, parse_mode='Markdown')
        except Exception as e:
            print(f"Error Telegram: {e}")

    def gestionar_trailing(self, ticker, precio_actual):
        if ticker in self.posiciones:
            pos = self.posiciones[ticker]
            if precio_actual > pos['max']:
                pos['max'] = precio_actual
                pos['stop'] = precio_actual * 0.92  # Trailing stop del 8%
                self.guardar_posiciones() # Persistencia tras cada actualización
                rendimiento = ((precio_actual - pos['entrada']) / pos['entrada']) * 100
                self.enviar_telegram(f"🚀 *UPDATE {ticker}*\n📍 Nuevo Stop: ${pos['stop']:.2f}\n📈 Rentabilidad: {rendimiento:.2f}%")

    def loop(self):
        while True:
            try:
                url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
                data = requests.get(url).json().get("tickers", [])
                
                for stock in data:
                    ticker = stock["ticker"]
                    precio = stock["day"]["c"]
                    volumen = stock["day"]["v"]
                    cambio = stock["day"]["p"]

                    # FILTROS DE EQUILIBRIO (500k volumen / 4% cambio)
                    if 2.0 <= precio <= 22.0 and volumen >= 500000 and cambio >= 4.0:
                        if ticker not in self.posiciones:
                            self.posiciones[ticker] = {'entrada': precio, 'stop': precio * 0.90, 'max': precio}
                            self.guardar_posiciones() # Guardar nueva posición
                            self.enviar_telegram(f"🔥 *ALERTA*: {ticker}\nPrecio: ${precio:.2f} | Cambio: {cambio}%\nVolumen: {volumen:,}")
                    
                    self.gestionar_trailing(ticker, precio)
            except Exception as e:
                print(f"Error en ciclo: {e}")
            time.sleep(120)

@app.route('/')
def home():
    return "Bot de Trading Activo - Persistencia OK"

if __name__ == "__main__":
    bot_instance = FrancotiradorEquilibrio()
    threading.Thread(target=bot_instance.loop, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
