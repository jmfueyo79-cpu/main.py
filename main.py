# -*- coding: utf-8 -*-
import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

class PipelineTradingAlphaTelegram:
    def __init__(self, api_key_polygon, telegram_token="8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys", telegram_chat_id="2047038250", archivo_estado="estado_alpha_trading.json"):
        """
        Pipeline Cuantitativo Avanzado con Escáner Diario Masivo.
        Detecta anomalías automáticamente en todo el mercado americano sin usar endpoints restringidos.
        """
        self.api_key = api_key_polygon
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.archivo_estado = archivo_estado
        self.estado = self.cargar_estado()
        
    def cargar_estado(self):
        if os.path.exists(self.archivo_estado):
            try:
                with open(self.archivo_estado, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR PERSISTENCIA] Re-inicializando estado: {e}")
        
        return {
            "watchlist_activa": ["CRDF", "IOVA", "ALT", "HUMA", "IREN"],
            "posiciones_abiertas": {},
            "alertas_historicas": []
        }

    def guardar_estado(self):
        try:
            with open(self.archivo_estado, 'w') as f:
                json.dump(self.estado, f, indent=4)
        except Exception as e:
            print(f"[ERROR PERSISTENCIA] Imposible guardar estado en JSON: {e}")

    def enviar_telegram(self, mensaje):
        print(f"[TELEGRAM LOG]:\n{mensaje}\n")
        if not self.telegram_token or not self.telegram_chat_id:
            return
            
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=payload, timeout=8)
            if response.status_code != 200:
                print(f"[TELEGRAM ERROR] Código erróneo: {response.status_code}")
        except Exception as e:
            print(f"[TELEGRAM EXCEPCIÓN] Fallo de conexión: {e}")

    def obtener_datos_historicos(self, ticker, dias=30):
        """Descarga el histórico corto para calcular la media de volumen y ATR de un candidato."""
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2026-05-01/2026-07-07"
        params = {"adjusted": "true", "sort": "asc", "limit": dias, "apiKey": self.api_key}
        try:
            response = requests.get(url, params=params, timeout=8)
            if response.status_code == 200:
                data = response.json()
                if "results" in data and len(data["results"]) > 0:
                    df = pd.DataFrame(data["results"])
                    df = df.rename(columns={'c': 'Close', 'o': 'Open', 'h': 'High', 'l': 'Low', 'v': 'Volume'})
                    return df
        except:
            pass
        return None

    @staticmethod
    def calcular_atr(df, periodo=14):
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        rangos = pd.concat([high_low, high_close, low_close], axis=1)
        return rangos.max(axis=1).rolling(window=period).mean()

    def escanear_mercado_completo_auto(self):
        """
        ESCÁNER AUTOMÁTICO REAL: Descarga los datos de TODO el mercado de EE.UU. 
        del día actual y filtra los activos que tengan anomalías salvajes de volumen.
        """
        print("[ESCÁNER] Iniciando barrido masivo del mercado americano...")
        
        # Usamos el último día laborable del que haya datos (Ajustar dinámicamente si es necesario)
        fecha_consulta = "2026-07-07" 
        url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{fecha_consulta}"
        params = {"adjusted": "true", "apiKey": self.api_key}
        
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code != 200:
                print(f"[ESCÁNER ERROR] No se pudo acceder a los datos agrupados. Código: {response.status_code}")
                return
                
            datos = response.json()
            if "results" not in datos:
                print("[ESCÁNER INFO] No se encontraron resultados para la fecha especificada.")
                return
                
            print(f"[ESCÁNER] Analizando {len(datos['results'])} tickers en tiempo real...")
            
            for activo in datos["results"]:
                ticker = activo.get("T")
                # Filtro rápido de liquidez para descartar ruido de inmediato
                volumen_hoy = activo.get("v", 0)
                if volumen_hoy < 150000:
                    continue
                    
                cierre_hoy = activo.get("c", 0)
                apertura_hoy = activo.get("o", 0)
                maximo_hoy = activo.get("h", 0)
                minimo_hoy = activo.get("l", 0)
                
                # Si el ticker está en posiciones abiertas, lo saltamos del escáner de entrada
                if ticker in self.estado["posiciones_abiertas"]:
                    continue
                    
                # Descargamos su histórico para comprobar si el volumen actual es una anomalía respecto a sus 20 días previos
                df_hist = self.obtener_datos_historicos(ticker)
                if df_hist is None or len(df_hist) < 20:
                    continue
                    
                vol_media_20 = df_hist['Volume'].mean()
                ratio_volumen = volumen_hoy / vol_media_20
                
                # CONDICIÓN 1: Volumen anómalo institucional (> 2.8 veces la media)
                if ratio_volumen > 2.8:
                    df_hist['ATR_14'] = self.calcular_atr(df_hist, 14)
                    atr_actual = df_hist['ATR_14'].iloc[-1] if not pd.isna(df_hist['ATR_14'].iloc[-1]) else (maximo_hoy - minimo_hoy)
                    
                    cuerpo_vela = abs(cierre_hoy - apertura_hoy)
                    
                    # CONDICIÓN 2 y 3: Absorción de compras en la parte alta y rango controlado
                    precio_en_rango = cuerpo_vela < (atr_actual * 1.2)
                    absorcion_compras = (cierre_hoy - minimo_hoy) > (cuerpo_vela * 0.6)
                    
                    if precio_en_rango and absorcion_compras:
                        # Acción detectada automáticamente con éxito
                        stop_loss_inicial = cierre_hoy - (2.5 * atr_actual)
                        
                        self.estado["posiciones_abiertas"][ticker] = {
                            "precio_entrada": round(cierre_hoy, 4),
                            "stop_loss": round(stop_loss_inicial, 4),
                            "max_precio_visto": round(cierre_hoy, 4),
                            "atr_en_entrada": round(atr_actual, 4),
                            "ultimo_rendimiento_notificado": 0.0
                        }
                        
                        msg = (
                            f"🚀 *¡ALERTA DE ENTRADA ALPHA (AUTO)!* 🚀\n\n"
                            f"📈 *Activo Detectado:* `{ticker}`\n"
                            f"💰 *Precio Entrada:* `${cierre_hoy:.2f}`\n"
                            f"📊 *Volumen hoy:* `{volumen_hoy:,}`\n"
                            f"🔥 *Anomalía Volumen:* `{ratio_volumen:.1f}x` MAV20\n"
                            f"🛡️ *Stop Loss Inicial:* `${stop_loss_inicial:.2f}` (2.5x ATR)\n"
                            f"🎯 *Objetivo Asimétrico:* >+50% de Rentabilidad"
                        )
                        self.enviar_telegram(msg)
                        self.guardar_estado()
                        
        except Exception as e:
            print(f"[ESCÁNER EXCEPCIÓN] Error crítico durante el filtrado de mercado: {e}")

    def gestionar_monitoreo_y_trailing_stops(self):
        """Monitoriza las posiciones que se han abierto de forma automática para gestionar sus salidas."""
        if not self.estado["posiciones_abiertas"]:
            print("[MONITOR] Sin posiciones abiertas que vigilar.")
            return

        print(f"[MONITOR] Vigilando {len(self.estado['posiciones_abiertas'])} posiciones activas...")
        for ticker, pos in list(self.estado["posiciones_abiertas"].items()):
            df = self.obtener_datos_historicos(ticker)
            if df is None: 
                continue
            
            hoy = df.iloc[-1]
            precio_actual = hoy['Close']
            df['ATR_14'] = self.calcular_atr(df, 14)
            atr_actual = df['ATR_14'].iloc[-1]
            
            rendimiento_acumulado = ((precio_actual - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
            
            # Subir máximo visto y recalcular trailing stop dinámico
            if precio_actual > pos["max_precio_visto"]:
                pos["max_precio_visto"] = round(precio_actual, 4)
                nuevo_stop = precio_actual - (2.2 * atr_actual)
                if nuevo_stop > pos["stop_loss"]:
                    pos["stop_loss"] = round(nuevo_stop, 4)
            
            # Alertas parciales cada 5% de beneficio
            if rendimiento_acumulado - pos["ultimo_rendimiento_notificado"] >= 5.0:
                pos["ultimo_rendimiento_notificado"] = round(rendimiento_acumulado, 2)
                msg = (
                    f"⚡ *ACTUALIZACIÓN DE RENDIMIENTO* ⚡\n\n"
                    f"💎 *Activo:* `{ticker}`\n"
                    f"💵 *Precio Actual:* `${precio_actual:.2f}`\n"
                    f"🔥 *Rendimiento Acumulado:* `+{rendimiento_acumulado:.2f}%`\n"
                    f"🛡️ *Trailing Stop Elevado a:* `${pos['stop_loss']:.2f}`"
                )
                self.enviar_telegram(msg)
                self.guardar_estado()
                
            # Verificar salida por stop loss
            if precio_actual <= pos["stop_loss"]:
                rendimiento_final = ((pos["stop_loss"] - pos["precio_entrada"]) / pos["precio_entrada"]) * 100
                msg = (
                    f"🚨 *DISPARO DE TRAILING STOP / SALIDA* 🚨\n\n"
                    f"📉 *Activo:* `{ticker}`\n"
                    f"🚪 *Precio de Salida:* `${pos['stop_loss']:.2f}`\n"
                    f"💰 *Rendimiento Final Neto:* `+{rendimiento_final:.2f}%`"
                )
                self.enviar_telegram(msg)
                del self.estado["posiciones_abiertas"][ticker]
                self.guardar_estado()

if __name__ == '__main__':
    print("[CRON] Iniciando motor de detección automática algorítmica...")
    
    # Carga la API Key guardada en Render
    api_key_polygon = os.environ.get("POLYGON_API_KEY", "TU_POLYGON_API_KEY_REAL")
    
    bot = PipelineTradingAlphaTelegram(api_key_polygon=api_key_polygon)
    
    # 1. Barre todo el mercado, calcula indicadores y detecta las ganadoras de hoy solo
    bot.escanear_mercado_completo_auto()
    
    # 2. Gestiona las salidas de las posiciones que sigan vivas
    bot.gestionar_monitoreo_y_trailing_stops()
    
    print("[CRON] Proceso completado de forma limpia.")
