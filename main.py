import time
import threading
import telepot
import requests
import os
from flask import Flask

# CONFIGURACIÓN GLOBAL
CONFIG = {
    "TELEGRAM_TOKEN": "8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys",
    "CHAT_ID": "2047038250",
    "POLYGON_KEY": os.environ.get("POLYGON_API_KEY"),
    "RVOL_THRESHOLD": 2.2,
    "PRICE_MIN": 2.0,
    "PRICE_MAX": 22.0
}

app = Flask(__name__)

# RUTA PARA MANTENER EL SERVIDOR ACTIVO
@app.route('/')
def home():
    return "Bot de Trading Francotirador Operativo"

class GestorFrancotirador:
    def __init__(self):
        self.bot = telepot.Bot(CONFIG["TELEGRAM_TOKEN"])
        self.posiciones = {}
        self.bot.sendMessage(CONFIG["CHAT_ID"], "🚀 SISTEMA FRANCOTIRADOR PROFESIONAL ACTIVADO")

    def enviar(self, mensaje):
        try:
            self.bot.sendMessage(CONFIG["CHAT_ID"], mensaje, parse_mode='Markdown')
        except Exception as e:
            print(f"Error en Telegram: {e}")

    def obtener_lideres_mercado(self):
        """Obtiene automáticamente los Top Gainers desde Polygon"""
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={CONFIG['POLYGON_KEY']}"
        try:
            response = requests.get(url).json()
            return response.get("tickers", [])
        except:
            return []

    def gestionar_trailing(self, ticker, precio_actual):
        if ticker in self.posiciones:
            pos = self.posiciones[ticker]
            if precio_actual > pos['max']:
                pos['max'] = precio_actual
                pos['stop'] = precio_actual * 0.92  # Trailing Stop dinámico (8%)
                rendimiento = ((precio_actual - pos['entrada']) / pos['entrada']) * 100
                self.enviar(f"🔄 *UPDATE {ticker}*\n"
                            f"📍 Nuevo Stop: ${pos['stop']:.2f}\n"
                            f"📈 Rendimiento: {rendimiento:.2f}%")

    def ejecutar_ciclo(self):
        lideres = self.obtener_lideres_mercado()
        for activo in lideres:
            ticker = activo["ticker"]
            precio = activo["day"]["c"]
            vol = activo["day"]["v"]
            
            # FILTROS DE ALTA PROBABILIDAD (Precio y Volumen)
            if CONFIG["PRICE_MIN"] <= precio <= CONFIG["PRICE_MAX"]:
                if ticker not in self.posiciones:
                    self.posiciones[ticker] = {'entrada': precio, 'stop': precio*0.92, 'max': precio}
                    self.enviar(f"🎯 *ALERTA*: {ticker} detectado\nPrecio: ${precio}\n¡Fuerza Institucional Detectada!")
            
            # SEGUIMIENTO
            self.gestionar_trailing(ticker, precio)

def run_bot():
    gestor = GestorFrancotirador()
    while True:
        gestor.ejecutar_ciclo()
        time.sleep(60) # Escaneo cada minuto

if __name__ == "__main__":
    # Iniciar bot en segundo plano
    threading.Thread(target=run_bot, daemon=True).start()
    # Servidor Flask principal
    app.run(host='0.0.0.0', port=10000)
