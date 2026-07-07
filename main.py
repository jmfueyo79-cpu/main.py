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
from http.server import BaseHTTPRequestHandler, HTTPServer

# SILENCIAR ADVERTENCIAS DE YFINANCE EN LOS LOGS
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- SERVIDOR WEB AUXILIAR PARA SATISFACER A RENDER ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("🤖 Bot Alpha Operativo: Escáner de Small Caps Activo.".encode("utf-8"))

    def log_message(self, format, *args):
        return  # Silenciar logs del servidor para mantener limpia la consola

def iniciar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", puerto), WebServerHandler)
    print(f"[WEB SERVER] Puerto {puerto} abierto con éxito para Render.")
    server.serve_forever()
# ------------------------------------------------------

class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        """
        Pipeline Cuantitativo de Alta Beta (Intervalo 30 Minutos).
        Filtrado estricto para buscar rendimientos explosivos (>50%) en acciones de $2 a $22.
        """
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        
        # Tus favoritas fijas (Si entran en rango de precio, el bot las analiza; si no, las salta)
        self.tus_favoritas = ["CRDF", "IOVA", "ALT", "HUMA", "IREN"]
        
        # BANCO MASIVO DE EXPLORACIÓN OPTIMIZADO PARA SMALL CAPS / BIOTECH / CRIPTO MINERS
        self.banco_total_activos = [
            # --- SECTOR BIOTECH & PHARMA EXPLOSIVAS ---
            "NVAX", "CELH", "GFAI", "ANVS", "AMAM", "KPTI", "PTGX", "CYTK",
            "RIGL", "CTXR", "AVXL", "BCRX", "GERN", "CRSP", "NTLA", "BEAM", "EDIT", "VERV",
            "BLUE", "SGMO", "SRPT", "PTCT", "AADI", "ABVC", "ACER", "ACET", "ACHV", "ACIU", 
            "ACRS", "ACST", "ACTG", "ALEC", "ALIM", "ALLR", "ALNA", "ALXO", "AMTI", "ANKR",
            "APLT", "APRE", "APTO", "APYX", "AQST", "ARDX", "ARQT", "ASMB", "ATNX", "ATOM", 
            "ATOS", "ATRA", "ATRC", "AURA", "AVDL", "AVIR", "AVTE", "AXLA", "AZTA", "BCAB", 
            "BCDA", "BMEA", "BNGO", "BTAI", "CARA", "CATX", "CDMO", "CDTX", "CDXC", "CELC",
            "CERE", "CGEN", "CGON", "CHRS", "CHYI", "CLDX", "CLSD", "CLVS", "CMPS", "CMRX",
            "CNCE", "CNTA", "CNTG", "COGT", "CRNX", "CRBU", "CRMD", "CRTX",
            # --- SECTOR CRIPTO, MINERÍA & BLOCKCHAIN (ALTA BETA) ---
            "MARA", "RIOT", "CLSK", "WULF", "CIFR", "CORZ", "HUT", "BTBT",
            "SDIG", "COWG", "MIGI", "CAN", "BOF", "BTCM", "GREE", "SOS", "BITF", "DGHI",
            # --- SECTOR IA, ROBÓTICA & SMALL TECH ---
            "SOFI", "HOOD", "UPST", "BBAI", "SOUN", "PATH", "C3AI", "PLUG",
            "UNITY", "RBLX", "ENVX", "FREY", "EVGO", "STEM", "SUNW", "MAXN", 
            "XPEV", "NIO", "FUTU", "TIGR", "WKHS", "GOEV", "HYLN", "REE", "ZEV"
        ]
        
        self.estado = self.cargar_estado()

    def cargar_estado(self):
        if os.path.exists(self.archivo_estado):
            try:
                with open(self.archivo_estado, 'r') as f:
                    return json.load(f)
            except: pass
        return {"posiciones_abiertas": {}}

    def guardar_estado(self):
        try:
            with open(self.archivo_estado, 'w') as f:
                json.dump(self.estado, f, indent=4)
        except: pass

    def generar_watchlist_exploratoria(self, tamano_total=100):
        pool_disponible = list(set(self.banco_total_activos) - set(self.tus_favoritas))
        cuantas_sortear = tamano_total - len(self.tus_favoritas)
        muestra_aleatoria = random.sample(pool_disponible, min(cuantas_sortear, len(pool_disponible)))
        return self.tus_favoritas + muestra_aleatoria

    def enviar_telegram(self, mensaje):
        if not self.telegram_token or not self.telegram_chat_id:
            return
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat_id, "text": mensaje, "parse_mode": "Markdown"}
        try: requests.post(url, json=payload, timeout=8)
        except: pass

    @staticmethod
    def calcular_atr(df, periodo=14):
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(window=periodo).mean()

    def escanear_intradiario(self, watchlist):
        print(f"[ESCÁNER] Iniciando barrido intradiario sobre {len(watchlist)} activos...")
        tickers_string = " ".join(watchlist)
        
        try:
            datos_mercado = yf.download(tickers_string, period="3d", interval="30m", group_by="ticker", progress=False, timeout=40)
        except Exception as e:
            print(f"[ESCÁNER ERROR] Fallo al conectar con Yahoo Finance: {e}")
            return

        for ticker in watchlist:
            try:
                if ticker not in datos_mercado.columns.levels[0]: continue
                df = datos_mercado[ticker].dropna()
                if len(df) < 25: continue
                
                hoy = df.iloc[-1]
                precio_actual = hoy['Close']
                
                # ─── FILTRO CRUCIAL DE PRECIO OBJETIVO ($2 A $22) ───
                if precio_actual < 2.0 or precio_actual > 22.0:
                    continue  # Si el precio no está en el rango explosivo, ignora el activo
                
                df['Vol_Media_20'] = df['Volume'].rolling(window=20).mean()
                df['ATR_14'] = self.calcular_atr(df, 14)
                
                if df['Vol_Media_20'].iloc[-1] < 10000: continue
                    
                ratio_volumen = hoy['Volume'] / df['Vol_Media_20'].iloc[-1]
                if ratio_volumen > 2.8:
                    cuerpo_vela = abs(hoy['Close'] - hoy['Open'])
                    if cuerpo_vela < (hoy['ATR_14'] * 1.2) and (hoy['Close'] - hoy['Low']) > (cuerpo_vela * 0.6):
                        if ticker not in self.estado["posiciones_abiertas"]:
                            atr_actual = hoy['ATR_14']
                            stop_loss_inicial = precio_actual - (2.5 * atr_actual)
                            
                            self.estado["posiciones_abiertas"][ticker] = {
                                "precio_entrada": round(precio_actual, 4),
                                "stop_loss": round(stop_loss_inicial, 4),
                                "max_precio_visto": round(precio_actual, 4),
                                "ultimo_rendimiento_notificado": 0.0
                            }
                            
                            msg = (
                                f"🚀 *COHETE INTRADIARIO DETECTADO ($2-$22)* 🚀\n\n"
                                f"📈 *Activo:* `{ticker}`\n"
                                f"💰 *Precio Entrada:* `${precio_actual:.2f}`\n"
                                f"📊 *Volumen Institucional:* `{ratio_volumen:.1f}x` MAV20\n"
                                f"🛡️ *Stop Inicial Sugerido:* `${stop_loss_inicial:.2f}` (2.5x ATR)"
                            )
                            self.enviar_telegram(msg)
                            self.guardar_estado()
            except: pass

    def gestionar_trailing_stops(self):
        if not self.estado["posiciones_abiertas"]: return
        tickers_abiertos = list(self.estado["posiciones_abiertas"].keys())
        tickers_string = " ".join(tickers_abiertos)
        
        try:
            datos_mercado = yf.download(tickers_string, period="3d", interval="30m", group_by="ticker", progress=False, timeout=15)
        except: return

        for ticker in tickers_abiertos:
            try:
                df = datos_mercado[ticker].dropna() if len(tickers_abiertos) > 1 else datos_mercado.dropna()
                if len(df) < 15: continue
                
                hoy = df.iloc[-1]
                precio_actual = hoy['Close']
                atr_actual = self.calcular_atr(df, 14).iloc[-1]
                
                pos = self.estado["posiciones_abiertas"][ticker]
                rendimiento_acumulado = ((precio_actual - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
                
                if precio_actual > pos["max_precio_visto"]:
                    pos["max_precio_visto"] = round(precio_actual, 4)
                    nuevo_stop = precio_actual - (2.2 * atr_actual)
                    if nuevo_stop > pos["stop_loss"]:
                        pos["stop_loss"] = round(nuevo_stop, 4)
                
                if rendimiento_acumulado - pos["ultimo_rendimiento_notificado"] >= 5.0:
                    pos["ultimo_rendimiento_notificado"] = round(rendimiento_acumulado, 2)
                    msg = (
                        f"⚡ *ACTUALIZACIÓN RENDIMIENTO* ⚡\n\n"
                        f"💎 *Activo:* `{ticker}`\n"
                        f"💵 *Precio Actual:* `${precio_actual:.2f}`\n"
                        f"🔥 *Rendimiento:* `+{rendimiento_acumulado:.2f}%`\n"
                        f"🛡️ *Trailing Stop Protegido:* `${pos['stop_loss']:.2f}`"
                    )
                    self.enviar_telegram(msg)
                    self.guardar_estado()
                    
                if precio_actual <= pos["stop_loss"]:
                    rendimiento_final = ((pos["stop_loss"] - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
                    msg = (
                        f"🚨 *DISPARO DE TRAILING STOP* 🚨\n\n"
                        f"📉 *Activo:* `{ticker}`\n"
                        f"🚪 *Precio Salida Ejecutado:* `${pos['stop_loss']:.2f}`\n"
                        f"💰 *Rendimiento Neto Final:* `+{rendimiento_final:.2f}%`"
                    )
                    self.enviar_telegram(msg)
                    del self.estado["posiciones_abiertas"][ticker]
                    self.guardar_estado()
            except: pass

if __name__ == '__main__':
    # 1. Servidor web en hilo paralelo para calmar a Render al instante
    t = threading.Thread(target=iniciar_servidor_web, daemon=True)
    t.start()
    time.sleep(1)
    
    print("[BOT] Iniciando ciclo de escaneo intradiario filtrado ($2 - $22)...")
    bot = PipelineTradingAlphaTelegram()
    
    # 2. Selección de activos y ejecución del radar
    watchlist_de_hoy = bot.generar_watchlist_exploratoria(tamano_total=100)
    bot.enviar_telegram(f"🔄 *Filtro Explosivo Activo ($2-$22):* Escaneando 100 activos de alta beta.")
    
    bot.escanear_intradiario(watchlist_de_hoy)
    bot.gestionar_trailing_stops()
    
    print("[BOT] Ciclo completado. Manteniendo contenedor activo para Render...")
    while True:
        time.sleep(300)
