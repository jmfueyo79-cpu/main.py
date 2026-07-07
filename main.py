# -*- coding: utf-8 -*-
import os
import json
import requests
import logging
import random
import pandas as pd
import yfinance as yf
import time

# SILENCIAR ADVERTENCIAS DE YFINANCE EN LOS LOGS
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        """
        Pipeline Cuantitativo Intradiario (Intervalo 30 Minutos).
        Optimizado para ejecutarse de Lunes a Viernes de 16:00 a 22:00 con Cron-Job.org.
        """
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        
        # Tus fijas que NUNCA se quitan del radar
        self.tus_favoritas = ["CRDF", "IOVA", "ALT", "HUMA", "IREN"]
        
        # BANCO MASIVO DE EXPLORACIÓN (+350 Activos Especulativos, Cripto, IA y Biotech)
        self.banco_total_activos = [
            # --- SECTOR BIOTECH & PHARMA ---
            "NVAX", "CELH", "GFAI", "ANVS", "AMAM", "KPTI", "PTGX", "MDGL", "VKTX", "CYTK",
            "RIGL", "CTXR", "AVXL", "BCRX", "GERN", "CRSP", "NTLA", "BEAM", "EDIT", "VERV",
            "BLUE", "SGMO", "SRPT", "BMRN", "PTCT", "ALNY", "IONIS", "EXAS", "GH", "GUARD",
            "AADI", "ABVC", "ACAD", "ACER", "ACET", "ACHV", "ACIU", "ACRS", "ACST", "ACTG",
            "ALEC", "ALIM", "ALKS", "ALLR", "ALNA", "ALXO", "AMED", "AMTI", "ANGI", "ANKR",
            "APLS", "APLT", "APRE", "APTO", "APYX", "AQST", "ARDX", "ARQT", "ARWR", "ASMB",
            "ASND", "ATNX", "ATOM", "ATOS", "ATRA", "ATRC", "AURA", "AUPH", "AUR", "AVDL",
            "AVIR", "AVTE", "AXSM", "AXLA", "AZTA", "BCAB", "BCDA", "BMEA", "BNGO", "BPMC",
            "BTAI", "CARS", "CARA", "CATX", "CCXI", "CDMO", "CDNA", "CDTX", "CDXC", "CELC",
            "CERE", "CGEN", "CGON", "CHRS", "CHYI", "CLDX", "CLSD", "CLVS", "CMPS", "CMRX",
            "CNCE", "CNTA", "CNTG", "COGT", "COLL", "CORT", "CRNX", "CRBU", "CRMD", "CRTX",
            # --- SECTOR CRIPTO, MINERÍA & BLOCKCHAIN ---
            "MARA", "RIOT", "CLSK", "WULF", "COIN", "MSTR", "CIFR", "CORZ", "HUT", "BTBT",
            "SDIG", "COWG", "MIGI", "CAN", "BOF", "BTCM", "GREE", "SOS", "BITF", "DGHI",
            # --- SECTOR IA, ROBÓTICA & BIG DATA ---
            "PLTR", "SOFI", "HOOD", "AFRM", "UPST", "AI", "BBAI", "SOUN", "PATH", "C3AI",
            "NVDA", "AMD", "SMCI", "ARM", "TSM", "MU", "INTC", "MRVL", "PLUG", "SNOW",
            "ASAN", "MDB", "DDOG", "CRWD", "NET", "OKTA", "ZS", "PANW", "FTNT", "QLYS",
            "S", "U", "UNITY", "RBLX", "SE", "MELI", "SHOP", "SQ", "PYPL", "DOCU",
            # --- SECTOR VEHÍCULOS ELÉCTRICOS, ENERGÍA LIMPIA & TECNOLOGÍA ---
            "RIVN", "LCID", "TLRY", "FCEL", "BLNK", "RUN", "CHPT", "NKLA", "QS",
            "ENVX", "FREY", "EVGO", "BE", "TPWR", "STEM", "SUNW", "MAXN", "CSIQ",
            "BABA", "DKNG", "XPEV", "NIO", "LI", "JD", "PDD", "FUTU", "TIGR", "TSLA",
            "WKHS", "GOEV", "HYLN", "PTRA", "XOS", "REE", "CANO", "ZEV", "ARGO"
        ]
        
        self.estado = self.cargar_estado()

    def cargar_estado(self):
        if os.path.exists(self.archivo_estado):
            try:
                with open(self.archivo_estado, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"posiciones_abiertas": {}}

    def guardar_estado(self):
        try:
            with open(self.archivo_estado, 'w') as f:
                json.dump(self.estado, f, indent=4)
        except:
            pass

    def generar_watchlist_exploratoria(self, tamano_total=100):
        """
        Mantiene tus 5 favoritas fijas y añade el resto de forma aleatoria del banco masivo.
        """
        pool_disponible = list(set(self.banco_total_activos) - set(self.tus_favoritas))
        cuantas_sortear = tamano_total - len(self.tus_favoritas)
        muestra_aleatoria = random.sample(pool_disponible, min(cuantas_sortear, len(pool_disponible)))
        return self.tus_favoritas + muestra_aleatoria

    def enviar_telegram(self, mensaje):
        if not self.telegram_token or not self.telegram_chat_id:
            return
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat_id, "text": mensaje, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=8)
        except:
            pass

    @staticmethod
    def calcular_atr(df, periodo=14):
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        rangos = pd.concat([high_low, high_close, low_close], axis=1)
        return rangos.max(axis=1).rolling(window=period).mean()

    def escanear_intradiario(self, watchlist):
        print(f"[ESCÁNER] Iniciando barrido intradiario sobre {len(watchlist)} activos...")
        tickers_string = " ".join(watchlist)
        
        try:
            # Descarga de datos en marcos temporales de 30 minutos
            datos_mercado = yf.download(tickers_string, period="3d", interval="30m", group_by="ticker", progress=False, timeout=40)
        except Exception as e:
            print(f"[ESCÁNER ERROR] Fallo al conectar con Yahoo Finance: {e}")
            return

        for ticker in watchlist:
            try:
                if ticker not in datos_mercado.columns.levels[0]:
                    continue
                df = datos_mercado[ticker].dropna()
                
                if len(df) < 25:
                    continue
                
                df['Vol_Media_20'] = df['Volume'].rolling(window=20).mean()
                df['ATR_14'] = self.calcular_atr(df, 14)
                
                hoy = df.iloc[-1]
                
                if hoy['Vol_Media_20'] < 10000:  # Umbral mínimo de liquidez en la vela de 30m
                    continue
                    
                ratio_volumen = hoy['Volume'] / hoy['Vol_Media_20']
                anomalia_volumen = ratio_volumen > 2.8
                
                cuerpo_vela = abs(hoy['Close'] - hoy['Open'])
                precio_en_rango = cuerpo_vela < (hoy['ATR_14'] * 1.2)
                absorcion_compras = (hoy['Close'] - hoy['Low']) > (cuerpo_vela * 0.6)
                
                if anomalia_volumen and precio_en_rango and absorcion_compras:
                    if ticker not in self.estado["posiciones_abiertas"]:
                        atr_actual = hoy['ATR_14']
                        precio_entrada = hoy['Close']
                        stop_loss_inicial = precio_entrada - (2.5 * atr_actual)
                        
                        self.estado["posiciones_abiertas"][ticker] = {
                            "precio_entrada": round(precio_entrada, 4),
                            "stop_loss": round(stop_loss_inicial, 4),
                            "max_precio_visto": round(precio_entrada, 4),
                            "ultimo_rendimiento_notificado": 0.0
                        }
                        
                        msg = (
                            f"🔥 *ALERTA INTRADIARIA RECIENTE (30m)* 🔥\n\n"
                            f"📈 *Activo:* `{ticker}`\n"
                            f"💰 *Precio Actual:* `${precio_entrada:.2f}`\n"
                            f"📊 *Volumen Institucional:* `{ratio_volumen:.1f}x` MAV20\n"
                            f"🛡️ *Stop Inicial Sugerido:* `${stop_loss_inicial:.2f}` (2.5x ATR)"
                        )
                        self.enviar_telegram(msg)
                        self.guardar_estado()
                        
            except:
                pass

    def gestionar_trailing_stops(self):
        if not self.estado["posiciones_abiertas"]:
            return

        tickers_abiertos = list(self.estado["posiciones_abiertas"].keys())
        tickers_string = " ".join(tickers_abiertos)
        
        try:
            datos_mercado = yf.download(tickers_string, period="3d", interval="30m", group_by="ticker", progress=False, timeout=15)
        except:
            return

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
            except:
                pass

if __name__ == '__main__':
    print("[BOT] Iniciando ciclo de escaneo intradiario 30 minutos...")
    bot = PipelineTradingAlphaTelegram()
    
    # Generamos una lista combinada de 100 activos (Tus 5 TOP fijos + 95 rotativos del banco)
    watchlist_de_hoy = bot.generar_watchlist_exploratoria(tamano_total=100)
    
    # Notificación obligatoria de inicio de ciclo a Telegram
    bot.enviar_telegram(f"🔄 *Rotador Activo (30m):* Analizando 100 activos en mercado abierto.")
    
    # Ejecutamos el análisis intradiario y las salidas por trailing
    bot.escanear_intradiario(watchlist_de_hoy)
    bot.gestionar_trailing_stops()
    
    print("[BOT] Ciclo completado con éxito. Entrando en modo reposo controlado...")
    
    # Bucle de mantenimiento de 5 minutos: mantiene el deploy en VERDE dentro de Render
    # y libera el recurso a tiempo antes del siguiente toque de Cron-job.org
    while True:
        time.sleep(300)
