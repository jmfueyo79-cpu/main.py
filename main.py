# -*- coding: utf-8 -*-
import os, json, requests, time, threading
import pandas as pd, yfinance as yf
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- CLASE PRINCIPAL ---
class PipelineTradingAlphaTelegram:
    def __init__(self):
        self.archivo = "estado_remolazo_final.json"
        self.activos = ["FFAI", "ALLO", "CRDF", "ALT", "IOVA", "CHRS", "AVXL", "TNXP"]
        self.estado = self.cargar_estado()
        self.enviar_tg("🛡️ *SISTEMA V12: AUTOMATIZADO, FILTRADO Y GESTIONADO*")

    def cargar_estado(self):
        if os.path.exists(self.archivo):
            with open(self.archivo, 'r') as f: return json.load(f)
        return {"posiciones": {}}

    def guardar_estado(self):
        with open(self.archivo, 'w') as f: json.dump(self.estado, f, indent=4)

    def enviar_tg(self, msg):
        try: requests.post(f"https://api.telegram.org/bot8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys/sendMessage", 
                           json={"chat_id": "2047038250", "text": msg, "parse_mode": "Markdown"}, timeout=5)
        except: pass

    def procesar(self):
        df_d = yf.download(" ".join(self.activos), period="1y", interval="1d", group_by="ticker", progress=False)
        df_i = yf.download(" ".join(self.activos), period="5d", interval="15m", group_by="ticker", progress=False)

        for ticker in self.activos:
            try:
                # Filtrado de datos
                dd = df_d[ticker].dropna() if len(self.activos) > 1 else df_d.dropna()
                di = df_i[ticker].dropna() if len(self.activos) > 1 else df_i.dropna()
                
                p = di['Close'].iloc[-1]
                ma200 = dd['Close'].rolling(200).mean().iloc[-1]
                rsi = 100 - (100 / (1 + (di['Close'].diff().clip(lower=0).rolling(14).mean() / -di['Close'].diff().clip(upper=0).rolling(14).mean()).iloc[-1]))
                vol_ratio = di['Volume'].iloc[-1] / di['Volume'].rolling(20).mean().iloc[-1]
                
                # ENTRADA AUTOMÁTICA Y CLASIFICACIÓN
                if p > ma200 and 30 < rsi < 85 and vol_ratio > 2.5 and ticker not in self.estado["posiciones"]:
                    cat = "🟥 SÚPER COHETE (>50%)" if vol_ratio >= 4.0 else "🟨 TENDENCIA FUERTE (15-30%)"
                    atr = (di['High']-di['Low']).rolling(14).mean().iloc[-1]
                    
                    self.estado["posiciones"][ticker] = {"entrada": p, "stop": p - (2.2 * atr), "max": p, "parcial": False}
                    self.enviar_tg(f"📡 *ALERTA {ticker}*\n🚨 {cat}\n💰 Precio: `{p:.4f}`\n📊 Vol: `{vol_ratio:.1f}x` | RSI: `{rsi:.1f}`")
                    self.guardar_estado()
            except: pass

    def gestionar_maximizar(self):
        tickers = list(self.estado["posiciones"].keys())
        if not tickers: return
        df = yf.download(" ".join(tickers), period="2d", interval="15m", group_by="ticker", progress=False)
        
        for ticker in tickers:
            try:
                data = df[ticker].dropna() if len(tickers) > 1 else df.dropna()
                p = data['Close'].iloc[-1]
                pos = self.estado["posiciones"][ticker]
                rend = ((p - pos["entrada"]) / pos["entrada"]) * 100
                
                # GANANCIAS INFINITAS: Sube el stop y asegura parciales
                if rend >= 15.0 and not pos["parcial"]:
                    pos["parcial"] = True; pos["stop"] = pos["entrada"]
                    self.enviar_tg(f"💰 *PARCIAL {ticker} (+15%)*. Stop movido a entrada.")
                
                if p > pos["max"]:
                    pos["max"] = p
                    pos["stop"] = p - (1.5 * (data['High']-data['Low']).rolling(14).mean().iloc[-1])
                
                if p <= pos["stop"]:
                    self.enviar_tg(f"🚨 *SALIDA {ticker}*. Res: `{rend:.2f}%`")
                    del self.estado["posiciones"][ticker]
                self.guardar_estado()
            except: pass

# --- BUCLE Y SERVIDOR ---
def ejecutar(bot):
    while True:
        if datetime.now().weekday() < 5:
            bot.gestionar_maximizar()
            bot.procesar()
        time.sleep(300)

if __name__ == "__main__":
    bot = PipelineTradingAlphaTelegram()
    threading.Thread(target=ejecutar, args=(bot,), daemon=True).start()
    # Iniciar servidor web aquí... (tu código estándar)
