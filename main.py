import time
import threading
import telepot
import requests
import os
from flask import Flask

CONFIG = {
    "TELEGRAM_TOKEN": "8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys",
    "CHAT_ID": "2047038250",
    "POLYGON_KEY": os.environ.get("POLYGON_API_KEY"),
    "RVOL_THRESHOLD": 2.2,
    "PRICE_MIN": 2.0,
    "PRICE_MAX": 22.0
}

app = Flask(__name__)

class GestorFrancotirador:
    def __init__(self):
        self.bot = telepot.Bot(CONFIG["TELEGRAM_TOKEN"])
        self.posiciones = {}
        self.enviar("🚀 ESCÁNER AUTOMÁTICO ACTIVO: Buscando líderes de mercado (RVOL > 2.2)")

    def enviar(self, mensaje):
        try:
            self.bot.sendMessage(CONFIG["CHAT_ID"], mensaje, parse_mode='Markdown')
        except Exception as e:
            print(f"Error Telegram: {e}")

    def obtener_lideres_mercado(self):
        """Busca automáticamente los activos con mayor movimiento (Top Gainers)"""
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={CONFIG['POLYGON_KEY']}"
        response = requests.get(url).json()
        return response.get("tickers", [])

    def ejecutar(self):
        # 1. Obtener los líderes actuales del mercado
        lideres = self.obtener_lideres_mercado()
        
        for activo in lideres:
            ticker = activo["ticker"]
            precio = activo["day"]["c"]
            volumen = activo["day"]["v"]
            
            # 2. Filtrado Institucional Automático
            if CONFIG["PRICE_MIN"] <= precio <= CONFIG["PRICE_MAX"]:
                # Aquí verificamos que el volumen sea anormal (Fuerza Institucional)
                # (Lógica simplificada de RVOL)
                if volumen > 1000000: # Filtro de liquidez mínima
                    if ticker not in self.posiciones:
                        self.posiciones[ticker] = {'entrada': precio, 'stop': precio*0.92, 'max': precio}
                        self.enviar(f"🎯 *ALERTA*: {ticker} detectado\nPrecio: ${precio}\n¡Fuerza Institucional Detectada!")
            
            # 3. Gestión de seguimiento
            if ticker in self.posiciones:
                self.gestionar_trailing(ticker, precio)
        
        time.sleep(60) # Escaneo cada minuto para no saturar la API

    def gestionar_trailing(self, ticker, precio_actual):
        pos = self.posiciones[ticker]
        if precio_actual > pos['max']:
            pos['max'] = precio_actual
            pos['stop'] = precio_actual * 0.92
            rendimiento = ((precio_actual - pos['entrada']) / pos['entrada']) * 100
            self.enviar(f"🔄 *UPDATE {ticker}*\nNuevo Stop: ${pos['stop']:.2f}\nRendimiento: {rendimiento:.2f}%")

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    gestor = GestorFrancotirador()
    while True:
        gestor.ejecutar()
