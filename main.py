# -*- coding: utf-8 -*-
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import os
import threading
import time
import numpy as np
import pandas as pd
import requests
import yfinance as yf

# Silenciar logs internos de yfinance
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ==============================================================================
# 1. CONFIGURACIÓN
# ==============================================================================
TELEGRAM_TOKEN = "8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys"
TELEGRAM_CHAT_ID = "2047038250"

TOTAL_CAPITAL = 20000.0
RISK_PERCENTAGE = 0.01  # Riesgo del 1% ($200)
MAX_RISK_USD = TOTAL_CAPITAL * RISK_PERCENTAGE

# Control para no enviar mensajes repetidos de "sin señales" seguidos
ultimo_pase_notificado = ""


def enviar_alerta_telegram(mensaje):
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {
      "chat_id": TELEGRAM_CHAT_ID,
      "text": mensaje,
      "parse_mode": "Markdown",
  }
  try:
    requests.post(url, json=payload, timeout=5)
  except Exception as e:
    print(f"Error enviando a Telegram: {e}")


def obtener_universo():
  tickers_gainers = []
  try:
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds=day_gainers"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    data = response.json()
    quotes = (
        data.get("finance", {})
        .get("result", [{}])[0]
        .get("quotes", [])
    )

    for q in quotes:
      symbol = q.get("symbol")
      if symbol and "^" not in symbol and len(symbol) <= 5:
        tickers_gainers.append(symbol.replace(".", "-"))
  except Exception as e:
    print(f"Aviso al obtener top gainers: {e}")

  base_watchlist = [
      "FFAI",
      "ALLO",
      "CRDF",
      "ALT",
      "IOVA",
      "CHRS",
      "AVXL",
      "TNXP",
  ]
  return list(set(tickers_gainers + base_watchlist))


# ==============================================================================
# 2. ESCÁNER CON FILTRO ADAPTATIVO
# ==============================================================================
def ejecutar_escaneo(es_ping_rutinario=False):
  global ultimo_pase_notificado

  ahora = datetime.datetime.now()
  hora_actual = ahora.time()

  # 1. Verificar si el mercado está en horario de negociación (15:30 a 22:00 CEST)
  if not (datetime.time(15, 30) <= hora_actual <= datetime.time(22, 0)):
    # Si es fin de semana o fuera de hora, no escanea en cada ping para no sobrecargar
    if es_ping_rutinario:
      return

  # 2. Definir exigencia de RVOL según el tramo horario
  if hora_actual < datetime.time(18, 0):
    RVOL_MINIMO_REQUERIDO = 2.0
    fase_mercado = "Apertura / Arranque"
  elif hora_actual < datetime.time(20, 0):
    RVOL_MINIMO_REQUERIDO = 3.0
    fase_mercado = "Ecuador de Sesión (Midday)"
  else:
    RVOL_MINIMO_REQUERIDO = 4.0
    fase_mercado = "Power Hour / Cierre"

  TOP_UNIVERSE = obtener_universo()
  end_date = datetime.date.today()
  start_date = end_date - datetime.timedelta(days=120)

  mensajes_telegram = (
      "🔥 *ALERTA EXPLOSIVA DETECTADA (>50% RALLIES)* 🔥\n"
      "----------------------------------------\n\n"
  )
  hay_senales = False

  for ticker in TOP_UNIVERSE:
    try:
      df = yf.download(
          ticker,
          start=start_date,
          end=end_date,
          progress=False,
          auto_adjust=False,
          threads=False,
      )
      if df is None or df.empty or len(df) < 30:
        continue
      df = df.dropna()
      if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

      # ATR (14)
      high_low = df["High"] - df["Low"]
      high_close = np.abs(df["High"] - df["Close"].shift())
      low_close = np.abs(df["Low"] - df["Close"].shift())
      df["ATR"] = (
          np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
          .rolling(window=14)
          .mean()
      )

      # Media de Volumen (10D)
      df["Vol_Media_10"] = df["Volume"].rolling(window=10).mean()

      last_row, prev_row = df.iloc[-1], df.iloc[-2]
      close_price = float(last_row["Close"])
      volume = float(last_row["Volume"])
      prev_close = float(prev_row["Close"])
      atr = float(last_row["ATR"])
      vol_media_10 = float(last_row["Vol_Media_10"])

      rvol_diario = volume / vol_media_10 if vol_media_10 > 0 else 0.0
      variacion_dia = ((close_price - prev_close) / prev_close) * 100
      max_20d = df["High"].iloc[-21:-1].max()

      # CONDICIONES EXPLOSIVAS
      es_breakout = close_price > max_20d
      is_valid_price = 1.50 <= close_price <= 20.00
      is_high_rvol = rvol_diario >= RVOL_MINIMO_REQUERIDO
      is_strong_move = variacion_dia >= 4.0

      if es_breakout and is_valid_price and is_high_rvol and is_strong_move:
        stop_loss_price = close_price - (3.0 * atr)
        risk_per_share = close_price - stop_loss_price

        if risk_per_share > 0:
          shares_to_buy = int(MAX_RISK_USD / risk_per_share)
          total_investment = shares_to_buy * close_price
          hay_senales = True

          cat_alerta = (
              "🔥 SÚPER COHETE"
              if rvol_diario >= 6.0
              else "⚡ BREAKOUT DE MOMENTUM"
          )

          mensajes_telegram += (
              f"📡 *ALERTA EXPLOSIVA: `{ticker}`*\n"
              f"🚨 *Tipo:* `{cat_alerta}`\n"
              f"📈 *Variación Sesión:* `+{round(variacion_dia, 2)}%`\n"
              f"📊 *RVOL Acumulado:* `🔥 {round(rvol_diario, 1)}x media`\n"
              f"💰 *Precio Actual:* `${round(close_price, 2)} USD`\n"
              f"🎯 *Máximo 20D Superado:* `${round(max_20d, 2)} USD`\n"
              f"🛡️ *Stop Loss (3.0x ATR):* `${round(stop_loss_price, 2)} USD`\n"
              f"🔢 *Acciones Recomendadas:* `{shares_to_buy}`\n"
              f"⚖️ *Riesgo Controlado:* `$200 (1%)`\n"
              f"----------------------------------------\n\n"
          )
    except Exception:
      continue

  # SI HAY ALERTAS: Se envía inmediatamente en cualquier ping
  if hay_senales:
    enviar_alerta_telegram(mensajes_telegram)
    print(f"[{ahora.strftime('%H:%M')}] ¡Alertas enviadas a Telegram!")

  # SI NO HAY ALERTAS: Solo enviamos reporte informativo en las 3 horas clave para no hacer spam
  else:
    clave_hora = ahora.strftime("%H")
    # Esquinas de horas clave: 16:xx, 18:xx, 20:xx
    if clave_hora in ["16", "18", "20"] and ultimo_pase_notificado != clave_hora:
      enviar_alerta_telegram(
          f"🔍 *Revisión de Mercado ({fase_mercado})*\nMercado escaneado a las"
          f" {ahora.strftime('%H:%M')}. Sin activos superando RVOL"
          f" ≥ {RVOL_MINIMO_REQUERIDO}x por ahora."
      )
      ultimo_pase_notificado = clave_hora


# ==============================================================================
# 3. SERVIDOR WEB Y RECEPCIÓN DE PINGS (RENDER)
# ==============================================================================
class WebServerHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    # Cada vez que tu Cron Job hace un PING HTTP a Render:
    self.send_response(200)
    self.send_header("Content-type", "text/html; charset=utf-8")
    self.end_headers()
    self.wfile.write(
        b"Bot High-Alpha Activo. Servidor Render Despierto."
    )

    # Disparar escaneo en segundo plano para no demorar la respuesta HTTP
    threading.Thread(
        target=ejecutar_escaneo, kwargs={"es_ping_rutinario": True}
    ).start()

  def log_message(self, format, *args):
    return  # Silenciar logs HTTP habituales en consola


def iniciar_servidor_web():
  puerto = int(os.environ.get("PORT", 10000))
  server = HTTPServer(("0.0.0.0", puerto), WebServerHandler)
  print(f" Servidor iniciado en el puerto {puerto}. Listo para recibir pings.")
  server.serve_forever()


if __name__ == "__main__":
  iniciar_servidor_web()
