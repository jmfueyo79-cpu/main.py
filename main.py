import time
import threading
import telepot
import requests
import os
from flask import Flask

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN = "8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys"
CHAT_ID = "2047038250"
POLYGON_KEY = os.environ.get("POLYGON_API_KEY")

@app.route('/')
def home():
    return "Bot Operativo"

def ejecutar_bot():
    print("Iniciando lógica del bot...")
    try:
        bot = telepot.Bot(TOKEN)
        bot.sendMessage(CHAT_ID, "🚀 SISTEMA FRANCOTIRADOR ACTIVADO Y CONECTADO")
        print("Mensaje de activación enviado a Telegram.")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")
        
    while True:
        # Aquí irá tu lógica de escaneo
        time.sleep(60)

if __name__ == "__main__":
    # Arrancamos el bot como hilo principal de lógica
    threading.Thread(target=ejecutar_bot, daemon=True).start()
    # Arrancamos Flask para cumplir con Render
    app.run(host='0.0.0.0', port=10000)
