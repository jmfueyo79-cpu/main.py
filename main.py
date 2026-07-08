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
from datetime import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

# SILENCIAR ADVERTENCIAS EN LOS LOGS PARA OPTIMIZAR VELOCIDAD
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)

# --- SERVIDOR WEB AUXILIAR (Obligatorio para que Render no cancele el Deploy) ---
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
# --------------------------------------------------------------------------------------

class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        
        # BANCO MASIVO EXTENDIDO DE TRADING
        self.banco_total_activos = [
            # --- SECTOR CRIPTO, MINERÍA & BLOCKCHAIN ---
            "MARA", "RIOT", "CLSK", "WULF", "CIFR", "CORZ", "HUT", "BTBT", "SDIG", "COWG", 
            "MIGI", "CAN", "BOF", "BTCM", "GREE", "SOS", "BITF", "DGHI", "BITQ", "WGMI", 
            "BLOK", "MSTR", "CONL", "COIN", "IREN",
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
            "CRDF", "IOVA", "ALT", "HUMA",
            # --- EXTRA SMALL CAPS DE MOMENTUM, ENERGY & REVERSAL ---
            "BABA", "DKNG", "JD", "PDD", "TLRY", "FCEL", "BLNK", "RUN", "CHPT", "NKLA", 
            "QS", "BILI", "TAL", "EDU", "GOTU", "UXIN", "YALA", "IQ", "HUYA",
            "DADA", "FINV", "LX", "UPLI", "GATO", "MAG", "ASM", "GPL", "NAK",
            "AAU", "PLG", "THM", "WRN", "TRX", "GSV", "CDXS", "VERI", "XAIR",
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

    def generar_watchlist_exploratoria(self, tamano_total=100):
        return random.sample(self.banco_total_activos, min(tamano_total, len(self.banco_total_activos)))

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
            datos_mercado = yf.download(tickers_string, period="2d", interval="15m", group_by="ticker", progress=False, timeout=10)
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
                
                if precio_actual < 2.0 or precio_actual > 22.0: continue
                
                df['Vol_Media_20'] = df['Volume'].rolling(window=20).mean()
                df['ATR_14'] = self.calcular_atr(df, 14)
                
                if df['Vol_Media_20'].iloc[-1] < 10000: continue
                    
                ratio_volumen = hoy['Volume'] / df['Vol_Media_20'].iloc[-1]
                
                if ratio_volumen > 2.2:
                    cuerpo_vela = abs(hoy['Close'] - hoy['Open'])
                    if cuerpo_vela < (hoy['ATR_14'] * 1.2) and (hoy['Close'] - hoy['Low']) > (cuerpo_vela * 0.6):
                        if ticker not in self.estado["posiciones_abiertas"]:
                            atr_actual = hoy['ATR_14']
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
                                "ultimo_rendimiento_notificado": 0.0
                            }
                            
                            msg = (
                                f"📡 *NUEVA ALERTA RADAR DE VOLUMEN (15M)* 📡\n"
                                f"───────────────────────\n"
                                f"🚨 *RANGO DE ACCIÓN:* `{categoria}`\n"
                                f"🎯 *Activo:* `{ticker}`\n"
                                f"💰 *Precio Entrada:* `${precio_actual:.2f}`\n"
                                f"📊 *Fuerza Volumen:* `{ratio_volumen:.1f}x` MAV20\n"
                                f"🛡️ *Stop Loss Inicial:* `${stop_loss_inicial:.2f}`\n"
                                f"───────────────────────\n"
                                f"💡 _Nota: {detalles_cat}_"
                            )
                            self.enviar_telegram(msg)
                            self.guardar_estado()
            except: pass

    def escanear_intradiario_concurrente(self, watchlist):
        tamano_bloque = 20
        bloques = [watchlist[i:i + tamano_bloque] for i in range(0, len(watchlist), tamano_bloque)]
        with ThreadPoolExecutor(max_workers=len(bloques)) as executor:
            executor.map(self.procesar_un_bloque, bloques)

    def gestionar_trailing_stops(self):
        if not self.estado["posiciones_abiertas"]: return
        tickers_abiertos = list(self.estado["posiciones_abiertas"].keys())
        tickers_string = " ".join(tickers_abiertos)
        
        try:
            datos_mercado = yf.download(tickers_string, period="2d", interval="15m", group_by="ticker", progress=False, timeout=10)
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
                
                if precio_actual > pos["max_precio_visto"]:
                    pos["max_precio_visto"] = round(precio_actual, 4)
                    nuevo_stop = precio_actual - (2.2 * atr_actual)
                    if nuevo_stop > pos["stop_loss"]:
                        pos["stop_loss"] = round(nuevo_stop, 4)
                
                if rendimiento_acumulado - pos["ultimo_rendimiento_notificado"] >= 5.0:
                    pos["ultimo_rendimiento_notificado"] = round(rendimiento_acumulado, 2)
                    msg = (
                        f"⚡ *SUBIDA CONTROLADA* ⚡\n\n"
                        f"💎 *Activo:* `{ticker}`\n"
                        f"💵 *Precio:* `${precio_actual:.2f}`\n"
                        f"🔥 *Beneficio actual:* `+{rendimiento_acumulado:.2f}%`\n"
                        f"🛡️ *Ajuste de Stop:* `${pos['stop_loss']:.2f}`"
                    )
                    self.enviar_telegram(msg)
                    self.guardar_estado()
                    
                if precio_actual <= pos["stop_loss"]:
                    rendimiento_final = ((pos["stop_loss"] - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
                    msg = (
                        f"🚨 *DISPARO DE TRAILING STOP* 🚨\n\n"
                        f"📉 *Activo:* `{ticker}`\n"
                        f"🚪 *Precio Salida:* `${pos['stop_loss']:.2f}`\n"
                        f"💰 *Resultado Neto:* `+{rendimiento_final:.2f}%`"
                    )
                    self.enviar_telegram(msg)
                    del self.estado["posiciones_abiertas"][ticker]
                    self.guardar_estado()
            except: pass

def es_horario_mercado():
    zona_local = pytz.timezone('Europe/Madrid')
    ahora = datetime.now(zona_local)
    if ahora.weekday() > 4: return False  # Fines de semana descartados
    if 16 <= ahora.hour < 22: return True  # Ventana activa: 16:00 a 22:00
    return False

def motor_cron_interno(bot):
    bot.enviar_telegram("🤖 *RADAR INTELIGENTE CONTROLADO OPERATIVO* 🤖\n_Monitoreando el mercado cada 15 min de Lunes a Viernes (16h a 22h)..._")
    
    while True:
        try:
            if es_horario_mercado():
                # Ejecutar barrido de mercado
                bot.gestionar_trailing_stops()
                watchlist_de_hoy = bot.generar_watchlist_exploratoria(tamano_total=100)
                bot.escanear_intradiario_concurrente(watchlist_de_hoy)
        except Exception:
            pass
        
        # Pausa estructural de 15 minutos (900 segundos) antes del siguiente ciclo
        time.sleep(900)

if __name__ == '__main__':
    # 1. Enciende el puerto web de forma instantánea. Render aprueba el deploy en 1 segundo.
    threading.Thread(target=iniciar_servidor_web, daemon=True).start()
    time.sleep(0.5)
    
    # 2. Arranca el motor infinito con la lógica de horarios encapsulada
    instancia_bot = PipelineTradingAlphaTelegram()
    motor_cron_interno(instancia_bot)
