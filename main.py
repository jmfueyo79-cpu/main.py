# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import threading
import numpy as np
import pandas as pd
import requests
import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)


class WebServerHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(
        b"Bot V12-Total Activo con Trailing Dinamico Progresivo (>50%)"
    )


class PipelineTradingAlphaTelegram:

  def __init__(self):
    self.archivo = "estado_remolazo_final.json"
    self.estado = self.cargar_estado()

    # PARAMETRIZACIÓN OPTIMIZADA PARA BÚSQUEDA DE MOVIMIENTOS PARABÓLICOS (>50%)
    self.config = {
        "price_range": (1.50, 20.0),
        "rvol_diario_min": 4.0,
        "rvol_15m_min": 5.0,
        "rsi_range": (50, 80),
        "trailing_atr_multiplier": 3.0,
        "lockout_minutes": 15,
        "trailing_trigger_percent": 0.05,
        "breakout_days": 20,
    }
    self.enviar_tg(
        "🛡️ *SISTEMA V12-HIGH ALPHA CON TRAIL DINÁMICO PROGRESIVO ACTIVADO*"
    )

  def cargar_estado(self):
    if os.path.exists(self.archivo):
      with open(self.archivo, "r") as f:
        return json.load(f)
    return {"posiciones": {}}

  def guardar_estado(self):
    with open(self.archivo, "w") as f:
      json.dump(self.estado, f, indent=4)

  def enviar_tg(self, msg):
    try:
      requests.post(
          "https://api.telegram.org/bot8620604654:AAEsvDlxfzCpICHtTyMg0HYApvKXwzJ9Xys/sendMessage",
          json={
              "chat_id": "2047038250",
              "text": msg,
              "parse_mode": "Markdown",
          },
          timeout=5,
      )
    except:
      pass

  def obtener_tickers(self):
    try:
      url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds=day_gainers&count=50"
      r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
      quotes = r.json()["finance"]["result"][0]["quotes"]
      dynamic_tickers = [
          q["symbol"].replace(".", "-")
          for q in quotes
          if "^" not in q["symbol"] and len(q["symbol"]) <= 5
      ]
    except:
      dynamic_tickers = []

    acciones_explosivas = [
        "NVDA",
        "TSLA",
        "PLTR",
        "COIN",
        "SMCI",
        "AMD",
        "MRVL",
        "HOOD",
        "CRWD",
        "ARM",
        "AVGO",
        "MSFT",
        "META",
        "NFLX",
        "QCOM",
        "MU",
        "APP",
        "MSTR",
        "ANF",
        "CELH",
        "AXON",
        "RDDT",
        "IONQ",
        "RGTI",
        "ASTS",
        "LUNR",
        "RKLB",
        "TEM",
        "SOFI",
        "AFRM",
        "PANW",
        "NET",
        "ZS",
        "DDOG",
        "SNOW",
        "DKNG",
        "UBER",
        "ABNB",
        "GME",
        "CVNA",
        "UPST",
        "OPEN",
        "PLUG",
        "MARA",
        "RIOT",
        "CLSK",
        "BYND",
        "NIO",
        "XPEV",
        "LI",
        "FFAI",
        "ALLO",
        "CRDF",
        "ALT",
        "IOVA",
        "CHRS",
        "AVXL",
        "TNXP",
    ]

    return list(set(dynamic_tickers + acciones_explosivas))

  def procesar(self):
    tickers = self.obtener_tickers()
    if not tickers:
      return

    df_d = yf.download(
        " ".join(tickers),
        period="3m",
        interval="1d",
        group_by="ticker",
        progress=False,
    )
    df_i = yf.download(
        " ".join(tickers),
        period="5d",
        interval="15m",
        group_by="ticker",
        progress=False,
    )

    for ticker in tickers:
      try:
        dd = (
            df_d[ticker].dropna() if len(tickers) > 1 else df_d.dropna()
        )
        di = (
            df_i[ticker].dropna() if len(tickers) > 1 else df_i.dropna()
        )

        if dd.empty or di.empty or len(dd) < 21 or len(di) < 20:
          continue

        p = di["Close"].iloc[-1]

        if not (
            self.config["price_range"][0]
            <= p
            <= self.config["price_range"][1]
        ):
          continue

        max_20d = dd["High"].iloc[-21:-1].max()
        es_breakout = p > max_20d

        vol_hoy_acumulado = di["Volume"].iloc[-26:].sum()
        vol_media_10d = dd["Volume"].iloc[-11:-1].mean()
        rvol_diario = (
            vol_hoy_acumulado / vol_media_10d if vol_media_10d > 0 else 0
        )

        vol_15m_actual = di["Volume"].iloc[-1]
        vol_15m_media = di["Volume"].rolling(20).mean().iloc[-1]
        rvol_15m = vol_15m_actual / vol_15m_media if vol_15m_media > 0 else 0

        change = di["Close"].diff()
        gain = change.clip(lower=0).rolling(14).mean()
        loss = -change.clip(upper=0).rolling(14).mean()
        rsi = (
            100 - (100 / (1 + (gain.iloc[-1] / loss.iloc[-1])))
            if loss.iloc[-1] != 0
            else 100
        )

        if (
            es_breakout
            and rvol_diario >= self.config["rvol_diario_min"]
            and rvol_15m >= self.config["rvol_15m_min"]
            and (self.config["rsi_range"][0] <= rsi <= self.config["rsi_range"][1])
            and ticker not in self.estado["posiciones"]
        ):

          cat = (
              "🔥 SÚPER COHETE CONFIRMADO (Breakout + RVOL Extremo)"
              if rvol_diario >= 8.0
              else "⚡ BREAKOUT DE MOMENTUM ALTA PROBABILIDAD"
          )

          self.estado["posiciones"][ticker] = {
              "entrada": p,
              "max": p,
              "ultimo_stop_notificado": 0.0,
              "timestamp": datetime.now().isoformat(),
              "active_trailing": False,
          }

          msg = (
              f"📡 *ALERTA EXPLOSIVA {ticker}*\n"
              f"🚨 {cat}\n"
              f"💰 Precio Entrada: `{p:.4f}` (Breakout 20D: `{max_20d:.2f}`)\n"
              f"📊 RVOL Diario: `{rvol_diario:.1f}x` | Vol 15m: `{rvol_15m:.1f}x`\n"
              f"📈 RSI 15m: `{rsi:.1f}`"
          )
          self.enviar_tg(msg)
          self.guardar_estado()
      except:
        pass

  def gestionar_maximizar(self):
    tickers = list(self.estado["posiciones"].keys())
    if not tickers:
      return
    df = yf.download(
        " ".join(tickers),
        period="2d",
        interval="15m",
        group_by="ticker",
        progress=False,
    )

    for ticker in tickers:
      try:
        data = (
            df[ticker].dropna() if len(tickers) > 1 else df.dropna()
        )
        if data.empty:
          continue

        p = data["Close"].iloc[-1]
        pos = self.estado["posiciones"][ticker]

        entry_time = datetime.fromisoformat(pos["timestamp"])
        if (
            datetime.now() - entry_time
            < timedelta(minutes=self.config["lockout_minutes"])
        ):
          continue

        rend = ((p - pos["entrada"]) / pos["entrada"]) * 100
        if rend >= (self.config["trailing_trigger_percent"] * 100):
          pos["active_trailing"] = True

        # Gestión de Trailing Stop adaptado (3.0x ATR) dejando correr el 100%
        if pos["active_trailing"]:
          atr = (data["High"] - data["Low"]).rolling(14).mean().iloc[-1]
          if p > pos["max"]:
            pos["max"] = p

          stop_loss = pos["max"] - (
              self.config["trailing_atr_multiplier"] * atr
          )

          # Si el stop dinámico ha subido de forma apreciable respecto al último aviso (ej. al menos un 3% arriba), avisa sin saturar
          if (
              pos["ultimo_stop_notificado"] == 0.0
              or stop_loss > pos["ultimo_stop_notificado"] * 1.03
          ):
            if rend >= 5.0:  # Solo avisa si ya va en positivo relevante
              pos["ultimo_stop_notificado"] = stop_loss
              msg_pro = (
                  f"🔄 *ACTUALIZACIÓN TRAILING {ticker}*\n"
                  f"📈 Beneficio Latente: `+{rend:.2f}%`\n"
                  f"💵 Precio Actual: `{p:.4f}`\n"
                  f"🛡️ Nuevo Stop Dinámico: `{stop_loss:.4f}`"
              )
              self.enviar_tg(msg_pro)

          if p <= stop_loss:
            self.enviar_tg(
                f"🚨 *SALIDA POR STOP EN {ticker}* 🛑\n"
                f"📊 Rendimiento Final Acumulado: `{rend:.2f}%`"
            )
            del self.estado["posiciones"][ticker]

        self.guardar_estado()
      except:
        pass


def ejecutar(bot):
  while True:
    if datetime.now().weekday() < 5:
      bot.gestionar_maximizar()
      bot.procesar()
    time.sleep(300)


def iniciar_servidor_web():
  puerto = int(os.environ.get("PORT", 10000))
  server = HTTPServer(("0.0.0.0", puerto), WebServerHandler)
  server.serve_forever()


if __name__ == "__main__":
  bot = PipelineTradingAlphaTelegram()
  threading.Thread(target=ejecutar, args=(bot,), daemon=True).start()
  iniciar_servidor_web()
