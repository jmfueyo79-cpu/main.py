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

# SILENCIAR ADVERTENCIAS EN LOS LOGS
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)

# --- SERVIDOR WEB AUXILIAR SILENCIOSO ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args): return

def iniciar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", puerto), WebServerHandler)
    server.serve_forever()
# ------------------------------------------------------

class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        
        # Tus favoritas fijas (Analizadas de forma obligatoria en cada ciclo)
        self.tus_favoritas = ["CRDF", "IOVA", "ALT", "HUMA", "IREN"]
        
        # BANCO MASIVO EXTENDIDO (+320 Activos de Alta Beta, Biotech, Cripto & Small Caps)
        self.banco_total_activos = [
            # --- SECTOR CRIPTO, MINERÍA & BLOCKCHAIN ---
            "MARA", "RIOT", "CLSK", "WULF", "CIFR", "CORZ", "HUT", "BTBT", "SDIG", "COWG", 
            "MIGI", "CAN", "BOF", "BTCM", "GREE", "SOS", "BITF", "DGHI", "BITQ", "WGMI", 
            "BLOK", "MSTR", "CONL", "COIN",
            # --- SECTOR IA, SEMICONDUCTORES, ROBÓTICA & TECH ---
            "SOFI", "HOOD", "AFRM", "UPST", "AI", "BBAI", "SOUN", "PATH", "C3AI", "PLUG", 
            "UNITY", "RBLX", "ENVX", "FREY", "EVGO", "BE", "STEM", "SUNW", "MAXN", "CSIQ", 
            "XPEV", "NIO", "LI", "FUTU", "TIGR", "WKHS", "GOEV", "HYLN", "REE", "ZEV", 
            "DM", "PRST", "AEYE", "BMR", "CXAI", "MKFG", "IKT", "LUNR", "SIDU", "VLD",
            "QUBT", "RGTI", "IONQ", "QMCO", "KOPN", "WAVS", "POET", "BOUG", "ASTR", "PLTR",
            # --- SECTOR BIOTECH & MICRO-PHARMA EXPLOSIVAS ---
            "NVAX", "CELH", "GFAI", "ANVS", "AMAM", "KPTI", "PTGX", "CYTK", "RIGL", "CTXR", 
            "AVXL", "BCRX", "GERN", "CRSP", "NTLA", "BEAM", "EDIT", "VERV", "BLUE", "SGMO", 
            "SRPT", "PTCT", "ALNY", "IONIS", "EXAS", "GH", "GUARD", "AADI", "ABVC", "ACAD", 
            "ACER", "ACET", "ACHV", "ACIU", "ACRS", "ACST", "ACTG", "ALEC", "ALIM", "ALKS", 
            "ALLR", "ALNA", "ALXO", "AMED", "AMTI", "ANGI", "ANKR", "APLS", "APLT", "APRE", 
            "APTO", "APYX", "AQST", "ARDX", "ARQT", "ARWR", "ASMB", "ASND", "ATNX", "ATOM", 
            "ATOS", "ATRA", "ATRC", "AURA", "AUPH", "AUR", "AVDL", "AVIR", "AVTE", "AXSM", 
            "AXLA", "AZTA", "BCAB", "BCDA", "BMEA", "BNGO", "BPMC", "BTAI", "CARS", "CARA", 
            "CATX", "CCXI", "CDMO", "CDNA", "CDTX", "CDXC", "CELC", "CERE", "CGEN", "CGON", 
            "CHRS", "CHYI", "CLDX", "CLSD", "CLVS", "CMPS", "CMRX", "CNCE", "CNTA", "CNTG", 
            "COGT", "COLL", "CORT", "CRNX", "CRBU", "CRMD", "CRTX", "VNDA", "TLSA", "PRTA",
            "INSM", "BBIO", "SRRK", "KNSA", "RLAY", "RYTM", "PLI", "XENE", "ZEAL", "MRUS",
            "MURA", "IMCR", "KROS", "RCKT", "ABOS", "VTYX", "ASND", "MOR", "IDYA", "CGEM",
            # --- EXTRA SMALL CAPS DE MOMENTUM, ENERGY & REVERSAL ---
            "BABA", "DKNG", "JD", "PDD", "TLRY", "FCEL", "BLNK", "RUN", "CHPT", "NKLA", 
            "QS", "JD", "BILI", "TAL", "EDU", "GOTU", "UXIN", "YALA", "IQ", "HUYA",
            "DADA", "FINV", "LX", "TIGR", "UPLI", "GATO", "MAG", "ASM", "GPL", "NAK",
            "AAU", "PLG", "THM", "WRN", "TRX", "GSV", "CDXS", "VERI", "CLSK", "XAIR",
            "PALI", "BTTX", "TCBP", "ISPR", "SNGX", "OCUP", "TENX", "PRSO", "SOPA", "LIPO",
            "OPTT", "WATT", "CEI", "HUSA", "IMPP", "REI", "PED", "MREO", "SNDL", "ACB"
        ]
        
        self.estado = self.cargar_estado()

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

    def generar_watchlist_exploratoria(self, tamano_total=200):
        pool_disponible = list(set(self.banco_total_activos) - set(self.tus_favoritas))
        cuantas_sortear = tamano_total - len(self.tus_favoritas)
        muestra_aleatoria = random.sample(pool_disponible, min(cuantas_sortear, len(pool_disponible)))
        return self.tus_favoritas + muestra_aleatoria

    def enviar_telegram(self, mensaje):
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
        tamano_bloque = 50
        bloques = [watchlist[i:i + tamano_bloque] for i in range(0, len(watchlist), tamano_bloque)]
        
        for bloque in bloques:
            tickers_string = " ".join(bloque)
            try:
                datos_mercado = yf.download(tickers_string, period="3d", interval="30m", group_by="ticker", progress=False, timeout=30)
            except:
                continue

            for ticker in bloque:
                try:
                    if len(bloque) > 1:
                        if ticker not in datos_mercado.columns.levels[0]: continue
                        df = datos_mercado[ticker].dropna()
                    else:
                        df = datos_mercado.dropna()
                        
                    if len(df) < 25: continue
                    
                    hoy = df.iloc[-1]
                    precio_actual = hoy['Close']
                    
                    # FILTRO DE PRECIO DE COHETES ($2 A $22)
                    if precio_actual < 2.0 or precio_actual > 22.0: continue
                    
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
            time.sleep(1.5)

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
    threading.Thread(target=iniciar_servidor_web, daemon=True).start()
    time.sleep(1)
    
    bot = PipelineTradingAlphaTelegram()
    
    # Marcamos un objetivo de escaneo de 200 activos por ciclo (4 bloques de 50)
    watchlist_de_hoy = bot.generar_watchlist_exploratoria(tamano_total=200)
    
    bot.enviar_telegram(f"⚡ *Súper Radar Activo:* Escaneando {len(watchlist_de_hoy)} activos aleatorios (en bloques de 50).")
    
    bot.escanear_intradiario(watchlist_de_hoy)
    bot.gestionar_trailing_stops()
    
    while True:
        time.sleep(300)
