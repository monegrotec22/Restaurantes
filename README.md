# Perla Restaurantes POS — Versión Web (para hosting gratuito)

Esta es la versión **100% web** de Perla Restaurantes POS, lista para alojar en un servidor gratuito en la nube. Funciona en **cualquier dispositivo con navegador**: Windows, Mac, Linux, Android, iOS, ChromeOS, tablets… No necesita instalación.

> ⚠️ **Diferencia con la versión original:** la versión de escritorio corre en tu PC con Windows y se accede por la red local (WiFi). Esta versión corre en un servidor en internet y se accede desde cualquier lugar del mundo con la URL. La base de datos (ventas, clientes, inventario) vive en el servidor, no en tu PC.

---

## 🎯 Opción RECOMENDADA: PythonAnywhere (GRATIS + datos persistentes)

**¿Por qué esta?** Porque la base de datos SQLite se guarda en disco y **no se borra** al reiniciar. En otros hostings gratuitos (Render, Railway) el disco se borra en cada despliegue y pierdes los datos.

### Pasos (10 minutos):

1. **Crea cuenta gratis** en <https://www.pythonanywhere.com> (elige "Beginner" = gratis).
2. **Sube los archivos:**
   - Ve a la pestaña **Files** → crea carpeta `perlapos_web` → entra en ella.
   - Sube todos los archivos de este paquete (arrastra y suelta): `app.py`, `idiomas.py`, `licencia.py`, `wsgi.py`, `requirements.txt`, y las carpetas `templates/`, `static/`, `data/`.
   - *(Alternativa más rápida: en la pestaña **Consoles** abre un Bash y usa `git clone` si tienes el repo, o sube el ZIP y descomprime con `unzip`.)*
3. **Instala dependencias:** abre **Consoles → Bash** y ejecuta:
   ```bash
   cd perlapos_web
   pip install -r requirements.txt --user
   ```
4. **Crea la web app:** ve a **Web → Add a new web app**:
   - "Next" → **Manual configuration** → Python **3.10** (o superior) → Next.
5. **Configura el WSGI:** en la pestaña Web, bajo "Code", haz clic en el link del archivo
   `WSGI configuration file` (algo como `/var/www/tuusuario_pythonanywhere_com_wsgi.py`).
   Borra TODO su contenido y pega el texto del archivo **`pythonanywhere_wsgi.py`** de este paquete.
   **Importante:** cambia `TU_USUARIO` por tu nombre de usuario de PythonAnywhere (en la variable `project_home`).
6. **Verifica rutas:** en la misma pestaña Web → "Code":
   - Source code: `/home/TU_USUARIO/perlapos_web`
   - Working directory: `/home/TU_USUARIO/perlapos_web`
7. **Recarga:** clic en el botón verde **"Reload tuusuario.pythonanywhere.com"**.
8. **¡Listo!** Abre `https://TU_USUARIO.pythonanywhere.com` e inicia sesión:
   - Usuario: `admin` / Clave: `admin123`
   - (Cambia la clave en Configuración → Usuarios.)

### ⚠️ Limitación del plan gratis de PythonAnywhere
- Debes **recargar la app cada 3 meses** (te avisan por email; es un clic).
- 1 web app gratis, 512 MB de disco, tráfico limitado pero suficiente para un restaurante pequeño.

---

## Opción B: Render.com (gratis, pero los datos se borran al redeployar)

Ideal solo para **pruebas/demo**. Si lo usas en producción, contrata un disco persistente (~$1/mes) o usa PythonAnywhere.

1. Crea cuenta en <https://render.com> (gratis).
2. Sube este proyecto a GitHub (crea repo público o privado y sube los archivos).
3. En Render → **New → Web Service** → conecta tu repo de GitHub.
4. Configura:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn wsgi:app --workers 2 --threads 4 --bind 0.0.0.0:$PORT --timeout 120`
   - **Plan:** Free
   - **Environment Variables:** añade `CLOUD = 1` y `PERLA_MACHINE_ID = PERLAWEB`
5. Click **Create Web Service**. En ~2 minutos tendrás una URL tipo `https://perlarestaurantes.onrender.com`.
6. La primera carga puede tardar 30-50 segundos (el plan free se "duerme" tras inactividad).

> 📌 El archivo `render.yaml` incluido hace el despliegue automático (Blueprint).

---

## Opción C: Replit (la más fácil, sin GitHub)

1. Crea cuenta en <https://replit.com>.
2. **Create Repl** → tipo **Python** → sube los archivos de este paquete.
3. En la consola: `pip install -r requirements.txt`
4. Crea/edita `.replit` con:
   ```
   run = "gunicorn wsgi:app --bind 0.0.0.0:8080"
   ```
5. Click **Run**. Te da una URL pública.

---

## 🔑 Licencia en la nube (IMPORTANTE)

En la nube, la "dirección MAC" del servidor cambia en cada reinicio, lo que invalidaría una licencia ligada a un equipo. **Solución ya integrada:**

- Se fijó el ID de máquina a `PERLAWEB` mediante la variable de entorno `PERLA_MACHINE_ID`.
- **Activa una licencia permanente wildcard** (válida en cualquier equipo):
  1. Entra al sistema como `admin`.
  2. Menú lateral → **🎫 Generar licencia**.
  3. Duración: **Permanente** → marca **"Válida para cualquier equipo"** → Generar.
  4. Copia la clave. Ve a **🔑 Activar licencia** (en el login o dentro del sistema) y pégala.
- O usa el generador por consola: `python licencia.py "*" perm`

---

## 👤 Usuarios iniciales (cambia las claves)

| Usuario | Clave | Rol |
|---|---|---|
| `admin` | `admin123` | Acceso total |
| `mesero` | `mesero123` | Toma órdenes, mesas |
| `cajero` | `cajero123` | Cobra, caja, facturas |
| `cocina` | `cocina123` | Pantalla de cocina (KDS) |

---

## 💾 Respaldos

- **PythonAnywhere:** pestaña **Files** → carpeta `perlapos_web/data/` → descarga `perla_restaurantes.db` periódicamente.
- **Render (free):** los datos NO persisten; no lo uses sin disco de pago.
- Para restaurar: sube tu `perla_restaurantes.db` respaldado a la carpeta `data/` y recarga la app.

---

## 📁 Estructura del paquete

```
PerlaPOS_Web/
├── app.py                  # Núcleo del sistema (Flask, 62 rutas)
├── idiomas.py              # Español / English / Português / Français
├── licencia.py             # Motor de licencias (parcheado para nube)
├── wsgi.py                 # Punto de entrada para Gunicorn/Render
├── requirements.txt        # Dependencias
├── Procfile                # Comando de arranque (Render/Railway)
├── render.yaml             # Despliegue automático en Render
├── runtime.txt             # Versión de Python (Render)
├── pythonanywhere_wsgi.py  # Configuración WSGI para PythonAnywhere
├── templates/              # 18 páginas HTML (login, POS, cocina, caja...)
├── static/                 # CSS, JS, logo
└── data/                   # Base de datos SQLite (se crea al primer uso)
```

---

## 🆘 Si algo falla

1. **Error 500 al abrir:** en PythonAnywhere, pestaña Web → "Log files" → mira el error. Lo más común es que falte una dependencia (revisa el paso 3) o que la ruta `project_home` en el WSGI tenga tu usuario mal escrito.
2. **Pide licencia al entrar:** genera una clave permanente wildcard (sección "Licencia en la nube" arriba).
3. **No carga CSS/imágenes:** verifica que la carpeta `static/` se subió completa.
4. **"Not found" / 404:** la app no está corriendo; recarga el web service.

---

*Versión web adaptada de Perla Restaurantes POS v1.0.0 — funciona en cualquier sistema operativo.*
