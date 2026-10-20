# -*- coding: utf-8 -*-
import re
"""
PERLA RESTAURANTE POS 1.0 PRO
Arquitectura identica a Perla POS (Flask + SQLite + Jinja2), adaptada para restaurantes.
Modulo central: ORDENES DE SERVICIO (mesas, meseros, comandas, cocina/KDS, cobro).
"""
import os, sys, json, sqlite3, datetime, hashlib, secrets
from functools import wraps
from flask import (Flask, render_template, request, jsonify, session, redirect,
                   url_for, g, Response, send_file)
from werkzeug.security import generate_password_hash, check_password_hash

APP_NAME = "Perla Restaurantes"
APP_VERSION = "1.0.0"

# ============================================================
#  BASE DE DATOS PROPIA E INDEPENDIENTE (DESLIGADA DE PERLA POS)
#  Este POS de restaurantes NO comparte base de datos con Perla POS.
#  Orden de resolucion de la ruta:
#   1. Variable de entorno PERLA_RESTAURANTES_DB (ruta completa al .db)
#   2. Modo portable: si existe la carpeta "data" al lado del programa,
#      la base se guarda alli (instalacion autocontenida y respaldable).
#   3. Por defecto: carpeta propia %LOCALAPPDATA%\PerlaRestaurantes\data
# ============================================================
def _resolver_ruta_bd():
    env_db = os.environ.get("PERLA_RESTAURANTES_DB", "").strip()
    if env_db:
        ruta = os.path.abspath(env_db)
        return os.path.dirname(ruta), ruta
    if getattr(sys, "frozen", False):
        prog_dir = os.path.dirname(sys.executable)
    else:
        prog_dir = os.path.dirname(os.path.abspath(__file__))
    portable_data = os.path.join(prog_dir, "data")
    if os.path.isdir(portable_data):
        return portable_data, os.path.join(portable_data, "perla_restaurantes.db")
    if sys.platform.startswith("win"):
        base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "PerlaRestaurantes", "data")
    else:
        base = os.path.join(os.path.expanduser("~"), ".perla_restaurantes", "data")
    return base, os.path.join(base, "perla_restaurantes.db")

DATA_DIR, DB_PATH = _resolver_ruta_bd()
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "perla-restaurantes-" + hashlib.md5(DB_PATH.encode()).hexdigest()[:16]
app.config["JSON_AS_ASCII"] = False

# Soporte para ejecutable compilado con PyInstaller: plantillas y estaticos
# se extraen en sys._MEIPASS (carpeta temporal del onefile).
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    app.template_folder = os.path.join(BASE_DIR, "templates")
    app.static_folder = os.path.join(BASE_DIR, "static")

# Proveedor JSON que entiende sqlite3.Row (para |tojson en plantillas)
from flask.json.provider import DefaultJSONProvider
class RowJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, sqlite3.Row): return dict(o)
        if isinstance(o, (datetime.date, datetime.datetime)): return o.isoformat()
        try: return super(RowJSONProvider, RowJSONProvider).default(o)
        except Exception: return str(o)
app.json = RowJSONProvider(app)

# ============================================================
#  BASE DE DATOS
# ============================================================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None: db.close()

def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows

def qx(sql, args=()):
    db = get_db(); cur = db.execute(sql, args); db.commit(); lid = cur.lastrowid; cur.close(); return lid

def audit(accion, detalle=""):
    try:
        qx("INSERT INTO auditoria(usuario_id, accion, detalle, fecha) VALUES(?,?,?,?)",
           (session.get("user_id"), accion, detalle[:500], now()))
    except Exception: pass

def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def today(): return datetime.date.today().isoformat()

def money_fmt(v):
    v = float(v or 0)
    s = "{:,.2f}".format(v)
    return "RD$ " + s.replace(",", "~").replace(".", ",").replace("~", ".")

# ============================================================
#  ESQUEMA Y DATOS INICIALES
# ============================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS sistema_version (version TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS empresa (id INTEGER PRIMARY KEY, razon_social TEXT, nombre_comercial TEXT,
  rnc TEXT, direccion TEXT, provincia TEXT, telefono TEXT, email TEXT, moneda TEXT DEFAULT 'RD$',
  actividad TEXT, propina_sugerida REAL DEFAULT 10, itbis REAL DEFAULT 18, logo TEXT);
CREATE TABLE IF NOT EXISTS parametros (clave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, descripcion TEXT);
CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT,
  nombre_completo TEXT, rol_id INTEGER, pin TEXT, activo INTEGER DEFAULT 1, fecha_creacion TEXT);
CREATE TABLE IF NOT EXISTS usuario_permisos (usuario_id INTEGER, modulo TEXT, permiso TEXT);
CREATE TABLE IF NOT EXISTS areas_salon (id INTEGER PRIMARY KEY, nombre TEXT, activo INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS mesas (id INTEGER PRIMARY KEY, nombre TEXT, area_id INTEGER, capacidad INTEGER DEFAULT 4,
  estado TEXT DEFAULT 'LIBRE', orden_abierta_id INTEGER);
CREATE TABLE IF NOT EXISTS categorias_menu (id INTEGER PRIMARY KEY, nombre TEXT, color TEXT, orden INTEGER DEFAULT 0, activo INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS platos (id INTEGER PRIMARY KEY, codigo TEXT UNIQUE, nombre TEXT, categoria_id INTEGER,
  precio REAL, costo REAL, descripcion TEXT, disponible INTEGER DEFAULT 1, lleva_itbis INTEGER DEFAULT 1,
  tiempo_preparacion INTEGER DEFAULT 10, es_bebida INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS insumos (id INTEGER PRIMARY KEY, nombre TEXT, unidad TEXT, stock REAL DEFAULT 0,
  stock_minimo REAL DEFAULT 0, costo_unitario REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS receta_detalle (id INTEGER PRIMARY KEY, plato_id INTEGER, insumo_id INTEGER, cantidad REAL);
CREATE TABLE IF NOT EXISTS ia_conocimiento (id INTEGER PRIMARY KEY, palabras_clave TEXT, respuesta TEXT, hits INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ia_conversaciones (id INTEGER PRIMARY KEY, usuario_id INTEGER, modulo TEXT, pregunta TEXT, respuesta TEXT, fecha TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY, nombre TEXT, rnc_cedula TEXT, telefono TEXT,
  direccion TEXT, email TEXT, zona_delivery TEXT, notas TEXT);
CREATE TABLE IF NOT EXISTS proveedores (id INTEGER PRIMARY KEY, nombre TEXT, rnc TEXT, telefono TEXT,
  direccion TEXT, email TEXT, dias_credito INTEGER DEFAULT 0, limite_credito REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS ordenes (id INTEGER PRIMARY KEY, numero TEXT UNIQUE, mesa_id INTEGER, area_id INTEGER,
  usuario_id INTEGER, tipo TEXT DEFAULT 'COMEDOR', estado TEXT DEFAULT 'ABIERTA', personas INTEGER DEFAULT 1,
  cliente_id INTEGER, fecha_apertura TEXT, fecha_cierre TEXT, subtotal REAL DEFAULT 0, itbis REAL DEFAULT 0,
  propina REAL DEFAULT 0, total REAL DEFAULT 0, notas TEXT, venta_id INTEGER);
CREATE TABLE IF NOT EXISTS ordenes_detalle (id INTEGER PRIMARY KEY, orden_id INTEGER, plato_id INTEGER,
  nombre_plato TEXT, precio REAL, cantidad REAL DEFAULT 1, notas TEXT, estado TEXT DEFAULT 'PENDIENTE',
  enviado_cocina INTEGER DEFAULT 0, fecha_agregado TEXT);
CREATE TABLE IF NOT EXISTS cajas (id INTEGER PRIMARY KEY, nombre TEXT, activo INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS formas_pago (id INTEGER PRIMARY KEY, nombre TEXT, activo INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS sesiones_caja (id INTEGER PRIMARY KEY, caja_id INTEGER, usuario_id INTEGER,
  apertura TEXT, cierre TEXT, monto_inicial REAL DEFAULT 0, monto_cierre REAL DEFAULT 0, estado TEXT DEFAULT 'ABIERTA');
CREATE TABLE IF NOT EXISTS movimientos_caja (id INTEGER PRIMARY KEY, sesion_id INTEGER, fecha TEXT, tipo TEXT,
  concepto TEXT, monto REAL, forma_pago TEXT, referencia TEXT, usuario_id INTEGER);
CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY, numero_factura TEXT, orden_id INTEGER, cliente_id INTEGER,
  usuario_id INTEGER, fecha TEXT, subtotal REAL, itbis REAL, propina REAL, total REAL, estado TEXT DEFAULT 'EMITIDA',
  tipo_comprobante TEXT DEFAULT 'CONSUMIDOR FINAL', sesion_caja_id INTEGER);
CREATE TABLE IF NOT EXISTS ventas_detalle (id INTEGER PRIMARY KEY, venta_id INTEGER, plato_id INTEGER,
  nombre TEXT, precio REAL, cantidad REAL, itbis REAL);
CREATE TABLE IF NOT EXISTS venta_pagos (id INTEGER PRIMARY KEY, venta_id INTEGER, forma_pago TEXT, monto REAL, referencia TEXT);
CREATE TABLE IF NOT EXISTS compras (id INTEGER PRIMARY KEY, numero TEXT, proveedor_id INTEGER, fecha TEXT,
  subtotal REAL, itbis REAL, total REAL, estado TEXT DEFAULT 'RECIBIDA', usuario_id INTEGER);
CREATE TABLE IF NOT EXISTS compras_detalle (id INTEGER PRIMARY KEY, compra_id INTEGER, insumo_id INTEGER,
  nombre TEXT, cantidad REAL, costo REAL);
CREATE TABLE IF NOT EXISTS movimientos_inventario (id INTEGER PRIMARY KEY, fecha TEXT, insumo_id INTEGER,
  tipo TEXT, cantidad REAL, referencia TEXT, usuario_id INTEGER);
CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY, usuario_id INTEGER, accion TEXT, detalle TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS reservas (id INTEGER PRIMARY KEY, mesa_id INTEGER, cliente_nombre TEXT, telefono TEXT,
  fecha_reserva TEXT, hora TEXT, personas INTEGER, estado TEXT DEFAULT 'ACTIVA');
"""

SEED_SQL = [
    "INSERT OR IGNORE INTO sistema_version(version, fecha) VALUES('1.0.0', datetime('now'))",
    "INSERT OR IGNORE INTO empresa(id, razon_social, nombre_comercial, rnc, direccion, provincia, telefono, email, moneda, actividad, propina_sugerida, itbis) VALUES(1,'Mi Restaurante S.R.L.','Mi Restaurante','131234567','Calle Principal #123','Santo Domingo','809-555-1234','info@mirestaurante.com.do','RD$','Restaurante / Comida rápida',10,18)",
    "INSERT OR IGNORE INTO roles(id, nombre, descripcion) VALUES(1,'Administrador','Acceso total'),(2,'Mesero','Toma órdenes y atiende mesas'),(3,'Cajero','Cobra y gestiona caja'),(4,'Cocina','Recibe comandas y prepara')",
    "INSERT OR IGNORE INTO usuarios(id, username, password_hash, nombre_completo, rol_id, pin, fecha_creacion) VALUES(1,'admin',?,'Administrador',1,'0000',datetime('now'))",
    "INSERT OR IGNORE INTO usuarios(id, username, password_hash, nombre_completo, rol_id, pin, fecha_creacion) VALUES(2,'mesero',?,'Juan Pérez (Mesero)',2,'1234',datetime('now')),(3,'cajero',?,'Ana Ruiz (Cajero)',3,'5678',datetime('now')),(4,'cocina',?,'Chef Cocina',4,'9999',datetime('now'))",
    "INSERT OR IGNORE INTO areas_salon(id, nombre) VALUES(1,'Salón Principal'),(2,'Terraza'),(3,'Bar')",
    "INSERT OR IGNORE INTO categorias_menu(id, nombre, color, orden) VALUES(1,'Entradas','#f59e0b',1),(2,'Platos Fuertes','#3b82f6',2),(3,'Sopas','#06b6d4',3),(4,'Postres','#ec4899',4),(5,'Bebidas Frías','#10b981',5),(6,'Bebidas Calientes','#8b5cf6',6),(7,'Licores','#ef4444',7)",
    "INSERT OR IGNORE INTO cajas(id, nombre) VALUES(1,'Caja Principal')",
    "INSERT OR IGNORE INTO formas_pago(id, nombre) VALUES(1,'Efectivo'),(2,'Tarjeta'),(3,'Transferencia')",
]

SEED_PLATOS = [
    ("EN-001","Tostones con guacamole",1,150,60,"Tostones crujientes con guacamole fresco",1,1,8,0),
    ("EN-002","Croquetas de pollo (6)",1,180,70,"Croquetas caseras de pollo",1,1,10,0),
    ("EN-003","Ceviche de pescado",1,320,150,"Pescado fresco marinado en cítricos",1,1,12,0),
    ("PF-001","La Bandera Dominicana",2,350,160,"Arroz, habichuelas, carne guisada y ensalada",1,1,20,0),
    ("PF-002","Mofongo con churrasco",2,480,220,"Mofongo de plátano verde con churrasco",1,1,25,0),
    ("PF-003","Pescado con coco y arroz",2,420,190,"Filete de pescado en salsa de coco",1,1,22,0),
    ("PF-004","Pollo al horno con puré",2,310,140,"1/2 pollo al horno, puré y vegetales",1,1,18,0),
    ("PF-005","Hamburguesa clásica con papas",2,260,110,"Carne 180g, queso, papas fritas",1,1,12,0),
    ("SP-001","Sopa de mondongo",3,180,80,"Sopa tradicional dominicana",1,1,15,0),
    ("SP-002","Crema de auyama",3,140,55,"Crema suave con crutones",1,1,10,0),
    ("PO-001","Flan de coco",4,120,40,"Flan casero de coco",1,1,5,0),
    ("PO-002","Helado tres bolas",4,110,45,"Helado artesanal (vainilla, chocolate, fresa)",1,1,3,0),
    ("BF-001","Jugo natural (naranja/limón)",5,90,25,"Jugo fresco exprimido",1,0,2,1),
    ("BF-002","Refresco (lata)",5,60,20,"Coca-Cola, Sprite, etc.",1,0,1,1),
    ("BF-003","Agua mineral 500ml",5,50,15,"Agua sin gas",1,0,1,1),
    ("BC-001","Café americano",6,70,20,"Café negro grande",1,0,3,1),
    ("BC-002","Café con leche",6,90,30,"Cappuccino / latte",1,0,4,1),
    ("BC-003","Chocolate caliente",6,110,35,"Chocolate espumoso con canela",1,0,5,1),
    ("LI-001","Presidente (botella)",7,250,120,"Cerveza nacional 12oz",1,0,1,1),
    ("LI-002","Ron con refresco",7,180,70,"Ron nacional con mezcla",1,0,3,1),
    ("LI-003","Vino tinto (copa)",7,220,90,"Vino tinto reserva",1,0,2,1),
]

SEED_INSUMOS = [
    ("Arroz","lb",50,10,8), ("Habichuelas","lb",30,8,12), ("Carne de res","lb",25,5,180),
    ("Pollo","lb",30,5,75), ("Cerdo","lb",15,3,95), ("Pescado","lb",15,3,220),
    ("Plátano verde","unid",80,20,8), ("Yuca","lb",20,5,25), ("Papa","lb",25,5,20),
    ("Tomate","lb",20,5,30), ("Cebolla","lb",15,3,25), ("Ajo","lb",5,1,80),
    ("Aguacate","unid",30,8,25), ("Verduras","lb",20,5,35), ("Queso","lb",10,2,200),
    ("Huevos","unid",120,30,5), ("Harina","lb",15,3,30), ("Azúcar","lb",20,5,25),
    ("Sal","lb",10,2,8), ("Aceite","lt",8,2,180), ("Leche","lt",12,3,60),
    ("Café","lb",10,2,350), ("Cerveza","unid",120,24,60), ("Refresco","unid",100,24,25),
    ("Agua","unid",96,24,10), ("Ron","botella",12,3,400), ("Vino","botella",10,2,600),
]

def init_db():
    db = sqlite3.connect(DB_PATH); db.executescript(SCHEMA)
    pw = generate_password_hash("admin123")
    pw2 = generate_password_hash("mesero123"); pw3 = generate_password_hash("cajero123"); pw4 = generate_password_hash("cocina123")
    db.execute(SEED_SQL[3], (pw,)); db.execute(SEED_SQL[4], (pw2,pw3,pw4))
    for s in [SEED_SQL[0],SEED_SQL[1],SEED_SQL[2],SEED_SQL[5],SEED_SQL[6],SEED_SQL[7],SEED_SQL[8]]:
        db.execute(s)
    # Mesas: Salon 1-12, Terraza T1-T4, Bar B1-B4
    existing = db.execute("SELECT COUNT(*) FROM mesas").fetchone()[0]
    if existing == 0:
        for i in range(1,13): db.execute("INSERT INTO mesas(nombre, area_id, capacidad, estado) VALUES(?,?,4,'LIBRE')", (f"Mesa {i}",1))
        for i in range(1,5):  db.execute("INSERT INTO mesas(nombre, area_id, capacidad, estado) VALUES(?,?,6,'LIBRE')", (f"Terraza {i}",2))
        for i in range(1,5):  db.execute("INSERT INTO mesas(nombre, area_id, capacidad, estado) VALUES(?,?,2,'LIBRE')", (f"Bar {i}",3))
    # Platos
    existing = db.execute("SELECT COUNT(*) FROM platos").fetchone()[0]
    if existing == 0:
        for p in SEED_PLATOS:
            db.execute("INSERT INTO platos(codigo,nombre,categoria_id,precio,costo,descripcion,disponible,lleva_itbis,tiempo_preparacion,es_bebida) VALUES(?,?,?,?,?,?,?,?,?,?)", p)
    # Insumos
    existing = db.execute("SELECT COUNT(*) FROM insumos").fetchone()[0]
    if existing == 0:
        for i in SEED_INSUMOS:
            db.execute("INSERT INTO insumos(nombre,unidad,stock,stock_minimo,costo_unitario) VALUES(?,?,?,?,?)", i)
            recetas = {
                "La Bandera Dominicana": [("Arroz",0.25),("Habichuelas",0.15),("Carne de res",0.25),("Aceite",0.02),("Verduras",0.1)],
                "Mofongo con churrasco": [("Plátano verde",2),("Carne de res",0.2),("Aceite",0.03),("Ajo",0.005)],
                "Pescado con coco y arroz": [("Pescado",0.35),("Arroz",0.2),("Leche",0.1),("Aceite",0.02)],
                "Pollo al horno con puré": [("Pollo",0.3),("Papa",0.2),("Aceite",0.02)],
                "Tostones con guacamole": [("Plátano verde",2),("Aguacate",0.5),("Tomate",0.1),("Aceite",0.05)],
                "Croquetas de pollo (6)": [("Pollo",0.2),("Harina",0.05),("Huevos",1),("Aceite",0.03)],
                "Ceviche de pescado": [("Pescado",0.3),("Tomate",0.1),("Cebolla",0.05)],
                "Sopa de mondongo": [("Carne de res",0.2),("Verduras",0.1),("Ajo",0.005)],
                "Hamburguesa clásica con papas": [("Carne de res",0.2),("Papa",0.2),("Queso",0.05),("Huevos",1)],
                "Crema de auyama": [("Verduras",0.2),("Leche",0.1)],
                "Flan de coco": [("Leche",0.2),("Huevos",2),("Azúcar",0.05)],
                "Helado tres bolas": [("Leche",0.15),("Azúcar",0.03)],
                "Jugo natural (naranja/limón)": [("Azúcar",0.02),("Agua",0.2)],
                "Refresco (lata)": [("Refresco",1)],
                "Agua mineral 500ml": [("Agua",1)],
                "Café americano": [("Café",0.02),("Azúcar",0.01),("Agua",0.2)],
                "Café con leche": [("Café",0.02),("Leche",0.15),("Azúcar",0.01)],
                "Chocolate caliente": [("Leche",0.2),("Azúcar",0.03)],
                "Presidente (botella)": [("Cerveza",1)],
                "Ron con refresco": [("Ron",0.1),("Refresco",1)],
                "Vino tinto (copa)": [("Vino",0.125)],
            }
            for pname, ings in recetas.items():
                pid = db.execute("SELECT id FROM platos WHERE nombre=?", (pname,)).fetchone()
                if not pid: continue
                for iname, cant in ings:
                    iid = db.execute("SELECT id FROM insumos WHERE nombre=?", (iname,)).fetchone()
                    if iid: db.execute("INSERT INTO receta_detalle(plato_id,insumo_id,cantidad) VALUES(?,?,?)", (pid[0], iid[0], cant))
            # Conocimiento inicial de Perla Intelligence AI (soporte del POS)
            if db.execute("SELECT COUNT(*) FROM ia_conocimiento").fetchone()[0] == 0:
                conocimiento = [
                    ("hola buenas ayuda que puedes opciones saludos", "¡Hola! Soy Perla Intelligence AI 🤖, asistente oficial de Perla Tech. Te ayudo con: abrir caja, tomar órdenes, cobrar y facturar, inventario y compras, reportes, usuarios, menú y recetas, cocina/KDS, configuración e impresión. ¿Qué necesitas?"),
                    ("caja abrir apertura fondo arqueo cierre", "Para abrir caja ve a 💰 Caja y Bancos → 🔓 Abrir caja. Indica la caja y el fondo inicial. Sin caja abierta no podrás cobrar. Al finalizar usa Cerrar / arqueo."),
                    ("cobrar facturar venta pagar pos cobro factura", "Ve a 💳 POS / Cobrar: agrega platos al carrito, elige forma de pago y monto recibido, pulsa Cobrar / Facturar. Se genera la factura imprimible (con logo y RNC) y se descuenta inventario automáticamente."),
                    ("orden mesa comanda servicio pedido atender reservar reserva", "En 🧾 Órdenes de Servicio toca una mesa libre, abre la orden, agrega platos con notas y pulsa Enviar a cocina. La comanda llega al KDS con tiempo estimado e ingredientes. También puedes reservar mesas."),
                    ("inventario stock insumo comprar faltante agotar agotado bajo reponer compra", "__STOCK__"),
                    ("reporte ventas estadistica csv exportar grafico", "En 📊 Reportes elige el tipo (ventas, platos, meseros, mesas, caja), el período y pulsa Exportar CSV para descargar los datos."),
                    ("usuario contraseña clave acceso login ingresar admin mesero cajero cocina", "Usuarios iniciales: admin/admin123, mesero/mesero123, cajero/cajero123, cocina/cocina123. Cambia las contraseñas en 👤 Usuarios por seguridad."),
                    ("menu plato receta ingrediente carta bebida categoria", "En 🍽️ Menú crea platos y categorías. Usa el botón 📋 de cada plato para definir su receta (ingredientes que consume): la IA la usa para descontar inventario y sugerir compras."),
                    ("cocina kds tiempo preparar listo servido comanda pantalla", "En 👨‍🍳 Cocina / KDS las comandas llegan en 3 columnas (Pendiente, Preparando, Listo) con temporizador, tiempo estimado e ingredientes. Toca un ticket para cambiar su estado."),
                    ("cliente delivery domicilio envio rnc facturacion", "En 👥 Clientes registra clientes para delivery y facturación con RNC. Al cobrar en el POS selecciona el cliente y aparecerá en la factura."),
                    ("configuracion logo itbis impuesto rnc empresa mesa area propina", "En ⚙️ Configuración edita los datos de la empresa (RNC, dirección, teléfono), ITBIS, propina sugerida, áreas y mesas, y sube el logo comercial que aparece solo en las facturas."),
                    ("imprimir factura ticket impresora pdf imprimir 80mm", "Tras cobrar pulsa 🖨 Imprimir factura: abre un ticket formato 80mm con logo, RNC, ítems, ITBIS, propina, totales, pagos y cambio, listo para impresora térmica o guardar como PDF."),
                    ("cerrar salir apagar detener cerrar pos segundo plano consola", "Usa ✖ Cerrar POS (arriba a la derecha) para detener el servidor en segundo plano. En el .exe compilado la consola está oculta."),
                    ("compra proveedor abastecer pedido insumo entrada", "En 🛒 Compras registra compras a proveedores: los insumos se suman automáticamente al inventario. La IA te sugiere cuánto comprar según el menú y ventas."),
                    ("perla tech empresa quien eres que eres inteligencia artificial", "Soy Perla Intelligence AI, la inteligencia artificial personalizada de Perla Tech para este POS. Aprendo de cada pregunta que me haces y solo hablo sobre este sistema de punto de venta."),
                ]
                for kw, resp in conocimiento:
                    db.execute("INSERT INTO ia_conocimiento(palabras_clave, respuesta) VALUES(?,?)", (kw, resp))
    db.commit(); db.close()

with app.app_context():
    if not os.path.exists(DB_PATH):
        init_db()
    else:
        # asegurar tablas nuevas + migracion de columna logo
        try:
            db = sqlite3.connect(DB_PATH); db.executescript(SCHEMA)
            try: db.execute("ALTER TABLE empresa ADD COLUMN logo TEXT")
            except Exception: pass
            db.commit(); db.close()
        except Exception: pass

# Ruta del logo comercial del restaurante (solo para facturas).
# Si no se ha subido uno, se usa el logo del sistema por defecto.
LOGO_COMERCIAL_PATH = os.path.join(DATA_DIR, "empresa_logo.png")

# ============================================================
#  AUTENTICACION Y PERMISOS
# ============================================================
def login_required(f):
    @wraps(f)
    def wrap(*a, **k):
        if not session.get("user_id"): return redirect(url_for("login"))
        return f(*a, **k)
    return wrap

def current_user():
    uid = session.get("user_id")
    if not uid: return None
    return q("SELECT u.*, r.nombre as rol FROM usuarios u LEFT JOIN roles r ON r.id=u.rol_id WHERE u.id=?", (uid,), one=True)

@app.context_processor
def inject_globals():
    u = current_user()
    emp = q("SELECT * FROM empresa WHERE id=1", one=True)
    return dict(current=u, empresa=emp, app_name=APP_NAME, app_version=APP_VERSION,
                money=money_fmt, can=(lambda m: True))  # permisos abiertos en esta edicion

@app.template_filter("money")
def money_filter(v): return money_fmt(v)

# ============================================================
#  AUTENTICACION
# ============================================================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM usuarios WHERE username=? AND activo=1", (request.form.get("username"),), one=True)
        if u and check_password_hash(u["password_hash"], request.form.get("password","")):
            session.clear()
            session["user_id"] = u["id"]; session["username"] = u["username"]
            audit("LOGIN", f"Usuario {u['username']}")
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Usuario o contraseña incorrectos.")
    if session.get("user_id"): return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    audit("LOGOUT", session.get("username",""))
    session.clear()
    return redirect(url_for("login"))

# ============================================================
#  DASHBOARD
# ============================================================
@app.route("/")
@login_required
def dashboard():
    hoy = today()
    ventas_hoy = q("SELECT COALESCE(SUM(total),0) t, COUNT(*) c FROM ventas WHERE fecha >= ?", (hoy,), one=True)
    ordenes_abiertas = q("SELECT COUNT(*) c FROM ordenes WHERE estado='ABIERTA' OR estado='EN_COCINA' OR estado='SERVIDA'", one=True)["c"]
    mesas_ocupadas = q("SELECT COUNT(*) c FROM mesas WHERE estado='OCUPADA'", one=True)["c"]
    mesas_libres = q("SELECT COUNT(*) c FROM mesas WHERE estado='LIBRE'", one=True)["c"]
    # ventas ultimos 7 dias
    dias = []
    for i in range(6,-1,-1):
        d = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        tot = q("SELECT COALESCE(SUM(total),0) t FROM ventas WHERE fecha >= ? AND fecha < ?",
                (d, (datetime.date.today() - datetime.timedelta(days=i-1)).isoformat()), one=True)["t"]
        dias.append({"fecha": d[5:], "total": tot})
    top_platos = q("""SELECT vd.nombre, SUM(vd.cantidad) c, SUM(vd.cantidad*vd.precio) t
        FROM ventas_detalle vd JOIN ventas v ON v.id=vd.venta_id WHERE v.fecha >= ?
        GROUP BY vd.nombre ORDER BY c DESC LIMIT 6""", (hoy,))
    ordenes_recientes = q("""SELECT o.*, m.nombre mesa, u.nombre_completo mesero FROM ordenes o
        LEFT JOIN mesas m ON m.id=o.mesa_id LEFT JOIN usuarios u ON u.id=o.usuario_id
        ORDER BY o.id DESC LIMIT 8""")
    caja_abierta = q("SELECT * FROM sesiones_caja WHERE estado='ABIERTA' ORDER BY id DESC LIMIT 1", one=True)
    return render_template("dashboard.html", ventas_hoy=ventas_hoy, ordenes_abiertas=ordenes_abiertas,
        mesas_ocupadas=mesas_ocupadas, mesas_libres=mesas_libres, dias=dias, top_platos=top_platos,
        ordenes_recientes=ordenes_recientes, caja_abierta=caja_abierta)

# ============================================================
#  MODULO: ORDENES DE SERVICIO  (el modulo central del restaurante)
# ============================================================
@app.route("/ordenes")
@login_required
def ordenes():
    areas = q("SELECT * FROM areas_salon WHERE activo=1")
    mesas = q("""SELECT m.*, a.nombre area, o.total cuenta_acumulada, o.id orden_id,
        (SELECT nombre_completo FROM usuarios WHERE id=o.usuario_id) mesero,
        o.fecha_apertura, o.personas
        FROM mesas m LEFT JOIN areas_salon a ON a.id=m.area_id
        LEFT JOIN ordenes o ON o.id=m.orden_abierta_id AND o.estado IN ('ABIERTA','EN_COCINA','SERVIDA')
        ORDER BY a.id, m.id""")
    meseros = q("SELECT id, nombre_completo FROM usuarios WHERE rol_id IN (1,2) AND activo=1")
    categorias = q("SELECT * FROM categorias_menu WHERE activo=1 ORDER BY orden")
    platos = q("SELECT p.*, c.nombre categoria FROM platos p LEFT JOIN categorias_menu c ON c.id=p.categoria_id WHERE p.disponible=1 ORDER BY c.orden, p.nombre")
    ordenes_abiertas = q("""SELECT o.*, m.nombre mesa, u.nombre_completo mesero,
        (SELECT COUNT(*) FROM ordenes_detalle od WHERE od.orden_id=o.id) items
        FROM ordenes o LEFT JOIN mesas m ON m.id=o.mesa_id LEFT JOIN usuarios u ON u.id=o.usuario_id
        WHERE o.estado IN ('ABIERTA','EN_COCINA','SERVIDA') ORDER BY o.id DESC""")
    clientes = q("SELECT id, nombre, telefono FROM clientes ORDER BY nombre")
    return render_template("ordenes.html", areas=areas, mesas=mesas, meseros=meseros,
        categorias=categorias, platos=platos, ordenes_abiertas=ordenes_abiertas, clientes=clientes)

@app.route("/cocina")
@login_required
def cocina():
    items = q("""SELECT od.*, o.numero orden_numero, m.nombre mesa, o.tipo, p.es_bebida
        FROM ordenes_detalle od JOIN ordenes o ON o.id=od.orden_id
        LEFT JOIN mesas m ON m.id=o.mesa_id LEFT JOIN platos p ON p.id=od.plato_id
        WHERE od.estado IN ('PENDIENTE','PREPARANDO') AND o.estado IN ('ABIERTA','EN_COCINA','SERVIDA')
        ORDER BY od.fecha_agregado""")
    return render_template("cocina.html", items=items)

def recalcular_orden(oid):
    det = q("SELECT SUM(precio*cantidad) s FROM ordenes_detalle WHERE orden_id=?", (oid,), one=True)
    subtotal = float(det["s"] or 0)
    emp = q("SELECT itbis FROM empresa WHERE id=1", one=True)
    itbis_pct = float(emp["itbis"] or 18)/100
    # ITBIS solo en items que lo llevan ( simplificado: sobre subtotal de platos con lleva_itbis )
    itbis = q("""SELECT COALESCE(SUM(od.precio*od.cantidad*?),0) s FROM ordenes_detalle od
        JOIN platos p ON p.id=od.plato_id WHERE od.orden_id=? AND p.lleva_itbis=1""", (itbis_pct, oid), one=True)["s"]
    o = q("SELECT propina FROM ordenes WHERE id=?", (oid,), one=True)
    propina = float(o["propina"] or 0)
    total = subtotal + itbis + propina
    qx("UPDATE ordenes SET subtotal=?, itbis=?, total=? WHERE id=?", (subtotal, itbis, total, oid))
    return subtotal, itbis, propina, total

@app.route("/api/orden", methods=["POST"])
@login_required
def api_orden_crear():
    d = request.get_json(force=True)
    mesa_id = d.get("mesa_id"); tipo = d.get("tipo","COMEDOR")
    if mesa_id:
        mesa = q("SELECT * FROM mesas WHERE id=?", (mesa_id,), one=True)
        if not mesa: return jsonify(success=False, error="Mesa no existe")
        if mesa["estado"] == "OCUPADA": return jsonify(success=False, error="Mesa ya está ocupada")
    numero = "ORD-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + str(secrets.randbelow(90)+10)
    oid = qx("""INSERT INTO ordenes(numero, mesa_id, area_id, usuario_id, tipo, estado, personas,
        cliente_id, fecha_apertura, notas) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (numero, mesa_id, d.get("area_id"), session["user_id"], tipo, "ABIERTA",
         d.get("personas",1), d.get("cliente_id"), now(), d.get("notas","")))
    if mesa_id:
        qx("UPDATE mesas SET estado='OCUPADA', orden_abierta_id=? WHERE id=?", (oid, mesa_id))
    audit("ORDEN_ABRIR", f"{numero} mesa={mesa_id} tipo={tipo}")
    return jsonify(success=True, orden_id=oid, numero=numero)

@app.route("/api/orden/<int:oid>")
@login_required
def api_orden_detalle(oid):
    o = q("""SELECT o.*, m.nombre mesa, u.nombre_completo mesero, c.nombre cliente
        FROM ordenes o LEFT JOIN mesas m ON m.id=o.mesa_id
        LEFT JOIN usuarios u ON u.id=o.usuario_id LEFT JOIN clientes c ON c.id=o.cliente_id
        WHERE o.id=?""", (oid,), one=True)
    if not o: return jsonify(success=False, error="Orden no encontrada")
    items = q("SELECT * FROM ordenes_detalle WHERE orden_id=? ORDER BY id", (oid,))
    items_rich = []
    tiempo_estimado = 0
    for it in items:
        di = dict(it)
        plato = q("SELECT tiempo_preparacion FROM platos WHERE id=?", (it["plato_id"],), one=True)
        if plato: tiempo_estimado = max(tiempo_estimado, int(plato["tiempo_preparacion"] or 10))
        ing = q("""SELECT DISTINCT i.nombre, i.unidad, r.cantidad FROM receta_detalle r JOIN insumos i ON i.id=r.insumo_id
                   WHERE r.plato_id=? ORDER BY i.nombre""", (it["plato_id"],))
        di["ingredientes"] = [f"{x['nombre']} ({x['cantidad']} {x['unidad']})" for x in ing]
        di["tiempo_preparacion"] = int((plato["tiempo_preparacion"] or 10)) if plato else 10
        items_rich.append(di)
    subtotal, itbis, propina, total = recalcular_orden(oid)
    return jsonify(success=True, orden=dict(o), items=items_rich,
                   totales=dict(subtotal=subtotal, itbis=itbis, propina=propina, total=total),
                   tiempo_estimado=tiempo_estimado)

@app.route("/api/orden/<int:oid>/item", methods=["POST"])
@login_required
def api_orden_item(oid):
    d = request.get_json(force=True)
    plato = q("SELECT * FROM platos WHERE id=? AND disponible=1", (d.get("plato_id"),), one=True)
    if not plato: return jsonify(success=False, error="Plato no disponible")
    qx("""INSERT INTO ordenes_detalle(orden_id, plato_id, nombre_plato, precio, cantidad, notas, estado, fecha_agregado)
        VALUES(?,?,?,?,?,?, 'PENDIENTE', ?)""",
        (oid, plato["id"], plato["nombre"], plato["precio"], d.get("cantidad",1), d.get("notas",""), now()))
    recalcular_orden(oid)
    audit("ORDEN_ITEM", f"orden {oid}: +{plato['nombre']}")
    return jsonify(success=True)

@app.route("/api/orden/item/<int:item_id>", methods=["PUT","DELETE"])
@login_required
def api_orden_item_edit(item_id):
    it = q("SELECT * FROM ordenes_detalle WHERE id=?", (item_id,), one=True)
    if not it: return jsonify(success=False, error="Item no existe")
    if request.method == "DELETE":
        qx("DELETE FROM ordenes_detalle WHERE id=?", (item_id,))
    else:
        d = request.get_json(force=True)
        qx("UPDATE ordenes_detalle SET cantidad=?, notas=? WHERE id=?",
           (d.get("cantidad", it["cantidad"]), d.get("notas", it["notas"] or ""), item_id))
    recalcular_orden(it["orden_id"])
    return jsonify(success=True)

@app.route("/api/orden/<int:oid>/enviar-cocina", methods=["POST"])
@login_required
def api_orden_enviar_cocina(oid):
    qx("UPDATE ordenes_detalle SET enviado_cocina=1, estado='PREPARANDO' WHERE orden_id=? AND estado='PENDIENTE'", (oid,))
    qx("UPDATE ordenes SET estado='EN_COCINA' WHERE id=? AND estado='ABIERTA'", (oid,))
    audit("COMANDA_ENVIAR", f"orden {oid}")
    return jsonify(success=True)

@app.route("/api/orden/item/<int:item_id>/estado", methods=["POST"])
@login_required
def api_item_estado(item_id):
    d = request.get_json(force=True)
    estado = d.get("estado")
    if estado not in ("PENDIENTE","PREPARANDO","LISTO","SERVIDO"):
        return jsonify(success=False, error="Estado inválido")
    qx("UPDATE ordenes_detalle SET estado=? WHERE id=?", (estado, item_id))
    # si todos los items servidos -> orden SERVIDA
    it = q("SELECT orden_id FROM ordenes_detalle WHERE id=?", (item_id,), one=True)
    pend = q("SELECT COUNT(*) c FROM ordenes_detalle WHERE orden_id=? AND estado!='SERVIDO'", (it["orden_id"],), one=True)["c"]
    if pend == 0:
        qx("UPDATE ordenes SET estado='SERVIDA' WHERE id=? AND estado!='CERRADA'", (it["orden_id"],))
    return jsonify(success=True)

@app.route("/api/orden/<int:oid>/propina", methods=["POST"])
@login_required
def api_orden_propina(oid):
    d = request.get_json(force=True)
    qx("UPDATE ordenes SET propina=? WHERE id=?", (float(d.get("propina",0)), oid))
    recalcular_orden(oid)
    return jsonify(success=True)

@app.route("/api/orden/<int:oid>/anular", methods=["POST"])
@login_required
def api_orden_anular(oid):
    o = q("SELECT * FROM ordenes WHERE id=?", (oid,), one=True)
    qx("UPDATE ordenes SET estado='ANULADA' WHERE id=?", (oid,))
    if o and o["mesa_id"]:
        qx("UPDATE mesas SET estado='LIBRE', orden_abierta_id=NULL WHERE id=?", (o["mesa_id"],))
    audit("ORDEN_ANULAR", f"orden {oid}")
    return jsonify(success=True)

@app.route("/api/mesa/<int:mid>/estado", methods=["POST"])
@login_required
def api_mesa_estado(mid):
    d = request.get_json(force=True)
    estado = d.get("estado")
    if estado not in ("LIBRE","OCUPADA","RESERVADA","SUCIA"):
        return jsonify(success=False, error="Estado inválido")
    qx("UPDATE mesas SET estado=? WHERE id=?", (estado, mid))
    if estado == "LIBRE":
        qx("UPDATE mesas SET orden_abierta_id=NULL WHERE id=?", (mid,))
    return jsonify(success=True)

@app.route("/api/reserva", methods=["POST","DELETE"])
@login_required
def api_reserva():
    if request.method == "DELETE":
        d = request.get_json(force=True)
        qx("DELETE FROM reservas WHERE id=?", (d.get("id"),))
        return jsonify(success=True)
    d = request.get_json(force=True)
    rid = qx("INSERT INTO reservas(mesa_id, cliente_nombre, telefono, fecha_reserva, hora, personas) VALUES(?,?,?,?,?,?)",
             (d.get("mesa_id"), d.get("cliente_nombre"), d.get("telefono"), d.get("fecha_reserva"), d.get("hora"), d.get("personas",2)))
    if d.get("mesa_id"):
        qx("UPDATE mesas SET estado='RESERVADA' WHERE id=?", (d.get("mesa_id"),))
    return jsonify(success=True, id=rid)

# ============================================================
#  POS / COBRO
# ============================================================
@app.route("/pos")
@login_required
def pos():
    orden_id = request.args.get("orden_id", type=int)
    categorias = q("SELECT * FROM categorias_menu WHERE activo=1 ORDER BY orden")
    platos = q("SELECT p.*, c.nombre categoria FROM platos p LEFT JOIN categorias_menu c ON c.id=p.categoria_id WHERE p.disponible=1 ORDER BY c.orden, p.nombre")
    formas = q("SELECT * FROM formas_pago WHERE activo=1")
    clientes = q("SELECT id, nombre, rnc_cedula FROM clientes ORDER BY nombre")
    caja_abierta = q("SELECT * FROM sesiones_caja WHERE estado='ABIERTA' ORDER BY id DESC LIMIT 1", one=True)
    ordenes_abiertas = q("""SELECT o.*, m.nombre mesa FROM ordenes o LEFT JOIN mesas m ON m.id=o.mesa_id
        WHERE o.estado IN ('ABIERTA','EN_COCINA','SERVIDA') ORDER BY o.id DESC""")
    orden = None
    if orden_id:
        o = q("SELECT * FROM ordenes WHERE id=?", (orden_id,), one=True)
        if o and o["estado"] != "CERRADA":
            items = q("SELECT * FROM ordenes_detalle WHERE orden_id=? ORDER BY id", (orden_id,))
            orden = dict(o); orden["items"] = [dict(i) for i in items]
    return render_template("pos.html", categorias=categorias, platos=platos, formas=formas,
        clientes=clientes, caja_abierta=caja_abierta, orden=orden, ordenes_abiertas=ordenes_abiertas)

@app.route("/api/venta", methods=["POST"])
@login_required
def api_venta():
    d = request.get_json(force=True)
    items = d.get("items", [])
    if not items: return jsonify(success=False, error="No hay items en la cuenta")
    orden_id = d.get("orden_id")
    emp = q("SELECT * FROM empresa WHERE id=1", one=True)
    numero = "F-" + datetime.datetime.now().strftime("%Y%m%d-") + str(q("SELECT COALESCE(MAX(id),0)+1 n FROM ventas", one=True)["n"])
    subtotal = sum(float(i["precio"])*float(i["cantidad"]) for i in items)
    itbis = sum(float(i["precio"])*float(i["cantidad"])*(float(emp["itbis"])/100) for i in items if i.get("lleva_itbis",1))
    propina = float(d.get("propina",0))
    total = subtotal + itbis + propina
    sesion = q("SELECT id FROM sesiones_caja WHERE estado='ABIERTA' ORDER BY id DESC LIMIT 1", one=True)
    vid = qx("""INSERT INTO ventas(numero_factura, orden_id, cliente_id, usuario_id, fecha, subtotal, itbis, propina, total, tipo_comprobante, sesion_caja_id)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (numero, orden_id, d.get("cliente_id"), session["user_id"], now(), subtotal, itbis, propina, total,
         d.get("tipo_comprobante","CONSUMIDOR FINAL"), sesion["id"] if sesion else None))
    for i in items:
        qx("INSERT INTO ventas_detalle(venta_id, plato_id, nombre, precio, cantidad, itbis) VALUES(?,?,?,?,?,?)",
           (vid, i.get("plato_id"), i["nombre"], i["precio"], i["cantidad"], float(i["precio"])*float(i["cantidad"])*(float(emp["itbis"])/100)))
    for p in d.get("pagos", []):
        qx("INSERT INTO venta_pagos(venta_id, forma_pago, monto, referencia) VALUES(?,?,?,?)",
           (vid, p.get("forma_pago","Efectivo"), p.get("monto",0), p.get("referencia","")))
        if sesion:
            qx("INSERT INTO movimientos_caja(sesion_id, fecha, tipo, concepto, monto, forma_pago, referencia, usuario_id) VALUES(?,?, 'INGRESO', ?, ?, ?, ?, ?)",
               (sesion["id"], now(), f"Venta {numero} - {p.get('forma_pago')}", p.get("monto",0), p.get("forma_pago"), numero, session["user_id"]))
    # cerrar orden y liberar mesa
    if orden_id:
        qx("UPDATE ordenes SET estado='CERRADA', fecha_cierre=?, venta_id=?, subtotal=?, itbis=?, propina=?, total=? WHERE id=?",
           (now(), vid, subtotal, itbis, propina, total, orden_id))
        o = q("SELECT mesa_id FROM ordenes WHERE id=?", (orden_id,), one=True)
        if o and o["mesa_id"]:
            # dejar mesa SUCIA para limpieza, o LIBRE segun parametro
            qx("UPDATE mesas SET estado='SUCIA', orden_abierta_id=NULL WHERE id=?", (o["mesa_id"],))
    faltantes = descontar_inventario_y_faltantes(items)
    audit("VENTA_COBRAR", f"{numero} total={total:.2f} faltantes={len(faltantes)}")
    return jsonify(success=True, venta_id=vid, numero=numero, total=total, faltantes=faltantes)

# ============================================================
#  FACTURA IMPRIMIBLE (ticket 80mm con logo y datos del restaurante)
# ============================================================
@app.route("/factura/<int:venta_id>/imprimir")
@login_required
def factura_imprimir(venta_id):
    v = q("""SELECT v.*, c.nombre cliente, c.rnc_cedula FROM ventas v
        LEFT JOIN clientes c ON c.id=v.cliente_id WHERE v.id=?""", (venta_id,), one=True)
    if not v: return "Factura no encontrada", 404
    items = q("SELECT * FROM ventas_detalle WHERE venta_id=? ORDER BY id", (venta_id,))
    pagos = q("SELECT * FROM venta_pagos WHERE venta_id=?", (venta_id,))
    emp = q("SELECT * FROM empresa WHERE id=1", one=True)
    total_pagos = sum(float(p["monto"] or 0) for p in pagos)
    recibido = total_pagos if total_pagos > 0 else float(v["total"])
    cambio = max(0, recibido - float(v["total"]))
    return render_template("factura.html", v=v, items=items, pagos=pagos, emp=emp,
                           recibido=recibido, cambio=cambio)

# ============================================================
#  CERRAR POS (para el ejecutable sin consola, en segundo plano)
# ============================================================
@app.route("/api/salir")
@login_required
def salir():
    audit("SALIR", "Cierre de la aplicacion")
    if getattr(sys, "frozen", False):
        from threading import Timer
        Timer(0.5, lambda: os._exit(0)).start()
        return jsonify(success=True, mensaje="POS cerrado")
    return jsonify(success=False, error="Modo desarrollo: detenga el servidor con Ctrl+C en la consola.")

# ============================================================
#  MENU (platos y categorias)
# ============================================================
@app.route("/menu")
@login_required
def menu():
    categorias = q("SELECT * FROM categorias_menu ORDER BY orden")
    platos = q("""SELECT p.*, c.nombre categoria FROM platos p LEFT JOIN categorias_menu c ON c.id=p.categoria_id
        ORDER BY c.orden, p.nombre""")
    insumos_menu = q("SELECT id, nombre, unidad FROM insumos ORDER BY nombre")
    return render_template("menu.html", categorias=categorias, platos=platos, insumos=insumos_menu)

@app.route("/api/plato", methods=["POST"])
@login_required
def api_plato():
    d = request.get_json(force=True)
    qx("""INSERT INTO platos(codigo, nombre, categoria_id, precio, costo, descripcion, disponible, lleva_itbis, tiempo_preparacion, es_bebida)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (d.get("codigo"), d.get("nombre"), d.get("categoria_id"), d.get("precio",0), d.get("costo",0),
         d.get("descripcion",""), 1 if d.get("disponible",1) else 0, 1 if d.get("lleva_itbis",1) else 0,
         d.get("tiempo_preparacion",10), 1 if d.get("es_bebida",0) else 0))
    return jsonify(success=True)

@app.route("/api/plato/<int:pid>", methods=["PUT","DELETE"])
@login_required
def api_plato_edit(pid):
    if request.method == "DELETE":
        qx("DELETE FROM platos WHERE id=?", (pid,)); return jsonify(success=True)
    d = request.get_json(force=True)
    qx("""UPDATE platos SET codigo=?, nombre=?, categoria_id=?, precio=?, costo=?, descripcion=?,
        disponible=?, lleva_itbis=?, tiempo_preparacion=?, es_bebida=? WHERE id=?""",
        (d.get("codigo"), d.get("nombre"), d.get("categoria_id"), d.get("precio"), d.get("costo"),
         d.get("descripcion",""), 1 if d.get("disponible",1) else 0, 1 if d.get("lleva_itbis",1) else 0,
         d.get("tiempo_preparacion",10), 1 if d.get("es_bebida",0) else 0, pid))
    return jsonify(success=True)

@app.route("/api/categoria", methods=["POST"])
@login_required
def api_categoria():
    d = request.get_json(force=True)
    qx("INSERT INTO categorias_menu(nombre, color, orden, activo) VALUES(?,?,?,1)",
       (d.get("nombre"), d.get("color","#3b82f6"), d.get("orden",0)))
    return jsonify(success=True)

# ============================================================
#  INVENTARIO DE INSUMOS
# ============================================================
@app.route("/inventario")
@login_required
def inventario():
    insumos = q("SELECT * FROM insumos ORDER BY nombre")
    movs = q("""SELECT mi.*, i.nombre insumo, u.nombre_completo usuario FROM movimientos_inventario mi
        LEFT JOIN insumos i ON i.id=mi.insumo_id LEFT JOIN usuarios u ON u.id=mi.usuario_id
        ORDER BY mi.id DESC LIMIT 30""")
    return render_template("inventario.html", insumos=insumos, movs=movs)

@app.route("/api/insumo", methods=["POST"])
@login_required
def api_insumo():
    d = request.get_json(force=True)
    qx("INSERT INTO insumos(nombre, unidad, stock, stock_minimo, costo_unitario) VALUES(?,?,?,?,?)",
       (d.get("nombre"), d.get("unidad","unid"), d.get("stock",0), d.get("stock_minimo",0), d.get("costo_unitario",0)))
    return jsonify(success=True)

@app.route("/api/insumo/<int:iid>", methods=["PUT","DELETE"])
@login_required
def api_insumo_edit(iid):
    if request.method == "DELETE":
        qx("DELETE FROM insumos WHERE id=?", (iid,)); return jsonify(success=True)
    d = request.get_json(force=True)
    qx("UPDATE insumos SET nombre=?, unidad=?, stock=?, stock_minimo=?, costo_unitario=? WHERE id=?",
       (d.get("nombre"), d.get("unidad"), d.get("stock"), d.get("stock_minimo"), d.get("costo_unitario"), iid))
    return jsonify(success=True)

@app.route("/api/inventario/ajuste", methods=["POST"])
@login_required
def api_ajuste():
    d = request.get_json(force=True)
    qx("UPDATE insumos SET stock=stock+? WHERE id=?", (d.get("cantidad",0), d.get("insumo_id")))
    qx("INSERT INTO movimientos_inventario(fecha, insumo_id, tipo, cantidad, referencia, usuario_id) VALUES(?,?,?,?,?,?)",
       (now(), d.get("insumo_id"), d.get("tipo","AJUSTE"), d.get("cantidad",0), d.get("referencia",""), session["user_id"]))
    return jsonify(success=True)

# ============================================================
#  COMPRAS Y PROVEEDORES
# ============================================================
@app.route("/compras")
@login_required
def compras():
    proveedores = q("SELECT * FROM proveedores ORDER BY nombre")
    insumos = q("SELECT * FROM insumos ORDER BY nombre")
    compras_l = q("""SELECT c.*, p.nombre proveedor FROM compras c LEFT JOIN proveedores p ON p.id=c.proveedor_id
        ORDER BY c.id DESC LIMIT 30""")
    return render_template("compras.html", proveedores=proveedores, insumos=insumos, compras=compras_l)

@app.route("/api/compra", methods=["POST"])
@login_required
def api_compra():
    d = request.get_json(force=True)
    items = d.get("items", [])
    subtotal = sum(float(i["cantidad"])*float(i["costo"]) for i in items)
    itbis = subtotal*0.18; total = subtotal+itbis
    numero = "C-" + datetime.datetime.now().strftime("%Y%m%d-") + str(q("SELECT COALESCE(MAX(id),0)+1 n FROM compras", one=True)["n"])
    cid = qx("INSERT INTO compras(numero, proveedor_id, fecha, subtotal, itbis, total, estado, usuario_id) VALUES(?,?,?,?,?,?, 'RECIBIDA', ?)",
             (numero, d.get("proveedor_id"), now(), subtotal, itbis, total, session["user_id"]))
    for i in items:
        qx("INSERT INTO compras_detalle(compra_id, insumo_id, nombre, cantidad, costo) VALUES(?,?,?,?,?)",
           (cid, i.get("insumo_id"), i.get("nombre"), i["cantidad"], i["costo"]))
        qx("UPDATE insumos SET stock=stock+? WHERE id=?", (i["cantidad"], i.get("insumo_id")))
        qx("INSERT INTO movimientos_inventario(fecha, insumo_id, tipo, cantidad, referencia, usuario_id) VALUES(?,?, 'COMPRA', ?, ?, ?)",
           (now(), i.get("insumo_id"), i["cantidad"], numero, session["user_id"]))
    return jsonify(success=True, id=cid)

@app.route("/proveedores")
@login_required
def proveedores():
    prov = q("SELECT * FROM proveedores ORDER BY nombre")
    return render_template("proveedores.html", proveedores=prov)

@app.route("/api/proveedor", methods=["POST"])
@login_required
def api_proveedor():
    d = request.get_json(force=True)
    qx("INSERT INTO proveedores(nombre, rnc, telefono, direccion, email, dias_credito, limite_credito) VALUES(?,?,?,?,?,?,?)",
       (d.get("nombre"), d.get("rnc",""), d.get("telefono",""), d.get("direccion",""), d.get("email",""),
        d.get("dias_credito",0), d.get("limite_credito",0)))
    return jsonify(success=True)

@app.route("/api/proveedor/<int:pid>", methods=["PUT","DELETE"])
@login_required
def api_proveedor_edit(pid):
    if request.method == "DELETE":
        qx("DELETE FROM proveedores WHERE id=?", (pid,)); return jsonify(success=True)
    d = request.get_json(force=True)
    qx("UPDATE proveedores SET nombre=?, rnc=?, telefono=?, direccion=?, email=?, dias_credito=?, limite_credito=? WHERE id=?",
       (d.get("nombre"), d.get("rnc",""), d.get("telefono",""), d.get("direccion",""), d.get("email",""),
        d.get("dias_credito",0), d.get("limite_credito",0), pid))
    return jsonify(success=True)

# ============================================================
#  CLIENTES (delivery / consumidores)
# ============================================================
@app.route("/clientes")
@login_required
def clientes():
    cli = q("SELECT * FROM clientes ORDER BY nombre")
    return render_template("clientes.html", clientes=cli)

@app.route("/api/cliente", methods=["POST"])
@login_required
def api_cliente():
    d = request.get_json(force=True)
    qx("INSERT INTO clientes(nombre, rnc_cedula, telefono, direccion, email, zona_delivery, notas) VALUES(?,?,?,?,?,?,?)",
       (d.get("nombre"), d.get("rnc_cedula",""), d.get("telefono",""), d.get("direccion",""), d.get("email",""),
        d.get("zona_delivery",""), d.get("notas","")))
    return jsonify(success=True)

@app.route("/api/cliente/<int:cid>", methods=["PUT","DELETE"])
@login_required
def api_cliente_edit(cid):
    if request.method == "DELETE":
        qx("DELETE FROM clientes WHERE id=?", (cid,)); return jsonify(success=True)
    d = request.get_json(force=True)
    qx("UPDATE clientes SET nombre=?, rnc_cedula=?, telefono=?, direccion=?, email=?, zona_delivery=?, notas=? WHERE id=?",
       (d.get("nombre"), d.get("rnc_cedula",""), d.get("telefono",""), d.get("direccion",""), d.get("email",""),
        d.get("zona_delivery",""), d.get("notas",""), cid))
    return jsonify(success=True)

# ============================================================
#  CAJA
# ============================================================
@app.route("/caja")
@login_required
def caja():
    cajas = q("SELECT * FROM cajas WHERE activo=1")
    sesiones = q("""SELECT s.*, c.nombre caja_nombre, u.nombre_completo FROM sesiones_caja s
        LEFT JOIN cajas c ON c.id=s.caja_id LEFT JOIN usuarios u ON u.id=s.usuario_id ORDER BY s.id DESC LIMIT 15""")
    movs = q("""SELECT m.*, u.nombre_completo FROM movimientos_caja m LEFT JOIN usuarios u ON u.id=m.usuario_id
        ORDER BY m.id DESC LIMIT 30""")
    abierta = q("SELECT * FROM sesiones_caja WHERE estado='ABIERTA' ORDER BY id DESC LIMIT 1", one=True)
    return render_template("caja.html", cajas=cajas, sesiones=sesiones, movimientos=movs, abierta=abierta)

@app.route("/api/caja/apertura", methods=["POST"])
@login_required
def api_caja_apertura():
    d = request.get_json(force=True)
    if q("SELECT id FROM sesiones_caja WHERE estado='ABIERTA'", one=True):
        return jsonify(success=False, error="Ya hay una caja abierta. Ciérrela primero.")
    sid = qx("INSERT INTO sesiones_caja(caja_id, usuario_id, apertura, monto_inicial, estado) VALUES(?,?,?,?, 'ABIERTA')",
             (d.get("caja_id",1), session["user_id"], now(), d.get("monto_inicial",0)))
    qx("INSERT INTO movimientos_caja(sesion_id, fecha, tipo, concepto, monto, forma_pago, usuario_id) VALUES(?,?, 'INGRESO', 'Fondo de caja inicial', ?, 'Efectivo', ?)",
       (sid, now(), d.get("monto_inicial",0), session["user_id"]))
    audit("CAJA_APERTURA", f"sesion {sid}")
    return jsonify(success=True)

@app.route("/api/caja/cierre/<int:sid>", methods=["POST"])
@login_required
def api_caja_cierre(sid):
    d = request.get_json(force=True)
    qx("UPDATE sesiones_caja SET cierre=?, monto_cierre=?, estado='CERRADA' WHERE id=?",
       (now(), d.get("monto_cierre",0), sid))
    audit("CAJA_CIERRE", f"sesion {sid}")
    return jsonify(success=True)

@app.route("/api/caja/movimiento", methods=["POST"])
@login_required
def api_caja_movimiento():
    d = request.get_json(force=True)
    s = q("SELECT id FROM sesiones_caja WHERE estado='ABIERTA' ORDER BY id DESC LIMIT 1", one=True)
    if not s: return jsonify(success=False, error="No hay caja abierta")
    qx("INSERT INTO movimientos_caja(sesion_id, fecha, tipo, concepto, monto, forma_pago, referencia, usuario_id) VALUES(?,?,?,?,?,?,?,?)",
       (s["id"], now(), d.get("tipo","INGRESO"), d.get("concepto",""), d.get("monto",0),
        d.get("forma_pago","Efectivo"), d.get("referencia",""), session["user_id"]))
    return jsonify(success=True)

# ============================================================
#  REPORTES
# ============================================================
@app.route("/reportes")
@login_required
def reportes():
    return render_template("reportes.html")

@app.route("/api/reporte/<tipo>")
@login_required
def api_reporte(tipo):
    desde = request.args.get("desde", today()+" 00:00:00")
    hasta = request.args.get("hasta", now())
    if tipo == "ventas":
        filas = q("""SELECT v.*, c.nombre cliente FROM ventas v LEFT JOIN clientes c ON c.id=v.cliente_id
            WHERE v.fecha BETWEEN ? AND ? ORDER BY v.id DESC""", (desde, hasta))
        tot = q("SELECT COALESCE(SUM(total),0) t, COUNT(*) c FROM ventas WHERE fecha BETWEEN ? AND ?", (desde,hasta), one=True)
        return jsonify(success=True, filas=[dict(f) for f in filas], total=tot["t"], cantidad=tot["c"])
    if tipo == "platos":
        filas = q("""SELECT vd.nombre, SUM(vd.cantidad) cantidad, SUM(vd.cantidad*vd.precio) total
            FROM ventas_detalle vd JOIN ventas v ON v.id=vd.venta_id WHERE v.fecha BETWEEN ? AND ?
            GROUP BY vd.nombre ORDER BY total DESC""", (desde, hasta))
        return jsonify(success=True, filas=[dict(f) for f in filas])
    if tipo == "meseros":
        filas = q("""SELECT u.nombre_completo mesero, COUNT(o.id) ordenes, COALESCE(SUM(o.total),0) total
            FROM ordenes o LEFT JOIN usuarios u ON u.id=o.usuario_id
            WHERE o.estado='CERRADA' AND o.fecha_cierre BETWEEN ? AND ? GROUP BY u.id ORDER BY total DESC""", (desde, hasta))
        return jsonify(success=True, filas=[dict(f) for f in filas])
    if tipo == "mesas":
        filas = q("""SELECT m.nombre mesa, COUNT(o.id) ordenes, COALESCE(SUM(o.total),0) total
            FROM ordenes o LEFT JOIN mesas m ON m.id=o.mesa_id
            WHERE o.estado='CERRADA' AND o.fecha_cierre BETWEEN ? AND ? GROUP BY m.id ORDER BY total DESC""", (desde, hasta))
        return jsonify(success=True, filas=[dict(f) for f in filas])
    if tipo == "caja":
        filas = q("""SELECT * FROM movimientos_caja WHERE fecha BETWEEN ? AND ? ORDER BY id DESC""", (desde, hasta))
        return jsonify(success=True, filas=[dict(f) for f in filas])
    return jsonify(success=False, error="Reporte no disponible")

# ============================================================
#  USUARIOS
# ============================================================
@app.route("/usuarios")
@login_required
def usuarios():
    users = q("""SELECT u.*, r.nombre rol FROM usuarios u LEFT JOIN roles r ON r.id=u.rol_id ORDER BY u.id""")
    roles = q("SELECT * FROM roles ORDER BY id")
    return render_template("usuarios.html", usuarios=users, roles=roles)

@app.route("/api/usuario", methods=["POST"])
@login_required
def api_usuario():
    d = request.get_json(force=True)
    qx("INSERT INTO usuarios(username, password_hash, nombre_completo, rol_id, pin, activo, fecha_creacion) VALUES(?,?,?,?,?,1,?)",
       (d.get("username"), generate_password_hash(d.get("password","1234")), d.get("nombre_completo"),
        d.get("rol_id",2), d.get("pin","0000"), now()))
    return jsonify(success=True)

@app.route("/api/usuario/<int:uid>", methods=["PUT","DELETE"])
@login_required
def api_usuario_edit(uid):
    if request.method == "DELETE":
        if uid == 1: return jsonify(success=False, error="No se puede eliminar el administrador principal")
        qx("DELETE FROM usuarios WHERE id=?", (uid,)); return jsonify(success=True)
    d = request.get_json(force=True)
    if d.get("password"):
        qx("UPDATE usuarios SET username=?, nombre_completo=?, rol_id=?, pin=?, password_hash=? WHERE id=?",
           (d.get("username"), d.get("nombre_completo"), d.get("rol_id"), d.get("pin","0000"),
            generate_password_hash(d["password"]), uid))
    else:
        qx("UPDATE usuarios SET username=?, nombre_completo=?, rol_id=?, pin=? WHERE id=?",
           (d.get("username"), d.get("nombre_completo"), d.get("rol_id"), d.get("pin","0000"), uid))
    return jsonify(success=True)

# ============================================================
#  CONFIGURACION
# ============================================================
@app.route("/configuracion")
@login_required
def configuracion():
    emp = q("SELECT * FROM empresa WHERE id=1", one=True)
    areas = q("SELECT * FROM areas_salon ORDER BY id")
    mesas_cfg = q("SELECT m.*, a.nombre area FROM mesas m LEFT JOIN areas_salon a ON a.id=m.area_id ORDER BY a.id, m.id")
    cajas = q("SELECT * FROM cajas ORDER BY id")
    formas = q("SELECT * FROM formas_pago ORDER BY id")
    return render_template("configuracion.html", emp=emp, areas=areas, mesas=mesas_cfg, cajas=cajas, formas=formas, db_path=DB_PATH)

@app.route("/api/configuracion", methods=["POST"])
@login_required
def api_configuracion():
    d = request.get_json(force=True)
    qx("""UPDATE empresa SET razon_social=?, nombre_comercial=?, rnc=?, direccion=?, provincia=?, telefono=?,
        email=?, propina_sugerida=?, itbis=? WHERE id=1""",
        (d.get("razon_social"), d.get("nombre_comercial"), d.get("rnc"), d.get("direccion"), d.get("provincia"),
         d.get("telefono"), d.get("email"), d.get("propina_sugerida",10), d.get("itbis",18)))
    return jsonify(success=True)

@app.route("/api/mesa", methods=["POST"])
@login_required
def api_mesa():
    d = request.get_json(force=True)
    qx("INSERT INTO mesas(nombre, area_id, capacidad, estado) VALUES(?,?,?, 'LIBRE')",
       (d.get("nombre"), d.get("area_id",1), d.get("capacidad",4)))
    return jsonify(success=True)

@app.route("/api/area", methods=["POST"])
@login_required
def api_area():
    d = request.get_json(force=True)
    qx("INSERT INTO areas_salon(nombre, activo) VALUES(?,1)", (d.get("nombre"),))
    return jsonify(success=True)

# ============================================================
#  LOGO COMERCIAL DEL RESTAURANTE (solo para facturas)
#  Se guarda en la carpeta de datos; NO reemplaza al logo del sistema.
# ============================================================
@app.route("/empresa/logo")
def empresa_logo():
    if os.path.exists(LOGO_COMERCIAL_PATH):
        return send_file(LOGO_COMERCIAL_PATH, mimetype="image/png")
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "logo.png"))

@app.route("/api/configuracion/logo", methods=["POST"])
@login_required
def api_configuracion_logo():
    f = request.files.get("logo")
    if not f: return jsonify(success=False, error="No se recibió imagen")
    try:
        from PIL import Image
        img = Image.open(f.stream).convert("RGBA")
        img.thumbnail((512, 512))
        fondo = Image.new("RGBA", img.size, (255,255,255,255))
        fondo.paste(img, (0,0), img)
        fondo.convert("RGB").save(LOGO_COMERCIAL_PATH, "PNG")
    except Exception:
        # Sin Pillow: guardar el archivo tal cual
        f.stream.seek(0)
        with open(LOGO_COMERCIAL_PATH, "wb") as out: out.write(f.stream.read())
    qx("UPDATE empresa SET logo=? WHERE id=1", ("empresa_logo.png",))
    audit("LOGO_EMPRESA", "Logo comercial actualizado (solo facturas)")
    return jsonify(success=True)

@app.route("/api/configuracion/logo", methods=["DELETE"])
@login_required
def api_configuracion_logo_delete():
    if os.path.exists(LOGO_COMERCIAL_PATH): os.remove(LOGO_COMERCIAL_PATH)
    qx("UPDATE empresa SET logo=NULL WHERE id=1")
    return jsonify(success=True)

# ============================================================
#  RESPALDO DE PRODUCCION (descarga de la base de datos)
# ============================================================
@app.route("/api/config/backup")
@login_required
def backup_db():
    import shutil, tempfile
    tmp = os.path.join(tempfile.gettempdir(), "restaurante_pos_backup.db")
    # checkpoint WAL a la base principal
    try:
        db = sqlite3.connect(DB_PATH); db.execute("PRAGMA wal_checkpoint(TRUNCATE)"); db.commit(); db.close()
    except Exception: pass
    shutil.copy2(DB_PATH, tmp)
    audit("BACKUP", "Respaldo de base de datos descargado")
    return send_file(tmp, as_attachment=True, download_name=f"respaldo_restaurante_pos_{datetime.date.today().isoformat()}.db")

# ============================================================
#  PERLA INTELLIGENCE AI — recetas, analisis de inventario y faltantes
# ============================================================
@app.route("/api/plato/<int:pid>/receta", methods=["GET"])
@login_required
def api_receta_get(pid):
    rows = q("""SELECT DISTINCT r.insumo_id, i.nombre, i.unidad, i.stock, i.stock_minimo, r.cantidad
        FROM receta_detalle r JOIN insumos i ON i.id=r.insumo_id WHERE r.plato_id=? ORDER BY i.nombre""", (pid,))
    return jsonify(success=True, items=[dict(r) for r in rows])

@app.route("/api/plato/<int:pid>/receta", methods=["PUT"])
@login_required
def api_receta_put(pid):
    data = request.get_json(force=True) or {}
    items = data.get("items", [])
    qx("DELETE FROM receta_detalle WHERE plato_id=?", (pid,))
    for it in items:
        if it.get("insumo_id") and float(it.get("cantidad", 0)) > 0:
            qx("INSERT INTO receta_detalle(plato_id,insumo_id,cantidad) VALUES(?,?,?)",
               (pid, it["insumo_id"], float(it["cantidad"])))
    audit("RECETA", f"Plato {pid} actualizada")
    return jsonify(success=True)

def descontar_inventario_y_faltantes(items_venta):
    """Descuenta insumos segun recetas y devuelve lista de faltantes (stock <= stock_minimo)."""
    faltantes = []
    tocados = set()
    for it in items_venta:
        pid = it.get("plato_id"); cant = float(it.get("cantidad", 1))
        if not pid: continue
        rec = q("SELECT DISTINCT insumo_id, cantidad FROM receta_detalle WHERE plato_id=?", (pid,))
        for r in rec:
            consumo = float(r["cantidad"]) * cant
            qx("UPDATE insumos SET stock = MAX(0, stock - ?) WHERE id=?", (consumo, r["insumo_id"]))
            tocados.add(r["insumo_id"])
    for iid in tocados:
        ins = q("SELECT * FROM insumos WHERE id=?", (iid,), one=True)
        if ins and float(ins["stock"] or 0) <= float(ins["stock_minimo"] or 0):
            faltantes.append({"nombre": ins["nombre"], "stock": round(float(ins["stock"] or 0), 2),
                              "stock_minimo": round(float(ins["stock_minimo"] or 0), 2), "unidad": ins["unidad"]})
    return faltantes

@app.route("/api/ia/sugerencias")
@login_required
def ia_sugerencias():
    """Perla Intelligence AI: segun el menu activo y ventas recientes, sugiere que comprar."""
    # demanda estimada por plato = promedio diario de los ultimos 7 dias (minimo 5)
    demanda = {}
    rows = q("""SELECT d.plato_id, SUM(d.cantidad)/7.0 as prom
        FROM ventas_detalle d JOIN ventas v ON v.id=d.venta_id
        WHERE v.fecha >= date('now','-7 days') GROUP BY d.plato_id""")
    for r in rows: demanda[r["plato_id"]] = max(5.0, float(r["prom"] or 0))
    # requerimiento por insumo
    insumos = q("SELECT * FROM insumos ORDER BY nombre")
    sugerencias = []
    criticos = 0; bajos = 0
    for ins in insumos:
        recs = q("""SELECT DISTINCT r.cantidad, r.plato_id FROM receta_detalle r WHERE r.insumo_id=?""", (ins["id"],))
        requerido = sum(float(r["cantidad"]) * demanda.get(r["plato_id"], 5.0) for r in recs)
        stock = float(ins["stock"] or 0); smin = float(ins["stock_minimo"] or 0)
        if requerido <= 0 and smin <= 0: continue
        if stock <= smin: nivel = "CRITICO"; criticos += 1
        elif stock < requerido: nivel = "BAJO"; bajos += 1
        else: nivel = "OK"
        comprar = round(max(0, requerido * 1.2 + smin - stock), 2)
        if nivel != "OK" or comprar > 0:
            sugerencias.append({"insumo": ins["nombre"], "unidad": ins["unidad"], "stock": round(stock,2),
                                "stock_minimo": round(smin,2), "requerido": round(requerido,2),
                                "comprar": comprar, "nivel": nivel})
    sugerencias.sort(key=lambda x: (0 if x["nivel"]=="CRITICO" else 1 if x["nivel"]=="BAJO" else 2, -x["comprar"]))
    audit("IA", "Analisis de inventario Perla Intelligence AI")
    return jsonify(success=True, resumen={"total_analizados": len(insumos), "criticos": criticos, "bajos": bajos},
                   sugerencias=sugerencias, faltantes=[s for s in sugerencias if s["nivel"]=="CRITICO"])


# ============================================================
#  PERLA INTELLIGENCE AI — chat de asistencia, alertas y memoria
# ============================================================
def _faltantes_stock():
    rows = q("SELECT nombre, stock, stock_minimo, unidad FROM insumos WHERE stock <= stock_minimo ORDER BY stock ASC")
    return [dict(r) for r in rows]

def _respuesta_stock():
    falt = _faltantes_stock()
    if not falt:
        return "✅ Inventario en niveles óptimos: ningún insumo crítico. Revisa el panel 🤖 Perla Intelligence AI en Inventario para la lista de compras sugerida según tu menú."
    lista = ", ".join(f"{f['nombre']} (quedan {f['stock']} {f['unidad']}, mín. {f['stock_minimo']})" for f in falt[:8])
    return f"⚠️ ALERTA de Perla Intelligence AI: debes comprar {len(falt)} insumo(s) crítico(s): {lista}. Ve a 🛒 Compras para reabastecer, o revisa el panel 🤖 en Inventario."

def ia_responder(mensaje, modulo=""):
    m = (mensaje or "").lower()
    kb = q("SELECT * FROM ia_conocimiento ORDER BY hits DESC")
    mejor, mejor_score = None, 0
    for k in kb:
        score = sum(1 for w in (k["palabras_clave"] or "").split() if w and w in m)
        if score > mejor_score:
            mejor, mejor_score = k, score
    if mejor and mejor_score > 0:
        qx("UPDATE ia_conocimiento SET hits = hits + 1 WHERE id=?", (mejor["id"],))
        resp = mejor["respuesta"]
        if resp == "__STOCK__": resp = _respuesta_stock()
        return resp
    # Aprende: guarda la pregunta como nuevo conocimiento
    palabras = " ".join([w for w in re.split(r"[^a-záéíóúñ]+", m) if len(w) > 3][:10])
    if palabras:
        qx("INSERT OR IGNORE INTO ia_conocimiento(palabras_clave, respuesta, hits) VALUES(?,?,1)",
           (palabras, "Estoy aprendiendo sobre eso. Mientras tanto puedo ayudarte con: caja, órdenes, cobro/factura, inventario, compras, reportes, menú/recetas, cocina, configuración e impresión. ¿Cuál necesitas?"))
    return "🤖 Estoy aprendiendo de tu pregunta (la guardé para mejorar). Puedo ayudarte con: abrir caja, tomar órdenes, cobrar y facturar, inventario y compras, reportes, menú/recetas, cocina/KDS, configuración e impresión de facturas. Reformula tu consulta o elige un tema."

@app.route("/api/ia/chat", methods=["POST"])
@login_required
def ia_chat():
    d = request.get_json(force=True) or {}
    msg = (d.get("mensaje") or "").strip()[:500]
    modulo = d.get("modulo") or ""
    if not msg: return jsonify(success=False, error="Mensaje vacío")
    resp = ia_responder(msg, modulo)
    uid = session.get("user_id")
    qx("INSERT INTO ia_conversaciones(usuario_id, modulo, pregunta, respuesta) VALUES(?,?,?,?)", (uid, modulo, msg, resp))
    return jsonify(success=True, respuesta=resp, alertas=_faltantes_stock())

@app.route("/api/ia/alertas")
@login_required
def ia_alertas():
    return jsonify(success=True, faltantes=_faltantes_stock())

@app.route("/api/info/red")
@login_required
def info_red():
    import socket
    try: ip = socket.gethostbyname(socket.gethostname())
    except Exception: ip = "127.0.0.1"
    return jsonify(success=True, ip=ip, port=5000)

def _ip_red_local():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


# ============================================================
#  SISTEMA DE LICENCIAS (24h / 1 mes / 6 meses / 1 ano / permanente)
# ============================================================
import licencia as _lic
os.environ["PERLA_DATA_DIR"] = DATA_DIR
_lic.activar_demo_24h()  # primer arranque: 24 horas de prueba automaticas

_RUTAS_LIBRES_LIC = ("/activacion", "/static", "/api/licencia", "/api/salir")

@app.before_request
def _control_licencia():
    p = request.path
    if any(p.startswith(r) for r in _RUTAS_LIBRES_LIC):
        return None
    try:
        est = _lic.estado()
    except Exception:
        return None
    if not est.get("activa"):
        return redirect(url_for("activacion"))
    g.licencia = est

@app.route("/activacion", methods=["GET", "POST"])
def activacion():
    mensaje = ""
    clase = "info"
    if request.method == "POST":
        clave = (request.form.get("clave") or "").strip()
        ok, dias, perm, msg = _lic.validar_clave(clave)
        if ok:
            _lic.guardar(clave)
            mensaje = "Licencia activada correctamente. " + msg + ' <a href="/" style="color:#4ade80;font-weight:bold">Entrar al sistema &rarr;</a>'
            clase = "ok"
        else:
            mensaje = "No se pudo activar la licencia: " + msg
            clase = "err"
    est = _lic.estado()
    return render_template("activacion.html", est=est, mensaje=mensaje, clase=clase, duraciones=_lic.DURACIONES)

@app.route("/generador-licencias", methods=["GET", "POST"])
@login_required
def generador_licencias():
    clave_generada = ""
    dur_sel = "1m"
    id_sel = _lic.id_maquina()
    cualquiera = False
    if request.method == "POST":
        dur_sel = request.form.get("duracion", "1m")
        id_sel = (request.form.get("id_maquina") or "").strip() or _lic.id_maquina()
        cualquiera = request.form.get("cualquiera") == "on"
        mid = "*" if cualquiera else id_sel
        try:
            clave_generada = _lic.generar_clave(mid, dur_sel)
        except Exception as e:
            clave_generada = "ERROR: " + str(e)
    return render_template("generador.html", clave=clave_generada, dur_sel=dur_sel,
                           id_sel=id_sel, cualquiera=cualquiera, duraciones=_lic.DURACIONES)

@app.route("/api/licencia/estado")
def api_licencia_estado():
    return jsonify(_lic.estado())


# ============================================================
#  SISTEMA DE IDIOMAS (ES / EN / PT / FR) - se elige en el navegador
# ============================================================
import idiomas as _idi
IDIOMAS_DISP = _idi.IDIOMAS_DISPONIBLES

@app.before_request
def _detectar_idioma():
    lang = request.cookies.get("perla_lang", "es")
    if lang not in IDIOMAS_DISP:
        lang = "es"
    g.idioma = lang

@app.context_processor
def _inyectar_traductor():
    lang = getattr(g, "idioma", "es")
    return {
        "t": lambda k: _idi.traducir(k, lang),
        "idioma_actual": lang,
        "idiomas_disponibles": IDIOMAS_DISP,
    }

if __name__ == "__main__":
    import webbrowser, threading
    port = int(os.environ.get("PORT", 5000))
    en_nube = bool(os.environ.get("RENDER") or os.environ.get("PYTHONANYWHERE_DOMAIN") or os.environ.get("CLOUD"))
    if not en_nube:
        ip_lan = _ip_red_local()
        url_local = f"http://127.0.0.1:{port}"
        url_red = f"http://{ip_lan}:{port}"
        threading.Timer(1.2, lambda: webbrowser.open(url_local)).start()
        print(f"\n  {APP_NAME} v{APP_VERSION}")
        print(f"  Base de datos: {DB_PATH}")
        print(f"  Desde este PC:      {url_local}")
        print(f"  Desde movil/tablet: {url_red}  (conectado al mismo WiFi)")
        print(f"  Usuario inicial: admin / admin123")
        print(f"  No cierre esta ventana mientras use el sistema.\n")
    else:
        print(f"  {APP_NAME} v{APP_VERSION} iniciado en modo nube (puerto {port}).")
    app.run(host="0.0.0.0", port=port, debug=False)
