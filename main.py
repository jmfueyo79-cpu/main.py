import time
from flask import Flask

# Configuración Ajustada para mayor flujo de alertas
CONFIG = {
    "RVOL_THRESHOLD": 2.2,       # Reducido de 3.0 para detectar más volumen
    "PRICE_MIN": 2.0,            # Mantenido en 2.0 para evitar penny stocks tóxicas
    "PRICE_MAX": 22.0,           # Aumentado para mayor universo de activos
    "CONFIRMATION_MINUTES": 3    # Reducido de 5 a 3 para mayor rapidez
}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Activo - Configuración Optimizada"

class GestorFrancotirador:
    def __init__(self):
        print("🚀 BOT PROFESIONAL: Trailing Stop + Confirmación 3min Activo")
        # Aquí iría tu lógica de conexión a Polygon y Telegram

    def ejecutar(self):
        # Lógica principal del bot
        # 1. Escaneo con RVOL >= CONFIG["RVOL_THRESHOLD"]
        # 2. Filtrado por precio: CONFIG["PRICE_MIN"] <= price <= CONFIG["PRICE_MAX"]
        # 3. Espera de confirmación: CONFIG["CONFIRMATION_MINUTES"]
        pass

if __name__ == "__main__":
    # Bucle robusto con reinicio automático
    while True:
        try:
            # Iniciar servidor web en hilo separado para evitar spin-down
            import threading
            threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
            
            gestor = GestorFrancotirador()
            while True:
                gestor.ejecutar()
                time.sleep(15)
        except Exception as e:
            print(f"Error detectado, reiniciando bot: {e}")
            time.sleep(60) 
