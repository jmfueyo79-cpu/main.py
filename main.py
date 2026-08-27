# -*- coding: utf-8 -*-
import datetime
from zoneinfo import ZoneInfo
import logging
import numpy as np
import pandas as pd
import requests
import yfinance as yf

# Silenciar logs internos de yfinance
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
AHORA_ESPAÑA = datetime.datetime.now(ZoneInfo("Europe/Madrid"))
hora_actual = AHORA_ESPAÑA.time()

if hora_actual < datetime.time(18, 0):
  RVOL_MINIMO_REQUERIDO = 2.0
  fase_mercado = "Apertura / Arranque Intradiario"
elif hora_actual < datetime.time(20, 0):
  RVOL_MINIMO_REQUERIDO = 3.0
  fase_mercado = "Ecuador de Sesión (Midday)"
else:
  RVOL_MINIMO_REQUERIDO = 4.0
  fase_mercado = "Tramo Final (Power Hour)"

print(f"--- ESCÁNER HIGH-ALPHA OPTIMIZADO: {fase_mercado.upper()} ---")
print(f"Exigencia de RVOL ajustada automáticamente a: {RVOL_MINIMO_REQUERIDO}x")

mensaje_inicio = (
    f"🚀 *ESCANEADOR HIGH-ALPHA v2 ACTIVADO* 🚀\n\n"
    f"• *Fase de Mercado:* `{fase_mercado}`\n"
    f"• *Filtro RVOL Dinámico:* `≥ {RVOL_MINIMO_REQUERIDO}x`\n"
    f"• *Filtros Avanzados:* Breakout 20D | Precio ($1.50 - $30.00)\n"
    f"• *Filtros Nuevos:* Tendencia SMA200 | Cap. Negociación | Toes Exhaustión (<25%)\n"
    f"⏳ *Estado:* Analizando mercado y filtrando riesgos..."
)
enviar_alerta_telegram(mensaje_inicio)


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
start_date = end_date - datetime.timedelta(days=250)  # Ampliado a 250 para SMA200

signals_list = []
mensajes_telegram = (
    "🔥 *ALERTA EXPLOSIVA FILTRADA (SWING PRO)* 🔥\n"
    "----------------------------------------\n\n"
)
hay_senales = False


# ==============================================================================
# 4. PROCESAMIENTO TÉCNICO Y FILTRADO AVANZADO
# ==============================================================================
for ticker in TOP_UNIVERSE:
  try:
    tk = yf.Ticker(ticker)

    # 1. Filtro de Noticias / Earnings (-2 a +3 días)
    has_near_earnings = False
    try:
      earnings_df = tk.get_earnings_dates(limit=4)
      if earnings_df is not None and not earnings_df.empty:
        today_ts = pd.Timestamp(datetime.date.today())
        for idx in earnings_df.index:
          earn_date = pd.Timestamp(idx).tz_localize(None).normalize()
          diff_days = (earn_date - today_ts).days
          if -2 <= diff_days <= 3:
            has_near_earnings = True
            break
    except Exception:
      pass

    if has_near_earnings:
      continue

    # 2. Descarga de datos históricos (mínimo 200 sesiones para la SMA200)
    df = tk.history(start=start_date, end=end_date, auto_adjust=False)

    if df is None or df.empty or len(df) < 200:
      continue

    df = df.dropna()

    # Indicadores técnicos
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df["ATR"] = true_range.rolling(window=14).mean()

    df["Vol_Media_10"] = df["Volume"].rolling(window=10).mean()
    df["SMA_200"] = df["Close"].rolling(window=200).mean()

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    close_price = float(last_row["Close"])
    volume = float(last_row["Volume"])
    prev_close = float(prev_row["Close"])
    atr = float(last_row["ATR"])
    vol_media_10 = float(last_row["Vol_Media_10"])
    sma_200 = float(last_row["SMA_200"])

    # Métricas clave
    rvol_diario = volume / vol_media_10 if vol_media_10 > 0 else 0.0
    variacion_dia = ((close_price - prev_close) / prev_close) * 100
    volumen_efectivo_usd = close_price * volume

    # Breakout del máximo de los últimos 20 días (excluyendo la vela actual)
    max_20d = df["High"].iloc[-21:-1].max()
    es_breakout = close_price > max_20d

    # CONDICIONALES DE ENTRADA MEJORADAS
    is_valid_price = 1.50 <= close_price <= 30.00
    is_high_rvol = rvol_diario >= RVOL_MINIMO_REQUERIDO
    # Rango saludable: sube al menos 4% pero NO se excede del 25% (evita clímax de techo)
    is_healthy_move = 4.0 <= variacion_dia <= 25.00
    # Filtro de Tendencia Macro: Precio por encima de la SMA de 200
    is_above_sma200 = close_price > sma_200
    # Filtro de Liquidez Mínima: Al menos $5 millones negociados en la sesión
    has_liquidity = volumen_efectivo_usd >= 5_000_000

    if (
        es_breakout
        and is_valid_price
        and is_high_rvol
        and is_healthy_move
        and is_above_sma200
        and has_liquidity
    ):
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
            "Volumen Negociado ($M)": round(volumen_efectivo_usd / 1e6, 2),
            "Stop Loss ($)": round(stop_loss_price, 2),
            "Acciones": shares_to_buy,
            "Inversión ($)": round(total_investment, 2),
        })

        mensajes_telegram += (
            f"📡 *ALERTA FILTRADA: `{ticker}`*\n"
            f"🚨 *Tipo:* `{cat_alerta}`\n"
            f"📈 *Variación Sesión:* `+{round(variacion_dia, 2)}%`\n"
            f"📊 *RVOL Acumulado:* `🔥 {round(rvol_diario, 1)}x media`\n"
            f"💰 *Precio Actual:* `${round(close_price, 2)} USD`\n"
            f"🌊 *Volumen Negociado:* `${round(volumen_efectivo_usd / 1e6, 2)}M`\n"
            f"🛡️ *Stop Loss (3.0x ATR):* `${round(stop_loss_price, 2)} USD`\n"
            f"🔢 *Acciones Recomendadas:* `{shares_to_buy}`\n"
            f"⚖️ *Riesgo Controlado:* `$200 (1%)`\n"
            f"----------------------------------------\n\n"
        )

  except Exception:
    continue


# ==============================================================================
# 5. ENVÍO DE RESULTADOS
# ==============================================================================
result_df = pd.DataFrame(signals_list)

if hay_senales:
  print("¡Candidatos de alta calidad detectados bajo los filtros pro!")
  print(result_df)
  enviar_alerta_telegram(mensajes_telegram)
else:
  print(
      f"Escaneo completado a las {hora_actual.strftime('%H:%M')}. Sin alertas"
      " que cumplan con la tendencia SMA200 y los filtros de liquidez."
  )
  enviar_alerta_telegram(
      f"🔍 *Escaneo Finalizado ({fase_mercado})*\nNingún activo superó los"
      f" filtros estrictos (Breakout 20D, RVOL ≥ {RVOL_MINIMO_REQUERIDO}x,"
      " SMA200 y volumen monetario)."
  )
