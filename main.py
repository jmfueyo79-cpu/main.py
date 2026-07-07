import time
import threading
import telepot
import requests
import os
from flask import Flask

# --- CONFIGURACIÓN GLOBAL ---
CONFIG = {
    # Tokens de Telegram (Obtenidos de variables de entorno en Render)
    "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN"),
    "CHAT_ID": os.environ.get("CHAT_ID"),
    # API Key de Polygon
    "POLYGON_KEY": os.environ.get("POLYGON_API_KEY"),
    # Filtros de Alta Probabilidad (Rendimiento >50%)
    "RVOL_THRESHOLD": 2.2,    # Confirmación de fuerza institucional
    "PRICE_MIN": 2.0,         # Rango explosivo bajo
    "PRICE_MAX": 22.0         # Rango explosivo alto
}

app = Flask(__name__)

# --- INFRAESTRUCTURA: Servidor Web para mantener Render activo ---
@app.route('/')
def home():
    return "Bot Francotirador Operativo - Monitorizando Mercado"

class GestorFrancotirador:
    def __init__(self):
        self.bot = telepot.Bot(CONFIG["TELEGRAM_TOKEN"])
        self.posiciones = {} # Estructura: {'TICKER': {'entrada': P, 'stop': S, 'max': P}}
        self.enviar("🚀 SISTEMA DE ALTA PROBABILIDAD (POLYGON) ACTIVADO")

    def enviar(self, mensaje):
        try:
            self.bot.sendMessage(CONFIG["CHAT_ID"], mensaje, parse_mode='Markdown')
        except Exception as e:
            print(f"Error Telegram: {e}")

    def obtener_lideres_polygon(self):
        """
        Consulta la API de Polygon.io para obtener los Top Gainers del día.
        Esto permite al bot encontrar las acciones más calientes automáticamente.
        """
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={CONFIG['POLYGON_KEY']}"
        try:
            response = requests.get(url).json()
            # Retorna la lista de tickers que más suben
            return response.get("tickers", [])
        except Exception as e:
            print(f"Error conectando a Polygon: {e}")
            return []

    def gestionar_trailing(self, ticker, precio_actual):
        """
        Ajusta el Trailing Stop automáticamente cuando el precio sube.
        """
        if ticker in self.posiciones:
            pos = self.posiciones[ticker]
            # Si el precio actual es mayor al máximo histórico registrado en la operación
            if precio_actual > pos['max']:
                pos['max'] = precio_actual
                # Nuevo stop dinámico (ej. 8% por debajo del nuevo máximo)
                nuevo_stop = pos['max'] * 0.92 
                if nuevo_stop > pos['stop']:
                    pos['stop'] = nuevo_stop
                    rendimiento = ((precio_actual - pos['entrada']) / pos['entrada']) * 100
                    self.enviar(f"🔄 *UPDATE {ticker}*\n"
                                f"📍 Nuevo Stop: ${pos['stop']:.2f}\n"
                                f"📈 Rendimiento Actual: {rendimiento:.2f}%")

    def ejecutar_ciclo(self):
        """
        Ciclo principal de escaneo y gestión.
        """
        # 1. Escaneo automático de líderes en Polygon
        lideres = self.obtener_lideres_polygon()
        
        for activo in lideres:
            ticker = activo["ticker"]
            precio = activo["day"]["c"] # Precio de cierre (o último) del día
            volumen = activo["day"]["v"]# Volumen del día
            
            # 2. Filtrado Institucional (Precio y Volumen)
            # Verificamos si el activo cumple los criterios de precio y liquidez
            if CONFIG["PRICE_MIN"] <= precio <= CONFIG["PRICE_MAX"]:
                # Filtro de liquidez (Volumen mínimo)
                if volumen > 500000: 
                    # Si el activo no estaba en seguimiento, se abre posición
                    if ticker not in self.posiciones:
                        self.posiciones[ticker] = {'entrada': precio, 'stop': precio*0.90, 'max': precio}
                        self.enviar(f"🚀 *ALERTA DE ENTRADA*: {ticker}\n"
                                    f"Precio: ${precio}\n"
                                    f"¡Fuerza Institucional Detectada!")

            # 3. Gestión de Seguimiento (Trailing Stop)
            # Si el activo ya está en seguimiento, el bot gestiona su salida
            self.gestionar_trailing(ticker, precio)
            
            # Puedes añadir aquí lógica para eliminar tickers de self.posiciones si el precio cae por debajo del stop

        # Pausa de 60 segundos entre escaneos para respetar los límites de la API de Polygon
        time.sleep(60)

def run_bot():
    # Inicializamos el gestor
    gestor = GestorFrancotirador()
    # Bucle infinito para que el bot trabaje solo
    while True:
        gestor.ejecutar_ciclo()

if __name__ == "__main__":
    # Ejecutar el bot en un hilo separado para no bloquear el servidor web
    threading.Thread(target=run_bot, daemon=True).start()
    # Ejecutar el servidor Flask en el hilo principal (puerto 10000)
    app.run(host='0.0.0.0', port=10000)
