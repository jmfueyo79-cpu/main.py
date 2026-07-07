# -*- coding: utf-8 -*-
import os
import json
import requests
import logging
import random
import pandas as pd
import yfinance as yf
import time

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        self.tus_favoritas = ["CRDF", "IOVA", "ALT", "HUMA", "IREN"]
        self.banco_total_activos = ["NVAX", "CELH", "GFAI", "ANVS", "AMAM", "KPTI", "PTGX", "MDGL", "VKTX", "CYTK", "MARA", "RIOT", "CLSK", "PLTR", "SOFI", "HOOD", "AFRM", "UPST", "AI", "NVDA", "AMD", "SMCI", "RIVN", "LCID"] # Amplía aquí tu lista
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
        muestra = random.sample(pool_disponible, min(cuantas_sortear, len(pool_disponible)))
        return self.tus_favoritas + muestra

    def enviar_telegram(self, mensaje):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat_id, "text": mensaje, "parse_mode": "Markdown"}
        try: requests.post(url, json=payload, timeout=5)
        except: pass

    @staticmethod
    def calcular_atr(df, periodo=14):
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(window=periodo).mean()

    def escanear_intradiario(self, watchlist):
        tickers_string = " ".join(watchlist)
        # ESCANEO INTRADIARIO: Intervalo de 1 hora
        datos = yf.download(tickers_string, period="5d", interval="1h", group_by="ticker", progress=False)
        
        for ticker in watchlist:
            try:
                df = datos[ticker].dropna()
                if len(df) < 20: continue
                
                hoy = df.iloc[-1]
                vol_ma = df['Volume'].rolling(window=20).mean().iloc[-1]
                
                # CONDICIÓN INTRADIARIA: Volumen > 2.8x media horaria
                if hoy['Volume'] > (vol_ma * 2.8):
                    if ticker not in self.estado["posiciones_abiertas"]:
                        msg = f"🚀 *ALERTA INTRADIARIA* 🚀\n\n📈 *Activo:* `{ticker}`\n💰 *Volumen Explosivo:* `{hoy['Volume']/vol_ma:.1f}x` MAV20\n🎯 *Marco:* 1 hora"
                        self.enviar_telegram(msg)
            except: continue

if __name__ == '__main__':
    print("[BOT] Iniciando ciclo de escaneo continuo...")
    bot = PipelineTradingAlphaTelegram()
    
    # Ejecución principal
    watchlist = bot.generar_watchlist_exploratoria(tamano_total=100)
    bot.escanear_intradiario(watchlist)
    
    print("[BOT] Ciclo completado. Entrando en reposo...")
    
    # Bucle para mantener el deploy vivo en Render (evita el "Failed")
    while True:
        time.sleep(600) # Espera 10 minutos antes de que cron-job.org te despierte otra vez
