# -*- coding: utf-8 -*-
import os, json, requests, pandas as pd, yfinance as yf, time, threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging

# CONFIGURACIÓN SILENCIOSA
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)

class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot Activo y Patrullando")
    def log_message(self, format, *args): return

def iniciar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", puerto), WebServerHandler)
    server.serve_forever()

class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250"):
        self.token = telegram_token
        self.chat_id = telegram_chat_id
        self.archivo = "estado_remolazo_final.json"
        self.activos = ["FFAI", "ALLO", "CRDF", "ALT", "IOVA", "CHRS", "AVXL", "TNXP"]
        self.estado = self.cargar_estado()
        self.enviar_tg("🛡️ *SISTEMA REMOLAZO V11 (MA200 + FILTRO RSI) ACTIVADO*")

    def cargar_estado(self):
        if os.path.exists(self.archivo):
            try:
                with open(self.archivo, 'r') as f: return json.load(f)
            except: pass
        return {"posiciones": {}}

    def guardar_estado(self):
        with open(self.archivo, 'w') as f: json.dump(self.estado, f, indent=4)

    def enviar_tg(self, msg):
        try: requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage", json={"chat_id": self.chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
        except: pass

    def procesar(self):
        # 1. Obtenemos datos para filtrar
        try: 
            df_diario = yf.download(" ".join(self.activos), period="1y", interval="1d", group_by="ticker", progress=False)
            df_15m = yf.download(" ".join(self.activos), period="5d", interval="15m", group_by="ticker", progress=False)
        except: return

        for ticker in self.activos:
            try:
                df_d = df_diario[ticker].dropna() if len(self.activos) > 1 else df_diario.dropna()
                df_i = df_15m[ticker].dropna() if len(self.activos) > 1 else df_15m.dropna()
                
                # FILTROS V11 DE CALIDAD
                p = df_i['Close'].iloc[-1]
                ma200_diaria = df_d['Close'].rolling(200).mean().iloc[-1]
                
                # RSI real sobre datos 15m
                delta = df_i['Close'].diff()
                rsi = 100 - (100 / (1 + (delta.clip(lower=0).rolling(14).mean() / -delta.clip(upper=0).rolling(14).mean()).iloc[-1]))
                vol_ratio = df_i['Volume'].iloc[-1] / df_i['Volume'].rolling(20).mean().iloc[-1]
                
                # ENTRADA AUTOMÁTICA CON FILTROS
                if p > ma200_diaria and 30 < rsi < 85 and vol_ratio > 2.5 and ticker not in self.estado["posiciones"]:
                    
                    cat = "🟥 SÚPER COHETE (>50%)" if vol_ratio >= 4.0 else "🟨 TENDENCIA FUERTE (15-30%)"
                    
                    atr = (df_i['High']-df_i['Low']).rolling(14).mean().iloc[-1]
                    self.estado["posiciones"][ticker] = {"entrada": p, "stop": p - (2.2 * atr), "max": p, "parcial": False}
                    self.enviar_tg(f"📡 *ALERTA {ticker}*\n🚨 {cat}\n💰 Precio: `{p:.4f}`\n📈 Sobre MA200: `SÍ`\n📊 Vol: `{vol_ratio:.1f}x` | RSI: `{rsi:.1f}`")
                    self.guardar_estado()
            except: pass

    def gestionar_maximizar(self):
        tickers = list(self.estado["posiciones"].keys())
        if not tickers: return
        df_m = yf.download(" ".join(tickers), period="2d", interval="15m", group_by="ticker", progress=False)
        for ticker in tickers:
            try:
                df = df_m[ticker].dropna() if len(tickers) > 1 else df_m.dropna()
                p = df['Close'].iloc[-1]
                pos = self.estado["posiciones"][ticker]
                rend = ((p - pos["entrada"]) / pos["entrada"]) * 100
                
                # MAXIMIZACIÓN INFINITA Y TRAILING STOP
                if rend >= 15.0 and not pos["parcial"]:
                    pos["parcial"] = True; pos["stop"] = pos["entrada"]
                    self.enviar_tg(f"💰 *PARCIAL {ticker} (+15%)*. Stop en entrada."); self.guardar_estado()
                
                if p > pos["max"]:
                    pos["max"] = p; pos["stop"] = p - (1.5 * (df['High']-df['Low']).rolling(14).mean().iloc[-1])
                    self.guardar_estado()
                
                if p <= pos["stop"]:
                    self.enviar_tg(f"🚨 *SALIDA {ticker}*. Res: `{rend:.2f}%`"); del self.estado["posiciones"][ticker]; self.guardar_estado()
            except: pass

def ejecutar_ciclo_continuo_bot(bot):
    while True:
        ahora = datetime.now(pytz.timezone('Europe/Madrid'))
        if ahora.weekday() < 5 and (15 <= ahora.hour < 22):
            bot.gestionar_maximizar()
            bot.procesar()
            time.sleep(300)
        else: time.sleep(60)

if __name__ == "__main__":
    bot = PipelineTradingAlphaTelegram()
    threading.Thread(target=ejecutar_ciclo_continuo_bot, args=(bot,), daemon=True).start()
    iniciar_servidor_web()
