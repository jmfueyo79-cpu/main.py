import os
import time
import random
import pandas as pd
from polygon import RESTClient
import telepot

# --- CONFIGURACIÓN ---
POLYGON_KEY = os.environ.get("POLYGON_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = RESTClient(POLYGON_KEY)
bot = telepot.Bot(TELEGRAM_TOKEN)

class GestorFrancotirador:
    def __init__(self):
        self.posiciones = {}
        bot.sendMessage(TELEGRAM_CHAT_ID, "🚀 BOT RVOL: Escaneando activos con alta presión institucional")

    def es_volumen_inusual(self, ticker):
        """Verifica si el volumen actual es > 3x la media de los últimos 5 días"""
        try:
            # Obtenemos los últimos 5 días
            aggs = list(client.get_aggs(ticker, 1, "day", (pd.Timestamp.now() - pd.Timedelta(days=10)), pd.Timestamp.now()))
            if len(aggs) < 5: return False
            
            df = pd.DataFrame(aggs)
            vol_actual = df['volume'].iloc[-1]
            vol_media = df['volume'].iloc[-6:-1].mean()
            
            # Filtro: Volumen actual al menos 3 veces superior a la media
            return vol_actual > (vol_media * 3)
        except: return False

    def tiene_noticias_negativas(self, ticker):
        # ... (mantén tu lógica actual de noticias)
        return False 

    def calcular_atr(self, ticker):
        # ... (mantén tu lógica actual de ATR)
        return 0.5

    def ejecutar(self):
        # 1. GESTIÓN DE POSICIONES (Mantener igual)
        # ... (tu código de gestión actual)

        # 2. ESCÁNER AUTOMÁTICO REFINADO CON RVOL
        if len(self.posiciones) < 3:
            try:
                tickers = [t.ticker for t in client.list_tickers(market="stocks", limit=50)]
                muestra = random.sample(tickers, min(len(tickers), 20))
                
                for ticker in muestra:
                    if ticker in self.posiciones or ticker.endswith('W'): continue
                    
                    # Filtro de Volumen inusual ANTES de consultar el libro (ahorra API calls)
                    if not self.es_volumen_inusual(ticker): continue
                    
                    quote = client.get_last_quote(ticker)
                    heat = quote.bid_size / (quote.bid_size + quote.ask_size + 1e-9)
                    
                    if heat > 0.80 and 2.00 <= quote.bid_price <= 20.00 and not self.tiene_noticias_negativas(ticker):
                        atr = self.calcular_atr(ticker)
                        self.posiciones[ticker] = {
                            'entrada': quote.bid_price,
                            'sl': quote.bid_price - (atr * 1.5),
                            'max_price': quote.bid_price
                        }
                        bot.sendMessage(TELEGRAM_CHAT_ID, f"🔥 OPORTUNIDAD RVOL: {ticker}\nVolumen 3x superior a la media!")
                        break
            except Exception as e: print(f"Error escaneo: {e}")

if __name__ == "__main__":
    gestor = GestorFrancotirador()
    while True:
        gestor.ejecutar()
        time.sleep(20) # Aumentado ligeramente para respetar límites de Polygon
