# -*- coding: utf-8 -*-
import datetime
from zoneinfo import ZoneInfo
import logging
import numpy as np
import pandas as pd
import requests
import yfinance as yf

# Silenciar logs internos de yfinance para mantener la consola limpia
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ==============================================================================
# 1. CONFIGURACIÓN DE TELEGRAM
# ==============================================================================
TELEGRAM_TOKEN = "8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys"
TELEGRAM_CHAT_ID = "2047038250"


def enviar_alerta_telegram(mensaje):
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {
      "chat_id": TELEGRAM_CHAT_ID,
      "text": mensaje,
      "parse_mode": "Markdown",
  }
  try:
    response = requests.post(url, json=payload, timeout=5)
    if response.status_code != 200:
      print(f"Error al enviar a Telegram: {response.text}")
  except Exception as e:
    print(f"Excepción al conectar con Telegram: {e}")


# ==============================================================================
# 2. ADAPTACIÓN DINÁMICA DEL UMBRAL DE RVOL SEGÚN LA HORA DE LA SESIÓN
# ==============================================================================
# Forzar la hora local de España para que el Cron Job dispare el filtro correcto
AHORA_ESPAÑA = datetime.datetime.now(ZoneInfo("Europe/Madrid"))
hora_actual = AHORA_ESPAÑA.time()

# El mercado abre a las 15:30 y cierra a las 22:00 (Hora Española - CEST)
if hora_actual < datetime.time(18, 0):
  RVOL_MINIMO_REQUERIDO = 2.0
  fase_mercado = "Apertura / Arranque Intradiario"
elif hora_actual < datetime.time(20, 0):
  RVOL_MINIMO_REQUERIDO = 3.0
  fase_mercado = "Ecuador de Sesión (Midday)"
else:
  RVOL_MINIMO_REQUERIDO = 4.0
  fase_mercado = "Tramo Final (Power Hour)"

print(f"--- ESCÁNER RENDER CRON EN FASE: {fase_mercado.upper()} ---")
print(f"Exigencia de RVOL ajustada automáticamente a: {RVOL_MINIMO_REQUERIDO}x")


# ==============================================================================
# 3. OBTENCIÓN DINÁMICA DE TOP GAINERS Y WATCHLIST
# ==============================================================================
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


TOP_UNIVERSE = obtener_universo()

TOTAL_CAPITAL = 20000.0
RISK_PERCENTAGE = 0.01  # Riesgo del 1% por operación
MAX_RISK_USD = TOTAL_CAPITAL * RISK_PERCENTAGE

end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=120)

signals_list = []
mensajes_telegram = (
    "🔥 *ALERTA EXPLOSIVA DETECTADA (>50% RALLIES)* 🔥\n"
    "----------------------------------------\n\n"
)
hay_senales = False


# ==============================================================================
# 4. PROCESAMIENTO TÉCNICO Y FILTRADO
# ==============================================================================
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

    # 1. Indicador ATR (14 períodos)
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df["ATR"] = true_range.rolling(window=14).mean()

    # 2. Promedio de volumen diario de 10 ruedas
    df["Vol_Media_10"] = df["Volume"].rolling(window=10).mean()

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    close_price = float(last_row["Close"])
    volume = float(last_row["Volume"])
    prev_close = float(prev_row["Close"])
    atr = float(last_row["ATR"])
    vol_media_10 = float(last_row["Vol_Media_10"])

    # Cálculo del RVOL acumulado
    rvol_diario = volume / vol_media_10 if vol_media_10 > 0 else 0.0
    variacion_dia = ((close_price - prev_close) / prev_close) * 100

    # 3. Filtro Estructural: Breakout del máximo de los últimos 20 días
    max_20d = df["High"].iloc[-21:-1].max()
    es_breakout = close_price > max_20d

    # CONDICIONALES APLICADOS
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
            "🔥 SÚPER COHETE" if rvol_diario >= 6.0 else "⚡ BREAKOUT DE MOMENTUM"
        )

        signals_list.append({
            "Ticker": ticker,
            "Tipo": cat_alerta,
            "Variación Día": f"+{round(variacion_dia, 2)}%",
            "Precio ($)": round(close_price, 2),
            "RVOL": f"{round(rvol_diario, 1)}x",
            "Breakout 20D ($)": round(max_20d, 2),
            "Stop Loss ($)": round(stop_loss_price, 2),
            "Acciones": shares_to_buy,
            "Inversión ($)": round(total_investment, 2),
        })

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


# ==============================================================================
# 5. ENVÍO DE RESULTADOS Y CIERRE DEL SCRIPT
# ==============================================================================
result_df = pd.DataFrame(signals_list)

if hay_senales:
  print("¡Patrones de alta probabilidad detectados!")
  print(result_df)
  enviar_alerta_telegram(mensajes_telegram)
else:
  print(
      f"Escaneo completado a las {hora_actual.strftime('%H:%M')}. Sin alertas"
      " hoy."
  )
  # Opcional: si no quieres que avise a Telegram cada vez que esté vacía la lista,
  # puedes comentar la línea de abajo para evitar spam en el móvil.
  enviar_alerta_telegram(
      f"🔍 *Escaneo Finalizado ({fase_mercado})*\nNingún activo superó los"
      f" filtros de Breakout 20D y RVOL ≥ {RVOL_MINIMO_REQUERIDO}x en este"
      " pase."
  )
