# -*- coding: utf-8 -*-
import datetime
from zoneinfo import ZoneInfo
import logging
import os
import numpy as np
import pandas as pd
import requests
from flask import Flask
import yfinance as yf

# Silenciar logs internos de yfinance
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Inicializar Flask para que cron-job.org pueda activarlo vía HTTP
app = Flask(__name__)


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
# 2. FUNCIÓN PRINCIPAL DE ESCANEO
# ==============================================================================
def ejecutar_escaner_completo():
  AHORA_ESPAÑA = datetime.datetime.now(ZoneInfo("Europe/Madrid"))
  hora_actual = AHORA_ESPAÑA.time()

  if hora_actual < datetime.time(18, 0):
    RVOL_MINIMO_REQUERIDO = 1.5
    fase_mercado = "Apertura / Arranque Intradiario"
  elif hora_actual < datetime.time(20, 0):
    RVOL_MINIMO_REQUERIDO = 2.0
    fase_mercado = "Ecuador de Sesión (Midday)"
  else:
    RVOL_MINIMO_REQUERIDO = 2.5
    fase_mercado = "Tramo Final (Power Hour)"

  print(f"--- ESCÁNER RALLIES + SPREAD & VOLUMEN: {fase_mercado.upper()} ---")
  print(f"Exigencia de RVOL ajustada a: {RVOL_MINIMO_REQUERIDO}x")

  mensaje_inicio = (
      f"🚀 *ESCANEADOR RALLIES PRO ACTIVADO* 🚀\n\n"
      f"• *Fase de Mercado:* `{fase_mercado}`\n"
      f"• *Filtro RVOL Dinámico:* `≥ {RVOL_MINIMO_REQUERIDO}x`\n"
      f"• *Filtros Avanzados:* Breakout 20D | Precio ($1.00 - $50.00)\n"
      f"• *Filtros Pro:* Cap ($20M-$5B) | Liq ($1M+) | Spread Máx 3% | Vol."
      f" Temprano\n"
      f"⏳ *Estado:* Analizando liquidez y profundidad de mercado..."
  )
  enviar_alerta_telegram(mensaje_inicio)

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
        "HIMS",
        "MARA",
        "RIOT",
    ]
    return list(set(tickers_gainers + base_watchlist))

  TOP_UNIVERSE = obtener_universo()

  TOTAL_CAPITAL = 20000.0
  RISK_PERCENTAGE = 0.01
  MAX_RISK_USD = TOTAL_CAPITAL * RISK_PERCENTAGE

  end_date = datetime.date.today()
  start_date = end_date - datetime.timedelta(days=250)

  signals_list = []
  mensajes_telegram = (
      "🔥 *ALERTA DE RALLIES DETECTADA (FILTRADA)* 🔥\n"
      "----------------------------------------\n\n"
  )
  hay_senales = False

  for ticker in TOP_UNIVERSE:
    try:
      tk = yf.Ticker(ticker)
      info_dict = tk.info

      try:
        market_cap = info_dict.get("marketCap", 0)
        if market_cap and not (20_000_000 <= market_cap <= 5_000_000_000):
          continue
      except Exception:
        pass

      spread_val_pct = 0.0
      is_tight_spread = True
      try:
        bid = info_dict.get("bid", 0)
        ask = info_dict.get("ask", 0)
        if bid and ask and ask > bid:
          spread_val_pct = ((ask - bid) / ask) * 100
          if spread_val_pct > 3.0:
            is_tight_spread = False
      except Exception:
        pass

      if not is_tight_spread:
        continue

      has_recent_news = False
      try:
        news_list = tk.news
        if news_list and isinstance(news_list, list):
          now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
          limite_tiempo_seg = 48 * 3600
          for item in news_list:
            pub_time = item.get("providerPublishTime")
            if pub_time and isinstance(pub_time, (int, float)):
              if (now_ts - pub_time) <= limite_tiempo_seg:
                has_recent_news = True
                break
      except Exception:
        pass

      has_recent_insider_buying = False
      try:
        insider_df = tk.insider_purchases
        if insider_df is not None and not insider_df.empty:
          date_col = None
          for col in ["Start Date", "Date", "Filing Date"]:
            if col in insider_df.columns:
              date_col = col
              break

          if date_col and "Shares" in insider_df.columns:
            insider_df[date_col] = pd.to_datetime(
                insider_df[date_col], errors="coerce"
            )
            limite_fecha = pd.Timestamp(datetime.date.today()) - pd.Timedelta(
                days=30
            )
            compras_recientes = insider_df[
                (insider_df[date_col] >= limite_fecha)
                & (insider_df["Shares"] > 0)
            ]
            if not compras_recientes.empty:
              has_recent_insider_buying = True
      except Exception:
        pass

      df = tk.history(start=start_date, end=end_date, auto_adjust=False)

      if df is None or df.empty or len(df) < 100:
        continue

      df = df.dropna()

      has_strong_early_volume = True
      try:
        df_intra = tk.history(period="1d", interval="30m")
        if df_intra is not None and len(df_intra) >= 2:
          early_vol = df_intra["Volume"].iloc[:2].sum()
          total_vol_today = df_intra["Volume"].sum()
          if total_vol_today > 0:
            if (early_vol / total_vol_today) < 0.12:
              has_strong_early_volume = False
      except Exception:
        pass

      if not has_strong_early_volume:
        continue

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

      rvol_diario = volume / vol_media_10 if vol_media_10 > 0 else 0.0
      variacion_dia = ((close_price - prev_close) / prev_close) * 100
      volumen_efectivo_usd = close_price * volume

      max_20d = df["High"].iloc[-21:-1].max()
      es_breakout = close_price > max_20d

      atr_previo_5d = df["ATR"].iloc[-6:-1].mean()
      atr_largo_20d = df["ATR"].iloc[-25:-5].mean()
      is_compressed = atr_previo_5d < atr_largo_20d

      hist_highs = df["High"].iloc[:-5]
      higher_highs = hist_highs[hist_highs > close_price]
      if not higher_highs.empty:
        resistencia_precio = float(higher_highs.max())
        distancia_res_pct = (
            (resistencia_precio - close_price) / close_price
        ) * 100
        resistencia_tag = (
            f"${round(resistencia_precio, 2)} (+{round(distancia_res_pct, 1)}%)"
        )
      else:
        resistencia_tag = "🚀 Cielo despejado (Máximo anual)"

      is_valid_price = 1.00 <= close_price <= 50.00
      is_high_rvol = rvol_diario >= RVOL_MINIMO_REQUERIDO
      is_healthy_move = 3.0 <= variacion_dia <= 35.00
      has_liquidity = volumen_efectivo_usd >= 1_000_000

      if (
          es_breakout
          and is_valid_price
          and is_high_rvol
          and is_healthy_move
          and has_liquidity
          and is_compressed
      ):
        stop_loss_price = close_price - (2.5 * atr)
        risk_per_share = close_price - stop_loss_price

        if risk_per_share > 0:
          shares_to_buy = int(MAX_RISK_USD / risk_per_share)
          total_investment = shares_to_buy * close_price
          hay_senales = True

          cat_alerta = (
              "🔥 RALLY EXPLOSIVO" if rvol_diario >= 4.0 else "⚡ IMPULSO INICIAL"
          )
          news_tag = "✅ Sí (Catalizador)" if has_recent_news else "❌ No Detectada"
          insider_tag = "✅ Sí" if has_recent_insider_buying else "❌ No"
          spread_tag = (
              f"{round(spread_val_pct, 2)}%"
              if spread_val_pct > 0
              else "Normal (<3%)"
          )

          mensajes_telegram += (
              f"📡 *ALERTA RALLY: `{ticker}`*\n"
              f"🚨 *Tipo:* `{cat_alerta}`\n"
              f"📈 *Variación:* `+{round(variacion_dia, 2)}%`\n"
              f"📊 *RVOL:* `🔥 {round(rvol_diario, 1)}x`\n"
              f"💰 *Precio:* `${round(close_price, 2)} USD`\n"
              f"🌊 *Volumen Inicial / Total:* `✅ Fuerte`\n"
              f"📐 *Spread Bid/Ask:* `{spread_tag}`\n"
              f"🧱 *Próxima Resistencia:* `{resistencia_tag}`\n"
              f"📰 *Noticia Reciente (48h):* `{news_tag}`\n"
              f"👔 *Compra Insiders (<30d):* `{insider_tag}`\n"
              f"🛡️ *Stop Loss:* `${round(stop_loss_price, 2)} USD`\n"
              f"🔢 *Acciones:* `{shares_to_buy}`\n"
              f"----------------------------------------\n\n"
          )

    except Exception:
      continue

  if hay_senales:
    enviar_alerta_telegram(mensajes_telegram)
  else:
    enviar_alerta_telegram(
        f"🔍 *Escaneo Finalizado ({fase_mercado})*\nNingún activo superó los"
        f" filtros estrictos de spread, volumen temprano y RVOL ≥"
        f" {RVOL_MINIMO_REQUERIDO}x."
    )


# ==============================================================================
# 3. ENDPOINT WEB PARA CRON-JOB.ORG
# ==============================================================================
@app.route("/")
def index():
  # Cada vez que cron-job.org haga una petición HTTP a tu URL, ejecutará el escáner
  ejecutar_escaner_completo()
  return "Escaneo ejecutado correctamente desde cron-job.org", 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
