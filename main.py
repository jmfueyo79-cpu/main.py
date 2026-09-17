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
# 2. ADAPTACIÓN DINÁMICA DEL UMBRAL DE RVOL
# ==============================================================================
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
    f"• *Filtros Pro:* Cap ($20M-$5B) | Liq ($1M+) | Spread Máx 3% | Vol. Temprano\n"
    f"⏳ *Estado:* Analizando liquidez y profundidad de mercado..."
)
enviar_alerta_telegram(mensaje_inicio)


# ==============================================================================
# 3. OBTENCIÓN DINÁMICA DE UNIVERSO
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


# ==============================================================================
# 4. PROCESAMIENTO TÉCNICO, SPREAD Y VOLUMEN TEMPRANO
# ==============================================================================
for ticker in TOP_UNIVERSE:
  try:
    tk = yf.Ticker(ticker)
    info_dict = tk.info

    # 1. Filtro de Capitalización de Mercado Ampliado ($20M - $5B)
    try:
      market_cap = info_dict.get("marketCap", 0)
      if market_cap and not (20_000_000 <= market_cap <= 5_000_000_000):
        continue
    except Exception:
      pass

    # 2. Filtro de Diferencial (Spread) entre Bid y Ask (< 3.0%)
    spread_val_pct = 0.0
    is_tight_spread = True
    try:
      bid = info_dict.get("bid", 0)
      ask = info_dict.get("ask", 0)
      close_temp = info_dict.get("previousClose", 0)
      if bid and ask and ask > bid:
        spread_val_pct = ((ask - bid) / ask) * 100
        if spread_val_pct > 3.0:  # Exige que el spread no supere el 3%
          is_tight_spread = False
    except Exception:
      pass

    if not is_tight_spread:
      continue

    # 3. Verificación de Noticias Recientes (< 48 horas)
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

    # 4. Verificación de Compras de Insiders en los últimos 30 días
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

    # 5. Descarga de datos históricos diarios
    df = tk.history(start=start_date, end=end_date, auto_adjust=False)

    if df is None or df.empty or len(df) < 100:
      continue

    df = df.dropna()

    # 6. Validación de Volumen en las Primeras Horas de la Sesión Actual
    has_strong_early_volume = True
    try:
      df_intra = tk.history(period="1d", interval="30m")
      if df_intra is not None and len(df_intra) >= 2:
        # Primeras 2 velas de 30 minutos (primera hora de sesión)
        early_vol = df_intra["Volume"].iloc[:2].sum()
        total_vol_today = df_intra["Volume"].sum()
        if total_vol_today > 0:
          # Exigimos que al menos el 12% del volumen diario se haya negociado en la primera hora
          if (early_vol / total_vol_today) < 0.12:
            has_strong_early_volume = False
    except Exception:
      pass

    if not has_strong_early_volume:
      continue

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
    sma_200 = (
        float(last_row["SMA_200"]) if not np.isnan(last_row["SMA_200"]) else 0.0
    )

    # Métricas clave
    rvol_diario = volume / vol_media_10 if vol_media_10 > 0 else 0.0
    variacion_dia = ((close_price - prev_close) / prev_close) * 100
    volumen_efectivo_usd = close_price * volume

    # Breakout del máximo de los últimos 20 días
    max_20d = df["High"].iloc[-21:-1].max()
    es_breakout = close_price > max_20d

    # Compresión previa evaluada en los días previos a la ruptura
    atr_previo_5d = df["ATR"].iloc[-6:-1].mean()
    atr_largo_20d = df["ATR"].iloc[-25:-5].mean()
    is_compressed = atr_previo_5d < atr_largo_20d

    # Cálculo de la Primera Resistencia Importante por encima
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

    # CONDICIONALES DE ENTRADA
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
        tendencia_tag = "✅ Alcista" if close_price > sma_200 else "⚠️ Giro Base"
        news_tag = "✅ Sí (Catalizador)" if has_recent_news else "❌ No Detectada"
        insider_tag = "✅ Sí" if has_recent_insider_buying else "❌ No"
        spread_tag = (
            f"{round(spread_val_pct, 2)}%"
            if spread_val_pct > 0
            else "Normal (<3%)"
        )

        signals_list.append({
            "Ticker": ticker,
            "Tipo": cat_alerta,
            "Variación Día": f"+{round(variacion_dia, 2)}%",
            "Precio ($)": round(close_price, 2),
            "RVOL": f"{round(rvol_diario, 1)}x",
            "Volumen ($M)": round(volumen_efectivo_usd / 1e6, 2),
            "Spread Bid/Ask": spread_tag,
            "Resistencia Arriba": resistencia_tag,
            "Noticia (48h)": news_tag,
            "Insider (30D)": insider_tag,
            "Stop Loss ($)": round(stop_loss_price, 2),
            "Acciones": shares_to_buy,
            "Inversión ($)": round(total_investment, 2),
        })

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


# ==============================================================================
# 5. ENVÍO DE RESULTADOS
# ==============================================================================
result_df = pd.DataFrame(signals_list)

if hay_senales:
  print("¡Candidatos de rally detectados con control de spread y volumen!")
  print(result_df)
  enviar_alerta_telegram(mensajes_telegram)
else:
  print(
      f"Escaneo completado a las {hora_actual.strftime('%H:%M')}. Sin alertas"
      " con los criterios actuales."
  )
  enviar_alerta_telegram(
      f"🔍 *Escaneo Finalizado ({fase_mercado})*\nNingún activo superó los"
      f" filtros estrictos de spread, volumen temprano y RVOL ≥"
      f" {RVOL_MINIMO_REQUERIDO}x."
  )
