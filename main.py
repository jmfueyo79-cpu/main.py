import time
import threading
import telepot
import requests
import os
from flask import Flask

app = Flask(__name__)

# CONFIGURACIÓN DEFINITIVA DE ALTA PROBABILIDAD
CONFIG = {
    "TELEGRAM_TOKEN": "8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys",
    "CHAT_ID": "2047038250",
    "POLYGON_KEY": os.environ.get("POLYGON_API_KEY"),
    "PRICE_RANGE": (2.0, 22.0),
    "MIN_VOLUMEN": 1500000, 
    "TRAILING_STOP_PCT": 0.08  # Trailing stop del 8% para proteger beneficio
}

class FrancotiradorElite:
    def __init__(self):
        self.bot = telepot.Bot(CONFIG["TELEGRAM_TOKEN"])
        self.posiciones = {} # Seguimiento activo de activos detectados
        self.bot.sendMessage(CONFIG["CHAT_ID"], "🎯 SISTEMA ÉLITE: ESCANEANDO RUPTURAS CON ALTO VOLUMEN")

    def gestionar_trailing(self, ticker, precio_actual):
        """Ajusta el stop automáticamente al subir el precio"""
        if ticker in self.posiciones:
            pos = self.posiciones[ticker]
            if precio_actual > pos['max']:
                pos['max'] = precio_actual
                pos['stop'] = precio_actual * (1 - CONFIG["TRAILING_STOP_PCT"])
                rendimiento = ((precio_actual - pos['entrada']) / pos['entrada']) * 100
                self.bot.sendMessage(CONFIG["CHAT_ID"], 
                    f"🚀 *UPDATE {ticker}*\n"
                    f"📍 Nuevo Stop (Protegiendo): ${pos['stop']:.2f}\n"
                    f"📈 Rendimiento Actual: {rendimiento:.2f}%")

    def ejecutar_analisis(self):
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={CONFIG['POLYGON_KEY']}"
        try:
            data = requests.get(url).json().get("tickers", [])
            for stock in data:
                ticker = stock["ticker"]
                precio = stock["day"]["c"]
                volumen = stock["day"]["v"]
                cambio = stock["day"]["p"]

                # 1. FILTROS DE ENTRADA (Alta Convicción)
                if (CONFIG["PRICE_RANGE"][0] <= precio <= CONFIG["PRICE_RANGE"][1] and 
                    volumen >= CONFIG["MIN_VOLUMEN"] and 
                    cambio >= 7.0):
                    
                    if ticker not in self.posiciones:
                        self.posiciones[ticker] = {'entrada': precio, 'stop': precio * 0.90, 'max': precio}
                        self.bot.sendMessage(CONFIG["CHAT_ID"], 
                            f"🔥 *ALERTA DE RUPTURA INSTITUCIONAL*\n"
                            f"Ticker: {ticker}\n"
                            f"Precio: ${precio:.2f} | Subida: {cambio}%\n"
                            f"Volumen: {volumen:,}\n"
                            f"Objetivo: Maximizar rendimiento (>50%)")
                
                # 2. SEGUIMIENTO ACTIVO
                self.gestionar_trailing(ticker, precio)

        except Exception as e:
            print(f"Error de escaneo: {e}")

    def loop(self):
        while True:
            self.ejecutar_analisis()
            time.sleep(120)

if __name__ == "__main__":
    threading.Thread(target=FrancotiradorElite().loop, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
