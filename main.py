# -*- coding: utf-8 -*-
import os
import json
import requests
import logging
import random
import pandas as pd
import yfinance as yf
import time
import threading
import gc
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

# SILENCIAR ADVERTENCIAS EN LOS LOGS PARA CONTROLAR EL CONSUMO
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)

# Instancia global del bot para que esté accesible desde el Servidor Web
instancia_bot = None

# Candado global para evitar ejecuciones simultáneas que saturen la RAM
lock_escaneo = threading.Lock()

# --- SERVIDOR WEB AUXILIAR (Actúa como el disparador real del análisis) ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Respondemos OK inmediatamente a cron-job.org para que no se quede colgado esperando
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")
        
        # Si el candado está libre, lanzamos el escaneo en segundo plano liberando recursos rápidamente
        if instancia_bot is not None and not lock_escaneo.locked():
            threading.Thread(target=ejecutar_ciclo_radar, args=(instancia_bot,), daemon=True).start()

    def log_message(self, format, *args): return

def iniciar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", puerto), WebServerHandler)
    server.serve_forever()
# --------------------------------------------------------------------------------------

class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        
        # Tus activos favoritos que SIEMPRE se analizan obligatoriamente en cada ciclo
        self.activos_prioritarios = ["FFAI", "ALLO", "CRDF", "ALT", "IOVA", "CHRS", "AVXL", "TNXP"]
        
        # Estado inicial del bot
        self.estado = self.cargar_estado()
        
        # Mensaje de confirmación de arranque con éxito en Telegram
        self.enviar_telegram("🤖 *RADAR ESTABILIZADO Y ANTIFUGAS ACTIVO*\nMonitoreo optimizado de memoria listo para la sesión.")

    def cargar_estado(self):
        if os.path.exists(self.archivo_estado):
            try:
                with open(self.archivo_estado, 'r') as f: return json.load(f)
            except: pass
        return {"posiciones_abiertas": {}}

    def guardar_estado(self):
        try:
            with open(self.archivo_estado, 'w') as f: json.dump(self.estado, f, indent=4)
        except: pass

    def obtener_top_ganadoras_del_mercado(self):
        """
        Descarga en tiempo real las acciones con más movimiento alcista del mercado US
        usando un endpoint público ligero de Yahoo Finance (no consume apenas RAM).
        """
        top_tickers = []
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds=day_gainers&count=40"
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                results = data.get("finance", {}).get("result", [])[0].get("quotes", [])
                for quote in results:
                    symbol = quote.get("symbol")
                    if symbol and "^" not in symbol and "=" not in symbol and len(symbol) <= 5:
                        top_tickers.append(symbol)
        except Exception as e:
            print(f"Error cargando top ganadoras: {e}")
            
        watchlist_completa = list(set(self.activos_prioritarios + top_tickers))
        return watchlist_completa

    def enviar_telegram(self, mensaje):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat_id, "text": mensaje, "parse_mode": "Markdown"}
        try: requests.post(url, json=payload, timeout=4)
        except: pass

    @staticmethod
    def calcular_atr(df, periodo=14):
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(window=periodo).mean()

    def procesar_un_bloque(self, bloque):
        tickers_string = " ".join(bloque)
        try:
            # Desactivamos threads para asegurar que Render no acumule basura en la RAM
            datos_mercado = yf.download(tickers_string, period="2d", interval="15m", group_by="ticker", progress=False, timeout=10, threads=False)
        except: return

        for ticker in bloque:
            try:
                if len(bloque) > 1:
                    if ticker not in datos_mercado.columns.levels[0]: continue
                    df = datos_mercado[ticker].dropna()
                else:
                    df = datos_mercado.dropna()
                    
                if len(df) < 16: continue
                
                hoy = df.iloc[-1]
                precio_actual = hoy['Close']
                
                if precio_actual < 0.10 or precio_actual > 25.0: continue
                
                df['Vol_Media_20'] = df['Volume'].rolling(window=20).mean()
                df['ATR_14'] = self.calcular_atr(df, 14)
                
                if df['Vol_Media_20'].iloc[-1] < 10000: continue
                    
                ratio_volumen = hoy['Volume'] / df['Vol_Media_20'].iloc[-1]
                
                if ratio_volumen > 2.2:
                    cuerpo_vela = abs(hoy['Close'] - hoy['Open'])
                    atr_actual = hoy['ATR_14']
                    
                    es_breakout_alcista = (hoy['Close'] > hoy['Open']) and (cuerpo_vela > (atr_actual * 0.8))
                    es_martillo_reversion = (cuerpo_vela < (atr_actual * 1.5)) and ((hoy['Close'] - hoy['Low']) > (cuerpo_vela * 0.5))
                    
                    if es_breakout_alcista or es_martillo_reversion:
                        if ticker not in self.estado["posiciones_abiertas"]:
                            stop_loss_inicial = precio_actual - (2.5 * atr_actual)
                            
                            if ratio_volumen >= 4.0:
                                categoria = "🟥 SÚPER COHETE (>50% Potencial)"
                                detalles_cat = "Anomalía crítica de Volumen Institucional (Ballenas acumulando agresivo)."
                            elif 2.5 <= ratio_volumen < 4.0:
                                categoria = "🟨 TENDENCIA FUERTE (15%-30% Potencial)"
                                detalles_cat = "Rompimiento limpio con volumen de confirmación sólido."
                            else:
                                categoria = "🟦 MOMENTUM ESTÁNDAR (5%-15% Potencial)"
                                detalles_cat = "Continuación o scalping rápido intradiario."
                            
                            self.estado["posiciones_abiertas"][ticker] = {
                                "precio_entrada": round(precio_actual, 4),
                                "stop_loss": round(stop_loss_inicial, 4),
                                "max_precio_visto": round(precio_actual, 4),
                                "ultimo_rendimiento_notificado": 0.0,
                                "salida_parcial_ejecutada": False
                            }
                            
                            msg = (
                                f"📡 *NUEVA ALERTA RADAR DE VOLUMEN (15M)* 📡\n"
                                f"───────────────────────\n"
                                f"🚨 *RANGO DE ACCIÓN:* `{categoria}`\n"
                                f"🎯 *Activo:* `{ticker}`\n"
                                f"💰 *Precio Entrada:* `${precio_actual:.4f}`\n"
                                f"📊 *Fuerza Volumen:* `{ratio_volumen:.1f}x` MAV20\n"
                                f"🛡️ *Stop Loss Inicial:* `${stop_loss_inicial:.4f}`\n"
                                f"───────────────────────\n"
                                f"💡 _Nota: {detalles_cat}_"
                            )
                            self.enviar_telegram(msg)
                            self.guardar_estado()
            except: pass

    def escanear_intradiario_concurrente(self, watchlist):
        tamano_bloque = 15
        bloques = [watchlist[i:i + tamano_bloque] for i in range(0, len(watchlist), tamano_bloque)]
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.map(self.procesar_un_bloque, bloques)

    def gestionar_trailing_stops(self):
        if not self.estado["posiciones_abiertas"]: return
        tickers_abiertos = list(self.estado["posiciones_abiertas"].keys())
        tickers_string = " ".join(tickers_abiertos)
        
        try:
            datos_mercado = yf.download(tickers_string, period="2d", interval="15m", group_by="ticker", progress=False, timeout=10, threads=False)
        except: return

        for ticker in tickers_abiertos:
            try:
                df = datos_mercado[ticker].dropna() if len(tickers_abiertos) > 1 else datos_mercado.dropna()
                if len(df) < 12: continue
                
                hoy = df.iloc[-1]
                precio_actual = hoy['Close']
                atr_actual = self.calcular_atr(df, 14).iloc[-1]
                
                pos = self.estado["posiciones_abiertas"][ticker]
                rendimiento_acumulado = ((precio_actual - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
                
                # 1. OBJETIVO EXTREMO ALCANZADO (+50%)
                if rendimiento_acumulado >= 50.0:
                    msg = (
                        f"🏆 *¡SÚPER COHETE COMPLETADO (+50%)!* 🏆\n\n"
                        f"🚀 *Activo:* `{ticker}`\n"
                        f"🎯 *Precio de Cierre:* `${precio_actual:.4f}`\n"
                        f"💰 *Rendimiento Final:* `+{rendimiento_acumulado:.2f}%`\n"
                        f"🔥 _¡Camión cargado con éxito! Posición cerrada en el objetivo._"
                    )
                    self.enviar_telegram(msg)
                    del self.estado["posiciones_abiertas"][ticker]
                    self.guardar_estado()
                    continue

                # 2. SALIDA PARCIAL AL +15% (REGLA FREE RIDER)
                if rendimiento_acumulado >= 15.0 and not pos.get("salida_parcial_ejecutada", False):
                    pos["salida_parcial_ejecutada"] = True
                    pos["stop_loss"] = pos["precio_entrada"]
                    pos["ultimo_rendimiento_notificado"] = 15.0
                    
                    msg = (
                        f"💰 *SALIDA PARCIAL EJECUTADA (+15%)* 💰\n\n"
                        f"💎 *Activo:* `{ticker}`\n"
                        f"💵 *Precio Actual:* `${precio_actual:.4f}`\n"
                        f"🛡️ *Acción:* `Se vende el 50% de la posición.`\n"
                        f"🔒 *Seguridad:* `Stop Loss de la otra mitad ajustado a precio de entrada (${pos['precio_entrada']:.4f}). ¡Operación libre de riesgo!`"
                    )
                    self.enviar_telegram(msg)
                    self.guardar_estado()

                # 3. TRAILING STOP HOLGADO DINÁMICO
                if precio_actual > pos["max_precio_visto"]:
                    pos["max_precio_visto"] = round(precio_actual, 4)
                    
                    multiplicador_stop = 3.5 if pos.get("salida_parcial_ejecutada", False) else 2.2
                    nuevo_stop = precio_actual - (multiplicador_stop * atr_actual)
                    
                    if nuevo_stop > pos["stop_loss"]:
                        pos["stop_loss"] = round(nuevo_stop, 4)
                
                if rendimiento_acumulado - pos["ultimo_rendimiento_notificado"] >= 10.0:
                    pos["ultimo_rendimiento_notificado"] = round(rendimiento_acumulado, 2)
                    msg = (
                        f"⚡ *SUBIDA CONTROLADA* ⚡\n\n"
                        f"💎 *Activo:* `{ticker}`\n"
                        f"💵 *Precio:* `${precio_actual:.4f}`\n"
                        f"🔥 *Beneficio actual:* `+{rendimiento_acumulado:.2f}%`\n"
                        f"🛡️ *Ajuste de Stop:* `${pos['stop_loss']:.4f}`"
                    )
                    self.enviar_telegram(msg)
                    self.guardar_estado()
                    
                # 4. SALIDA POR TACTO DE STOP
                if precio_actual <= pos["stop_loss"]:
                    rendimiento_final = ((pos["stop_loss"] - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
                    tipo_salida = "TRAILING STOP (FREE RIDER)" if pos.get("salida_parcial_ejecutada", False) else "STOP LOSS"
                    
                    msg = (
                        f"🚨 *DISPARO DE {tipo_salida}* 🚨\n\n"
                        f"📉 *Activo:* `{ticker}`\n"
                        f"🚪 *Precio Salida:* `${pos['stop_loss']:.4f}`\n"
                        f"💰 *Resultado Neto:* `{rendimiento_final:+.2f}%`"
                    )
                    self.enviar_telegram(msg)
                    del self.estado["posiciones_abiertas"][ticker]
                    self.guardar_estado()
            except: pass

def es_horario_mercado():
    zona_local = pytz.timezone('Europe/Madrid')
    ahora = datetime.now(zona_local)
    if ahora.weekday() > 4: return False
    if 15 <= ahora.hour < 22: return True
    return False

def ejecutar_ciclo_radar(bot):
    if not es_horario_mercado():
        return
        
    with lock_escaneo:
        try:
            bot.gestionar_trailing_stops()
            watchlist_dinamica = bot.obtener_top_ganadoras_del_mercado()
            if watchlist_dinamica:
                bot.escanear_intradiario_concurrente(watchlist_dinamica)
        finally:
            if 'watchlist_dinamica' in locals(): del watchlist_dinamica
            gc.collect()

# --- INICIALIZACIÓN DEL SERVIDOR Y DEL RADAR ---
if __name__ == "__main__":
    # Creamos la instancia y en el constructur se enviará el mensaje de inicio
    instancia_bot = PipelineTradingAlphaTelegram()
    
    hilo_servidor = threading.Thread(target=iniciar_servidor_web, daemon=True)
    hilo_servidor.start()
    
    while True:
        time.sleep(1)
