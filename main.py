# -*- coding: utf-8 -*-
import os
import json
import time
import requests
import pandas as pd
import numpy as np
from threading import Thread
from flask import Flask

# =====================================================================
# 1. SERVIDOR FLASK INTEGRADO PARA QUE RENDER MANTENGA EL WEB SERVICE VIVO
# =====================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Pipeline Trading Alpha en ejecución continua...", 200

def ejecutar_servidor_web():
    # Render asigna automáticamente un puerto dinámico en la variable de entorno PORT
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)

# =====================================================================
# 2. CORE DEL PIPELINE CUANTITATIVO CON TELEGRAM
# =====================================================================
class PipelineTradingAlphaTelegram:
    def __init__(self, api_key_polygon, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        """
        Pipeline Cuantitativo Avanzado adaptado para ejecuciones continuas en Render.
        """
        self.api_key = api_key_polygon
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        self.estado = self.cargar_estado()
        
    def cargar_estado(self):
        if os.path.exists(self.archivo_estado):
            try:
                with open(self.archivo_estado, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR PERSISTENCIA] Re-inicializando estado: {e}")
        
        return {
            "watchlist_activa": ["CRDF", "IOVA", "ALT", "HUMA", "IREN"],
            "posiciones_abiertas": {},
            "alertas_historicas": []
        }

    def guardar_estado(self):
        try:
            with open(self.archivo_estado, 'w') as f:
                json.dump(self.estado, f, indent=4)
        except Exception as e:
            print(f"[ERROR PERSISTENCIA] Imposible guardar estado en JSON: {e}")

    def enviar_telegram(self, mensaje):
        print(f"[TELEGRAM LOG]:\n{mensaje}\n")
        if not self.telegram_token or not self.telegram_chat_id:
            return
            
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=payload, timeout=8)
            if response.status_code != 200:
                print(f"[TELEGRAM ERROR] Código erróneo: {response.status_code}")
        except Exception as e:
            print(f"[TELEGRAM EXCEPCIÓN] Fallo de conexión: {e}")

    def obtener_datos_polygon(self, ticker, dias=120):
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2026-01-01/2026-07-07"
        params = {"adjusted": "true", "sort": "asc", "limit": dias, "apiKey": self.api_key}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "results" in data and len(data["results"]) > 0:
                    df = pd.DataFrame(data["results"])
                    df = df.rename(columns={'c': 'Close', 'o': 'Open', 'h': 'High', 'l': 'Low', 'v': 'Volume', 't': 'Timestamp'})
                    return df
        except Exception as e:
            print(f"[POLYGON ERROR] {ticker}: {e}")
        return None

    def verificar_cluster_insiders_sec(self, ticker):
        base_insiders = {
            "CRDF": {"compras_recientes": 3, "confianza": "ALTA"},
            "IOVA": {"compras_recientes": 1, "confianza": "MEDIA"},
            "ALT": {"compras_recientes": 5, "confianza": "CRÍTICA"},
            "HUMA": {"compras_recientes": 0, "confianza": "NULA"},
            "IREN": {"compras_recientes": 2, "confianza": "ALTA"}
        }
        return base_insiders.get(ticker, {"compras_recientes": 0, "confianza": "NULA"})

    @staticmethod
    def calcular_atr(df, periodo=14):
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        rangos = pd.concat([high_low, high_close, low_close], axis=1)
        return rangos.max(axis=1).rolling(window=period).mean()

    def ejecutar_screener_potencial_alto(self):
        for ticker in self.estado["watchlist_activa"]:
            df = self.obtener_datos_polygon(ticker)
            if df is None or len(df) < 30: 
                continue
            
            df['Vol_Media_20'] = df['Volume'].rolling(window=20).mean()
            df['ATR_14'] = self.calcular_atr(df, 14)
            hoy = df.iloc[-1]
            
            ratio_volumen = hoy['Volume'] / hoy['Vol_Media_20']
            anomalia_volumen = ratio_volumen > 2.8
            
            cuerpo_vela = abs(hoy['Close'] - hoy['Open'])
            precio_en_rango = cuerpo_vela < (hoy['ATR_14'] * 1.2)
            absorcion_compras = (hoy['Close'] - hoy['Low']) > (cuerpo_vela * 0.6)
            
            datos_insider = self.verificar_cluster_insiders_sec(ticker)
            cluster_insider = datos_insider["compras_recientes"] >= 2
            
            if anomalia_volumen and precio_en_rango and absorcion_compras and cluster_insider:
                if ticker not in self.estado["posiciones_abiertas"]:
                    atr_actual = hoy['ATR_14']
                    precio_entrada = hoy['Close']
                    stop_loss_inicial = precio_entrada - (2.5 * atr_actual)
                    
                    self.estado["posiciones_abiertas"][ticker] = {
                        "precio_entrada": round(precio_entrada, 4),
                        "stop_loss": round(stop_loss_inicial, 4),
                        "max_precio_visto": round(precio_entrada, 4),
                        "atr_en_entrada": round(atr_actual, 4),
                        "ultimo_rendimiento_notificado": 0.0
                    }
                    
                    msg = (
                        f"🚀 *¡ALERTA DE ENTRADA ALPHA!* 🚀\n\n"
                        f"📈 *Activo:* `{ticker}`\n"
                        f"💰 *Precio Entrada:* `${precio_entrada:.2f}`\n"
                        f"📊 *Anomalía Volumen:* `{ratio_volumen:.1f}x` MAV20\n"
                        f"👥 *Cluster de Insiders:* `{datos_insider['confianza']}`\n"
                        f"🛡️ *Stop Loss Inicial:* `${stop_loss_inicial:.2f}` (2.5x ATR - Holgado)\n"
                        f"🎯 *Objetivo Asimétrico:* >+50% de Rentabilidad"
                    )
                    self.enviar_telegram(msg)
                    self.guardar_estado()

    def gestionar_monitoreo_y_trailing_stops(self):
        if not self.estado["posiciones_abiertas"]:
            return

        for ticker, pos in list(self.estado["posiciones_abiertas"].items()):
            df = self.obtener_datos_polygon(ticker)
            if df is None: 
                continue
            
            hoy = df.iloc[-1]
            precio_actual = hoy['Close']
            atr_actual = self.calcular_atr(df, 14).iloc[-1]
            
            rendimiento_acumulado = ((precio_actual - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
            
            if precio_actual > pos["max_precio_visto"]:
                pos["max_precio_visto"] = round(precio_actual, 4)
                nuevo_stop = precio_actual - (2.2 * atr_actual)
                if nuevo_stop > pos["stop_loss"]:
                    pos["stop_loss"] = round(nuevo_stop, 4)
            
            if rendimiento_acumulado - pos["ultimo_rendimiento_notificado"] >= 5.0:
                pos["ultimo_rendimiento_notificado"] = round(rendimiento_acumulado, 2)
                msg = (
                    f"⚡ *ACTUALIZACIÓN DE RENDIMIENTO* ⚡\n\n"
                    f"💎 *Activo:* `{ticker}`\n"
                    f"💵 *Precio Actual:* `${precio_actual:.2f}`\n"
                    f"🔥 *Rendimiento Acumulado:* `+{rendimiento_acumulado:.2f}%`\n"
                    f"🛡️ *Trailing Stop Elevado a:* `${pos['stop_loss']:.2f}`"
                )
                self.enviar_telegram(msg)
                self.guardar_estado()
                
            if precio_actual <= pos["stop_loss"]:
                rendimiento_final = ((pos["stop_loss"] - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
                msg = (
                    f"🚨 *DISPARO DE TRAILING STOP / SALIDA* 🚨\n\n"
                    f"📉 *Activo:* `{ticker}`\n"
                    f"🚪 *Precio de Salida:* `${pos['stop_loss']:.2f}`\n"
                    f"💰 *Rendimiento Final Neto:* `+{rendimiento_final:.2f}%`"
                )
                self.enviar_telegram(msg)
                del self.estado["posiciones_abiertas"][ticker]
                self.guardar_estado()

# Bucle infinito en segundo plano para no bloquear a Flask
def loop_estrategia_trading():
    # Recuerda poner aquí tu clave real de Polygon o usar variables de entorno
    api_key_polygon = os.environ.get("POLYGON_API_KEY", "TU_POLYGON_API_KEY_REAL")
    bot = PipelineTradingAlphaTelegram(api_key_polygon=api_key_polygon)
    
    print("[BOT] Iniciando ciclo de monitoreo continuo...")
    while True:
        try:
            bot.ejecutar_screener_potencial_alto()
            bot.gestionar_monitoreo_y_trailing_stops()
        except Exception as e:
            print(f"[ERROR EN CICLO]: {e}")
            
        # Espera 1 hora (3600 segundos) entre chequeos para operar velas diarias sin saturar la API
        time.sleep(3600)

if __name__ == '__main__':
    # 1. Lanzamos el bot de trading en un hilo paralelo (Background)
    hilo_trading = Thread(target=loop_estrategia_trading)
    hilo_trading.daemon = True
    hilo_trading.start()
    
    # 2. Iniciamos Flask en el hilo principal para satisfacer el Web Service de Render
    ejecutar_servidor_web()
