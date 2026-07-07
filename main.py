    def escanear_tickers_activos_mercado(self):
        """
        CONECTOR DINÁMICO REFORZADO: Detecta si el plan de la API permite el escaneo masivo.
        """
        print("[API POLYGON] Escaneando el mercado en busca de acciones activas...")
        url = "https://api.polygon.io/v3/reference/tickers"
        
        params = {
            "market": "stocks",
            "type": "CS",
            "active": "true",
            "sort": "ticker",
            "order": "asc",
            "limit": 1000, 
            "apiKey": self.api_key
        }
        
        nuevos_tickers = []
        try:
            response = requests.get(url, params=params, timeout=12)
            if response.status_code == 200:
                datos = response.json()
                if "results" in datos:
                    nuevos_tickers = [item["ticker"] for item in datos["results"]]
                    print(f"[ESCÁNER] Se han detectado {len(nuevos_tickers)} acciones automáticamente.")
            elif response.status_code == 401:
                print("[ESCÁNER INFO] Tu API Key no tiene permisos para escaneo masivo V3. Usando Watchlist del JSON.")
            else:
                print(f"[ESCÁNER ERROR] Respuesta inesperada del servidor. Código: {response.status_code}")
        except Exception as e:
            print(f"[ESCÁNER EXCEPCIÓN] Error de conexión: {e}")
            
        if nuevos_tickers:
            lista_combinada = list(set(self.estado["watchlist_activa"] + nuevos_tickers))
            self.estado["watchlist_activa"] = lista_combinada
