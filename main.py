# -*- coding: utf-8 -*-
import os, json, requests, pandas as pd, yfinance as yf, time, threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer

# CONFIGURACIÓN SILENCIOSA
import logging
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)

# --- SERVIDOR WEB AUXILIAR ESTÁNDAR (Garantiza el paso de pings de Render) ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot Activo y Patrullando")

    def log_message(self, format, *args): 
        return  # Silencia los logs de peticiones HTTP para mantener limpia la consola

def iniciar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", puerto), WebServerHandler)
    print(f"🌍 Servidor Web de pings levantado con éxito en el puerto {puerto}")
    server.serve_forever()

# --- CLASE PRINCIPAL ---
class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250"):
        self.token = telegram_token
        self.chat_id = telegram_chat_id
        self.archivo = "estado_remolazo_final.json"
        self.activos = ["FFAI", "ALLO", "CRDF", "ALT", "IOVA", "CHRS", "AVXL", "TNXP"]
        self.estado = self.cargar_estado()
        self.enviar_tg("🛡️ *SISTEMA REMOLAZO V10 (FILTRADO) ACTIVADO*\nFiltro EMA20 + RSI + Maximización Infinita.")

    def cargar_estado(self):
        if os.path.exists(self.archivo):
            try:
                with open(self.archivo, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"posiciones": {}}

    def guardar_estado(self):
        with open(self.archivo, 'w') as f: json.dump(self.estado, f, indent=4)

    def enviar_tg(self, msg):
        try: requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage", json={"chat_id": self.chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
        except: pass

    def obtener_ganadoras(self):
        try:
            url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds=day_gainers&count=40"
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            quotes = r.json()["finance"]["result"][0]["quotes"]
            return list(set(self.activos + [q["symbol"] for q in quotes if "^" not in q["symbol"] and len(q["symbol"]) <= 5]))
        except: return self.activos

    def procesar(self):
        tickers = self.obtener_ganadoras()
        try: df_m = yf.download(" ".join(tickers), period="10d", interval="15m", group_by="ticker", progress=False)
        except: return

        for ticker in tickers:
            try:
                df = df_m[ticker].dropna() if len(tickers) > 1 else df_m.dropna()
                if len(df) < 30: continue
                
                p = df['Close'].iloc[-1]
                ema20 = df['Close'].ewm(span=20).mean().iloc[-1]
                
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
                
                vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
                
                if vol_ratio > 2.5 and p > ema20 and rsi > 50 and ticker not in self.estado["posiciones"]:
                    
                    if vol_ratio >= 4.0: cat = "🟥 SÚPER COHETE (>50%)"
                    elif 2.5 <= vol_ratio < 4.0: cat = "🟨 TENDENCIA FUERTE (15-30%)"
                    else: cat = "🟦 MOMENTUM ESTÁNDAR (5-15%)"
                    
                    atr = (df['High']-df['Low']).rolling(14).mean().iloc[-1]
                    self.estado["posiciones"][ticker] = {
                        "entrada": p, "stop": p - (2.2 * atr), "max": p, "parcial": False
                    }
                    self.enviar_tg(f"📡 *ALERTA {ticker}*\n🚨 {cat}\n💰 Entrada: `{p:.4f}`\n📊 Vol: `{vol_ratio:.1f}x` | RSI: `{rsi:.1f}`")
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
                
                if rend >= 15.0 and not pos["parcial"]:
                    pos["parcial"] = True
                    pos["stop"] = pos["entrada"]
                    self.enviar_tg(f"💰 *PARCIAL {ticker} (+15%)*. Stop en entrada. Dejando correr resto.")
                    self.guardar_estado()
                
                if p > pos["max"]:
                    pos["max"] = p
                    pos["stop"] = p - (1.5 * (df['High']-df['Low']).rolling(14).mean().iloc[-1])
                    self.guardar_estado()
                
                if p <= pos["stop"]:
                    self.enviar_tg(f"🚨 *SALIDA {ticker}*. Res: `{rend:.2f}%`")
                    del self.estado["posiciones"][ticker]
                    self.guardar_estado()
            except: pass

# --- BUCLE DE CONTROL EN SEGUNDO PLANO ---
def ejecutar_ciclo_continuo_bot(bot):
    print("🤖 Hilo del radar de trading iniciado en segundo plano.")
    while True:
        zona_local = pytz.timezone('Europe/Madrid')
        ahora = datetime.now(zona_local)
        
        # Lunes a Viernes de 15:00 a 22:00 CET
        if ahora.weekday() < 5 and (15 <= ahora.hour < 22):
            print(f"[{ahora.strftime('%H:%M:%S')}] Escaneando y gestionando posiciones...")
            bot.gestionar_maximizar()
            bot.procesar()
            time.sleep(300)  # Espera de 5 minutos
        else:
            time.sleep(60)   # Espera de 1 minuto fuera de horario

# --- EJECUCIÓN INICIAL ---
if __name__ == "__main__":
    # 1. Inicializar lógica
    bot = PipelineTradingAlphaTelegram()
    
    # 2. Arrancar el bot de trading en un hilo paralelo para que no bloquee a Render
    hilo_bot = threading.Thread(target=ejecutar_ciclo_continuo_bot, args=(bot,), daemon=True)
    hilo_bot.start()
    
    # 3. Levantar el servidor web en el hilo principal (Esto asegura el "200 OK" y responde correctamente a Render)
    iniciar_servidor_web()
