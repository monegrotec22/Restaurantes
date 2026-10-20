# -*- coding: utf-8 -*-
"""Punto de entrada WSGI para despliegue en la nube (Render, Railway, etc.).
Gunicorn lo usa asi:  gunicorn wsgi:app
"""
import os
# Asegura que la base de datos se guarde en la carpeta persistente data/
os.environ.setdefault("PERLA_RESTAURANTES_DB",
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "perla_restaurantes.db"))
from app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
