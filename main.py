if __name__ == "__main__":
    # Render asigna el puerto mediante una variable de entorno
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
  
