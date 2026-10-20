# -*- coding: utf-8 -*-
"""
CONFIGURACION PARA PYTHONANYWHERE (recomendado - gratis y con almacenamiento PERSISTENTE)
-------------------------------------------------------------------------
1. Crea cuenta gratis en https://www.pythonanywhere.com
2. Ve a "Web" -> "Add a new web app" -> Manual configuration -> Python 3.10+
3. Sube los archivos de esta carpeta a: /home/TU_USUARIO/perlapos_web/
   (puedes usar la pestaña "Files" o consola: git clone / zip upload)
4. En la consola de PythonAnywhere ejecuta:
      cd /home/TU_USUARIO/perlapos_web
      pip install -r requirements.txt --user
5. Ve a la pestaña "Web" y edita el archivo WSGI (pincha en el link
   "/var/www/TU_USUARIO_pythonanywhere_com_wsgi.py"). Borra TODO su contenido
   y pega el codigo de abajo (ajusta TU_USUARIO).
6. En la misma pestaña Web, en "Code":
   - Source code:  /home/TU_USUARIO/perlapos_web
   - Working directory: /home/TU_USUARIO/perlapos_web
7. (Opcional) En "Virtualenv" deja vacio (usamos --user).
8. Click en el boton verde "Reload TU_USUARIO.pythonanywhere.com".
9. Abre https://TU_USUARIO.pythonanywhere.com  -> login admin / admin123

VARIABLES DE ENTORNO (pestana Web -> "Environment variables" o edita el wsgi):
   PERLA_MACHINE_ID = PERLAWEB   (fija el ID de maquina para la licencia)
"""

import sys, os

# ====== AJUSTA ESTA RUTA ======
project_home = "/home/TU_USUARIO/perlapos_web"
# ==============================

if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["PERLA_RESTAURANTES_DB"] = os.path.join(project_home, "data", "perla_restaurantes.db")
os.environ["PERLA_MACHINE_ID"] = "PERLAWEB"
os.environ["CLOUD"] = "1"

from app import app as application  # noqa: E402
