# -*- coding: utf-8 -*-
import os
import json
import requests
import pandas as pd
import numpy as np
import yfinance as yf

class PipelineTradingAlphaTelegram:
    def __init__(self, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        """
        Pipeline Cuantitativo de Autodetección Masiva Ampliado (Yahoo Finance).
        Analiza dinámicamente decenas de activos sin restricciones de API Key ni errores 401.
        """
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        self.estado = self.cargar_estado()
        
    def cargar_estado(self):
        if os.path.exists(self.archivo_estado):
            try:
                with open(self.archivo_estado, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # UNIVERSO AMPLADO AUTOMÁTICO (Biotech, Growth, IA, Cripto y Semiconductores)
        return {
            "watchlist_base": [
                # Tus Favoritas de Cabecera
                "CRDF", "IOVA", "ALT", "HUMA", "IREN", 
                # Biotech & Pharma de Alta Volatilidad (Small/Mid Caps)
                "NVAX", "CELH", "GFAI", "ANVS", "AMAM", "KPTI", "PTGX", "MDGL", "VKTX", "CYTK",
                "RIGL", "CTXR", "AGRX", "AVXL", "SAVA", "TIER", "TRIL", "BCRX", "KERX", "GERN",
                # Cripto, Blockchain & Minería (Anomalías salvajes de volumen)
                "MARA", "RIOT", "CLSK", "WULF", "COIN", "MSTR", "CIFR", "CORZ", "HUT", "BTBT",
                # Inteligencia Artificial, Big Data & Crecimiento (Growth)
                "PLTR", "SOFI", "HOOD", "AFRM", "UPST", "AI", "BBAI", "SOUN", "PATH", "C3AI",
                # Semiconductores & Hardware de Alto Rendimiento
                "AMD", "NVDA", "SMCI", "ARM", "TSM", "MU", "INTC", "MRVL", "CELH",
                # Vehículos Eléctricos, Energía Limpia & Especulativas Activas
                "RIVN", "LCID", "PLUG", "TLRY", "FCEL", "BLNK", "RUN", "CHPT", "Fisker", "NKLA",
                # Gigantes Tecnológicos de Alta Liquidez (Para balancear rango de volatilidad)
                "BABA", "DKNG", "XPEV", "NIO", "LI", "JD", "PDD", "FUTU", "TIGR"
            ],
            "posiciones_abiertas": {}
        }

    def guardar_estado(self):
        try:
            with open(self.archivo_estado, 'w') as f:
                json.dump(self.estado, f, indent=4)
        except Exception as e:
            print(f"[ERROR PERSISTENCIA] No se pudo guardar el JSON: {e}")

    def enviar_telegram(self, mensaje):
        print(f"[TELEGRAM LOG]:\n{mensaje}\n")
        if not self.telegram_token or not self.telegram_chat_id:
            return
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat_id, "text": mensaje, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=8)
        except Exception as e:
            print(f"[TELEGRAM ERROR] Fallo de envío: {e}")

    @staticmethod
    def calcular_atr(df, periodo=14):
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        rangos = pd.concat([high_low, high_close, low_close], axis=1)
        return rangos.max(axis=1).rolling(window=period).mean()

    def escanear_y_detectar_auto(self):
        print(f"[ESCÁNER] Iniciando barrido automático sobre {len(self.estado['watchlist_base'])} activos de alto potencial...")
        
        # Descarga masiva del mercado en un solo bloque ultra rápido
        tickers_string = " ".join(self.estado["watchlist_base"])
        try:
            datos_mercado = yf.download(tickers_string, period="60d", group_by="ticker", progress=False, timeout=30)
        except Exception as e:
            print(f"[ESCÁNER ERROR] Fallo al conectar con Yahoo Finance: {e}")
            return

        for ticker in self.estado["watchlist_base"]:
            try:
                if ticker not in datos_mercado.columns.levels[0]:
                    continue
                df = datos_mercado[ticker].dropna()
                
                if len(df) < 30:
                    continue
                
                # Cálculo de filtros cuantitativos
                df['Vol_Media_20'] = df['Volume'].rolling(window=20).mean()
                df['ATR_14'] = self.calcular_atr(df, 14)
                
                hoy = df.iloc[-1]
                
                # Ignorar completamente si no tiene liquidez mínima operativa
                if hoy['Vol_Media_20'] < 100000:
                    continue
                    
                ratio_volumen = hoy['Volume'] / hoy['Vol_Media_20']
                
                # CONDICIÓN DE FILTRADO INSTITUCIONAL (>2.8 veces el volumen promedio)
                anomalia_volumen = ratio_volumen > 2.8
                
                cuerpo_vela = abs(hoy['Close'] - hoy['Open'])
                precio_en_rango = cuerpo_vela < (hoy['ATR_14'] * 1.2)
                absorcion_compras = (hoy['Close'] - hoy['Low']) > (cuerpo_vela * 0.6)
                
                if anomalia_volumen and precio_en_rango and absorcion_compras:
                    # Si cumple todo y no está ya abierta, se caza automáticamente
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
                            f"🚀 *¡ACCÓN DETECTADA AUTOMÁTICAMENTE!* 🚀\n\n"
                            f"📈 *Activo Creado:* `{ticker}`\n"
                            f"💰 *Precio Entrada:* `${precio_entrada:.2f}`\n"
                            f"📊 *Anomalía Volumen:* `{ratio_volumen:.1f}x` MAV20\n"
                            f"🛡️ *Stop Loss Inicial:* `${stop_loss_inicial:.2f}` (2.5x ATR)\n"
                            f"🎯 *Estrategia:* Compresión con Volumen Institucional"
                        )
                        self.enviar_telegram(msg)
                        self.guardar_estado()
                        
            except Exception as e:
                pass

    def gestionar_trailing_stops(self):
        if not self.estado["posiciones_abiertas"]:
            print("[MONITOR] Sin posiciones activas que vigilar.")
            return

        print(f"[MONITOR] Gestionando trailing stops de {len(self.estado['posiciones_abiertas'])} activos...")
        tickers_abiertos = list(self.estado["posiciones_abiertas"].keys())
        tickers_string = " ".join(tickers_abiertos)
        
        try:
            datos_mercado = yf.download(tickers_string, period="30d", group_by="ticker", progress=False, timeout=15)
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
                
                # Actualizar trailing stop si marca máximos crecientes
                if precio_actual > pos["max_precio_visto"]:
                    pos["max_precio_visto"] = round(precio_actual, 4)
                    nuevo_stop = precio_actual - (2.2 * atr_actual)
                    if nuevo_stop > pos["stop_loss"]:
                        pos["stop_loss"] = round(nuevo_stop, 4)
                
                # Notificación por cada tramo del 5% capturado
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
                    
                # Comprobación de salida
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
    print("[CRON] Iniciando motor automático de detección ampliado...")
    
    bot = PipelineTradingAlphaTelegram()
    
    # 1. Escaneo en bloque de los sectores calientes del mercado de EEUU
    bot.escanear_y_detectar_auto()
    
    # 2. Gestión automatizada de Trailing Stops
    bot.gestionar_trailing_stops()
    
    print("[CRON] Proceso finalizado correctamente.")
