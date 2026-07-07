import time
import threading
import telepot
from flask import Flask

CONFIG = {
    "TELEGRAM_TOKEN": "8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys",
    "CHAT_ID": "2047038250",
    "RVOL_THRESHOLD": 2.2,
    "PRICE_MIN": 2.0,
    "PRICE_MAX": 22.0
}

app = Flask(__name__)

class GestorFrancotirador:
    def __init__(self):
        self.bot = telepot.Bot(CONFIG["TELEGRAM_TOKEN"])
        self.posiciones = {} 
        self.enviar("🎯 SISTEMA DE ALTA PROBABILIDAD (Fuerza Institucional) ACTIVO.")

    def enviar(self, mensaje):
        try:
            self.bot.sendMessage(CONFIG["CHAT_ID"], mensaje, parse_mode='Markdown')
        except Exception as e:
            print(f"Error Telegram: {e}")

    def escanear_fuerza_institucional(self):
        """
        Lógica para detectar acciones calientes:
        Busca activos con RVOL > 2.2, rango $2-$22 y momentum sectorial.
        """
        # Aquí se ejecutaría tu lógica de escáner contra una API (ej. yfinance o similar)
        # El bot filtra los activos que están siendo "comprados" por instituciones
        pass

    def gestionar_posicion(self, ticker, precio_actual):
        if ticker in self.posiciones:
            pos = self.posiciones[ticker]
            # Gestión de Trailing Stop dinámico
            if precio_actual > pos['max']:
                pos['max'] = precio_actual
                pos['stop'] = precio_actual * 0.92 # Ajuste de trailing al 8%
                rendimiento = ((precio_actual - pos['entrada']) / pos['entrada']) * 100
                self.enviar(f"🔄 *UPDATE {ticker}*\n"
                            f"📍 Nuevo Trailing Stop: ${pos['stop']:.2f}\n"
                            f"📈 Rendimiento: {rendimiento:.2f}%")

    def ejecutar(self):
        # 1. Escanear mercado buscando anomalías de volumen (RVOL > 2.2)
        # 2. Filtrar por rango $2-$22 (Rango de aceleración explosiva)
        # 3. Identificar si pertenecen a sectores con "Smart Money"
        
        # Ejemplo: Si se cumple la condición de fuerza, se abre posición:
        # self.posiciones[ticker] = {'entrada': p, 'stop': p*0.85, 'max': p}
        # self.enviar(f"🚀 *OPORTUNIDAD DETECTADA*: {ticker} (Fuerza Institucional)")
        pass

@app.route('/')
def home():
    return "Bot de Trading - Operativo"

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    gestor = GestorFrancotirador()
    while True:
        gestor.ejecutar()
        time.sleep(15)
