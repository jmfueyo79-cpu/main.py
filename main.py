import time
import os
import threading
from flask import Flask

# Configuración Optimizada
CONFIG = {
    "RVOL_THRESHOLD": 2.2,
    "PRICE_MIN": 2.0,
    "PRICE_MAX": 22.0,
    "CONFIRMATION_MINUTES": 3
}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Activo - Configuración Optimizada"

class GestorFrancotirador:
    def __init__(self):
        # Lectura directa de variables de entorno
        self.token = os.environ.get("TELEGRAM_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        # Log inmediato para diagnóstico
        print(f"DEBUG: Token detectado: {'SÍ' if self.token else 'NO'}")
        print(f"DEBUG: Chat ID detectado: {'SÍ' if self.chat_id else 'NO'}")
        
        if not self.token or not self.chat_id:
            print("ERROR: Las variables TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no están configuradas.")
        else:
            print("🚀 BOT PROFESIONAL: Trailing Stop + Confirmación 3min Activo")

    def ejecutar(self):
        # Aquí va la lógica de escaneo y envío a Telegram
        pass

if __name__ == "__main__":
    # Iniciar servidor web Flask en hilo separado
    def run_flask():
        app.run(host='0.0.0.0', port=10000)
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Iniciar gestor
    gestor = GestorFrancotirador()
    
    while True:
        try:
            gestor.ejecutar()
            time.sleep(15)
        except Exception as e:
            print(f"Error en bucle principal: {e}")
            time.sleep(60)
            
