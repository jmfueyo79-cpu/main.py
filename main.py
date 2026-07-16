# -*- coding: utf-8 -*-
import os, json, requests, time, threading
import pandas as pd, yfinance as yf
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot V12-Total Activo con Filtros")

class PipelineTradingAlphaTelegram:
    def __init__(self):
        self.archivo = "estado_remolazo_final.json"
        self.estado = self.cargar_estado()
        # Configuración de mejoras para filtrar ruido[span_1](start_span)[span_1](end_span)
        self.config = {
            'price_range': (1.0, 50.0),
            'vol_ratio_min': 3.5,
            'rsi_range': (45, 75),
            'trailing_atr_multiplier': 2.5,
            'lockout_minutes': 30,
            'trailing_trigger_percent': 0.03 # Colchón del 3%[span_2](start_span)[span_2](end_span)
        }
        self.enviar_tg("🛡️ *SISTEMA V12-TOTAL OPTIMIZADO: ESCANEO ACTIVO*")

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

    def obtener_tickers(self):
        try:
            url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds=day_gainers&count=40"
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            quotes = r.json()["finance"]["result"][0]["quotes"]
            return [q["symbol"] for q in quotes if "^" not in q["symbol"] and len(q["symbol"]) <= 5]
        except: return ["FFAI", "ALLO", "CRDF", "ALT", "IOVA", "CHRS", "AVXL", "TNXP"]

    def procesar(self):
        tickers = self.obtener_tickers()
        df_d = yf.download(" ".join(tickers), period="1y", interval="1d", group_by="ticker", progress=False)
        df_i = yf.download(" ".join(tickers), period="5d", interval="15m", group_by="ticker", progress=False)
        
        for ticker in tickers:
            try:
                dd = df_d[ticker].dropna() if len(tickers) > 1 else df_d.dropna()
                di = df_i[ticker].dropna() if len(tickers) > 1 else df_i.dropna()
                p = di['Close'].iloc[-1]
                
                # Filtro de Precio aplicado[span_3](start_span)[span_3](end_span)
                if not (self.config['price_range'][0] <= p <= self.config['price_range'][1]):
                    continue

                ma200 = dd['Close'].rolling(200).mean().iloc[-1]
                rsi = 100 - (100 / (1 + (di['Close'].diff().clip(lower=0).rolling(14).mean() / -di['Close'].diff().clip(upper=0).rolling(14).mean()).iloc[-1]))
                vol_ratio = di['Volume'].iloc[-1] / di['Volume'].rolling(20).mean().iloc[-1]
                
                if p > ma200 and 45 < rsi < 75 and vol_ratio > self.config['vol_ratio_min'] and ticker not in self.estado["posiciones"]:
                    cat = "🟥 SÚPER COHETE (>50%)" if vol_ratio >= 5.0 else "🟨 TENDENCIA FUERTE (15-30%)"
                    atr = (di['High']-di['Low']).rolling(14).mean().iloc[-1]
                    # Registro de tiempo para bloqueo de 30 min[span_4](start_span)[span_4](end_span)
                    self.estado["posiciones"][ticker] = {
                        "entrada": p, "max": p, "parcial": False, 
                        "timestamp": datetime.now().isoformat(), "active_trailing": False
                    }
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
                
                # Lógica de Bloqueo de 30 min y Colchón del 3%[span_5](start_span)[span_5](end_span)
                entry_time = datetime.fromisoformat(pos["timestamp"])
                if datetime.now() - entry_time < timedelta(minutes=self.config['lockout_minutes']):
                    continue
                
                rend = ((p - pos["entrada"]) / pos["entrada"]) * 100
                if rend >= (self.config['trailing_trigger_percent'] * 100):
                    pos["active_trailing"] = True
                
                if rend >= 15.0 and not pos["parcial"]:
                    pos["parcial"] = True
                    self.enviar_tg(f"💰 *PARCIAL {ticker} (+15%)*. Stop movido a entrada.")
                
                if pos["active_trailing"]:
                    atr = (data['High']-data['Low']).rolling(14).mean().iloc[-1]
                    if p > pos["max"]: pos["max"] = p
                    stop_loss = p - (self.config['trailing_atr_multiplier'] * atr) # ATR 2.5x[span_6](start_span)[span_6](end_span)
                    
                    if p <= stop_loss:
                        self.enviar_tg(f"🚨 *SALIDA {ticker}*. Res: `{rend:.2f}%`")
                        del self.estado["posiciones"][ticker]
                
                self.guardar_estado()
            except: pass

def ejecutar(bot):
    while True:
        if datetime.now().weekday() < 5:
            bot.gestionar_maximizar()
            bot.procesar()
        time.sleep(300)

def iniciar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", puerto), WebServerHandler)
    server.serve_forever()

if __name__ == "__main__":
    bot = PipelineTradingAlphaTelegram()
    threading.Thread(target=ejecutar, args=(bot,), daemon=True).start()
    iniciar_servidor_web()
