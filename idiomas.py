# -*- coding: utf-8 -*-
"""
SISTEMA DE IDIOMAS - PERLA RESTAURANTES
Idiomas: es (Espanol, por defecto), en (English), pt (Portugues), fr (Francais).
Se anaden mas idiomas agregando diccionarios a TRAD.
"""
IDIOMAS_DISPONIBLES = {
    "es": "Español",
    "en": "English",
    "pt": "Português",
    "fr": "Français",
}

TRAD = {
    "es": {
        # Navegacion
        "nav_inicio": "Inicio", "nav_ordenes": "Órdenes de Servicio", "nav_cocina": "Cocina / KDS",
        "nav_pos": "POS / Cobrar", "nav_menu": "Menú", "nav_inventario": "Inventario",
        "nav_compras": "Compras", "nav_proveedores": "Proveedores", "nav_clientes": "Clientes",
        "nav_caja": "Caja y Bancos", "nav_reportes": "Reportes", "nav_usuarios": "Usuarios",
        "nav_configuracion": "Configuración", "nav_licencia": "Licencia", "nav_generador": "Generar licencia",
        # Login
        "login_titulo": "Iniciar sesión", "login_bienvenida": "Bienvenido de nuevo",
        "login_usuario": "Usuario", "login_clave": "Contraseña", "login_entrar": "Entrar al sistema",
        "login_activar": "🔑 Activar / renovar licencia",
        # Comun
        "comun_guardar": "Guardar", "comun_cancelar": "Cancelar", "comun_eliminar": "Eliminar",
        "comun_editar": "Editar", "comun_nuevo": "Nuevo", "comun_buscar": "Buscar",
        "comun_acciones": "Acciones", "comun_estado": "Estado", "comun_fecha": "Fecha",
        "comun_total": "Total", "comun_cerrar_sesion": "Cerrar sesión",
        "comun_idioma": "Idioma",
        # Activacion de licencia
        "lic_titulo": "Activación de Licencia", "lic_activar": "Activar licencia",
        "lic_clave": "CLAVE DE LICENCIA", "lic_id_equipo": "ID de este equipo (envíaselo al proveedor)",
        "lic_duraciones": "Duraciones disponibles", "lic_entrar": "Entrar al sistema",
        # Generador
        "gen_titulo": "🎫 Generador de licencias", "gen_duracion": "Duración de la licencia",
        "gen_id_cliente": "ID del equipo del cliente (se muestra en su pantalla de activación)",
        "gen_cualquiera": "Válida para CUALQUIER equipo (sin bloqueo por máquina)",
        "gen_generar": "⚡ Generar clave de licencia", "gen_copiar": "📋 Copiar clave",
        "gen_copiado": "✅ Copiada al portapapeles",
    },
    "en": {
        "nav_inicio": "Home", "nav_ordenes": "Service Orders", "nav_cocina": "Kitchen / KDS",
        "nav_pos": "POS / Checkout", "nav_menu": "Menu", "nav_inventario": "Inventory",
        "nav_compras": "Purchases", "nav_proveedores": "Suppliers", "nav_clientes": "Customers",
        "nav_caja": "Cash & Banks", "nav_reportes": "Reports", "nav_usuarios": "Users",
        "nav_configuracion": "Settings", "nav_licencia": "License", "nav_generador": "Generate license",
        "login_titulo": "Sign in", "login_bienvenida": "Welcome back",
        "login_usuario": "Username", "login_clave": "Password", "login_entrar": "Enter the system",
        "login_activar": "🔑 Activate / renew license",
        "comun_guardar": "Save", "comun_cancelar": "Cancel", "comun_eliminar": "Delete",
        "comun_editar": "Edit", "comun_nuevo": "New", "comun_buscar": "Search",
        "comun_acciones": "Actions", "comun_estado": "Status", "comun_fecha": "Date",
        "comun_total": "Total", "comun_cerrar_sesion": "Log out",
        "comun_idioma": "Language",
        "lic_titulo": "License Activation", "lic_activar": "Activate license",
        "lic_clave": "LICENSE KEY", "lic_id_equipo": "This device ID (send it to your provider)",
        "lic_duraciones": "Available durations", "lic_entrar": "Enter the system",
        "gen_titulo": "🎫 License generator", "gen_duracion": "License duration",
        "gen_id_cliente": "Customer device ID (shown on their activation screen)",
        "gen_cualquiera": "Valid for ANY device (no machine lock)",
        "gen_generar": "⚡ Generate license key", "gen_copiar": "📋 Copy key",
        "gen_copiado": "✅ Copied to clipboard",
    },
    "pt": {
        "nav_inicio": "Início", "nav_ordenes": "Pedidos de Serviço", "nav_cocina": "Cozinha / KDS",
        "nav_pos": "POS / Cobrar", "nav_menu": "Cardápio", "nav_inventario": "Inventário",
        "nav_compras": "Compras", "nav_proveedores": "Fornecedores", "nav_clientes": "Clientes",
        "nav_caja": "Caixa e Bancos", "nav_reportes": "Relatórios", "nav_usuarios": "Usuários",
        "nav_configuracion": "Configurações", "nav_licencia": "Licença", "nav_generador": "Gerar licença",
        "login_titulo": "Entrar", "login_bienvenida": "Bem-vindo de volta",
        "login_usuario": "Usuário", "login_clave": "Senha", "login_entrar": "Entrar no sistema",
        "login_activar": "🔑 Ativar / renovar licença",
        "comun_guardar": "Salvar", "comun_cancelar": "Cancelar", "comun_eliminar": "Excluir",
        "comun_editar": "Editar", "comun_nuevo": "Novo", "comun_buscar": "Buscar",
        "comun_acciones": "Ações", "comun_estado": "Estado", "comun_fecha": "Data",
        "comun_total": "Total", "comun_cerrar_sesion": "Sair",
        "comun_idioma": "Idioma",
        "lic_titulo": "Ativação de Licença", "lic_activar": "Ativar licença",
        "lic_clave": "CHAVE DE LICENÇA", "lic_id_equipo": "ID deste dispositivo (envie ao fornecedor)",
        "lic_duraciones": "Durações disponíveis", "lic_entrar": "Entrar no sistema",
        "gen_titulo": "🎫 Gerador de licenças", "gen_duracion": "Duração da licença",
        "gen_id_cliente": "ID do dispositivo do cliente (mostrado na tela de ativação)",
        "gen_cualquiera": "Válido para QUALQUER dispositivo (sem bloqueio)",
        "gen_generar": "⚡ Gerar chave de licença", "gen_copiar": "📋 Copiar chave",
        "gen_copiado": "✅ Copiado para a área de transferência",
    },
    "fr": {
        "nav_inicio": "Accueil", "nav_ordenes": "Commandes de Service", "nav_cocina": "Cuisine / KDS",
        "nav_pos": "POS / Encaisser", "nav_menu": "Menu", "nav_inventario": "Inventaire",
        "nav_compras": "Achats", "nav_proveedores": "Fournisseurs", "nav_clientes": "Clients",
        "nav_caja": "Caisse et Banques", "nav_reportes": "Rapports", "nav_usuarios": "Utilisateurs",
        "nav_configuracion": "Paramètres", "nav_licencia": "Licence", "nav_generador": "Générer licence",
        "login_titulo": "Connexion", "login_bienvenida": "Bon retour",
        "login_usuario": "Utilisateur", "login_clave": "Mot de passe", "login_entrar": "Entrer dans le système",
        "login_activar": "🔑 Activer / renouveler la licence",
        "comun_guardar": "Enregistrer", "comun_cancelar": "Annuler", "comun_eliminar": "Supprimer",
        "comun_editar": "Modifier", "comun_nuevo": "Nouveau", "comun_buscar": "Rechercher",
        "comun_acciones": "Actions", "comun_estado": "État", "comun_fecha": "Date",
        "comun_total": "Total", "comun_cerrar_sesion": "Se déconnecter",
        "comun_idioma": "Langue",
        "lic_titulo": "Activation de Licence", "lic_activar": "Activer la licence",
        "lic_clave": "CLÉ DE LICENCE", "lic_id_equipo": "ID de cet appareil (envoyez-le au fournisseur)",
        "lic_duraciones": "Durées disponibles", "lic_entrar": "Entrer dans le système",
        "gen_titulo": "🎫 Générateur de licences", "gen_duracion": "Durée de la licence",
        "gen_id_cliente": "ID de l'appareil client (affiché sur son écran d'activation)",
        "gen_cualquiera": "Valable pour TOUT appareil (sans verrouillage)",
        "gen_generar": "⚡ Générer la clé de licence", "gen_copiar": "📋 Copier la clé",
        "gen_copiado": "✅ Copiée dans le presse-papiers",
    },
}

def traducir(clave, idioma="es"):
    """Traduce una clave. Fallback: espanol, luego la clave misma."""
    return TRAD.get(idioma, TRAD["es"]).get(clave, TRAD["es"].get(clave, clave))
