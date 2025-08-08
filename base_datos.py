import sqlite3
import time
import utils

DB_PATH = "trafico.db"
IP_CRITICAS = {"127.0.0.1", "8.8.8.8", utils.obtener_ip_local()}

_app_lista_blanca_temporal = {}


def inicializar_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registro_trafico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT,
                pais TEXT,
                compania TEXT,
                puerto INTEGER,
                protocolo TEXT,
                motivo_decision TEXT,
                score_ia REAL,
                feedback_usuario TEXT,
                fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                estado TEXT,
                origen TEXT,
                app_origen TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lista_blanca (
                ip TEXT PRIMARY KEY,
                expira INTEGER,
                comentario TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lista_blanca_apps (
                app_origen TEXT PRIMARY KEY,
                expira INTEGER,
                comentario TEXT
            );
        """)

        for ip in IP_CRITICAS:
            cursor.execute(
                "INSERT OR IGNORE INTO lista_blanca (ip) VALUES (?);",
                (ip,)
            )

        conn.commit()
        print("[📁] Base de datos 'trafico.db' y tablas listas.")
    except sqlite3.Error as e:
        print(f"[❌] Error al inicializar la base de datos: {e}")
        raise
    finally:
        conn.close()


def crear_tablas_listas_negra_paises():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lista_negra (
                ip TEXT PRIMARY KEY,
                expira INTEGER,
                comentario TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paises_bloqueados (
                pais TEXT PRIMARY KEY
            );
        """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"[❌] Error al crear tablas de listas negra/paises: {e}")
        raise
    finally:
        conn.close()


def agregar_a_lista_negra(ip: str, expira: int = None, comentario: str = None) -> bool:
    """Agrega una IP a la lista negra. Si ya existe, la actualiza. Devuelve True si hubo cambios."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO lista_negra (ip, expira, comentario) VALUES (?, ?, ?);",
            (ip, expira, comentario)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[❌] Error al agregar IP a lista negra: {e}")
        return False
    finally:
        conn.close()


def eliminar_de_lista_negra(ip: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM lista_negra WHERE ip = ?;",
            (ip,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[❌] Error al eliminar IP de lista negra: {e}")
        return False
    finally:
        conn.close()


def obtener_lista_negra():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT ip FROM lista_negra;")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[❌] Error al obtener lista negra: {e}")
        return []
    finally:
        conn.close()


def agregar_pais_bloqueado(pais: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO paises_bloqueados (pais) VALUES (?);",
            (pais,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[❌] Error al agregar país bloqueado: {e}")
        return False
    finally:
        conn.close()


def eliminar_pais_bloqueado(pais: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM paises_bloqueados WHERE pais = ?;",
            (pais,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[❌] Error al eliminar país bloqueado: {e}")
        return False
    finally:
        conn.close()


def obtener_paises_bloqueados():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT pais FROM paises_bloqueados;")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[❌] Error al obtener países bloqueados: {e}")
        return []
    finally:
        conn.close()


def registrar_evento(data: dict) -> bool:
    ip = data.get("ip", "0.0.0.0")
    pais = data.get("pais", "Desconocido")
    compania = data.get("compania", "Desconocido")
    puerto = data.get("puerto")
    protocolo = data.get("protocolo")
    motivo_decision = data.get("motivo_decision")
    score_ia = data.get("score_ia")
    feedback_usuario = data.get("feedback_usuario")
    estado = data.get("estado", "SIN_ACCION")
    origen = data.get("origen", "Sistema")
    app_origen = data.get("app_origen", "Desconocida")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 1 FROM registro_trafico
            WHERE ip = ? AND origen = ? AND estado = ?
              AND fecha_hora > datetime('now', '-5 minutes')
            LIMIT 1;
        """, (ip, origen, estado))

        if cursor.fetchone():
            return False

        cursor.execute("""
            INSERT INTO registro_trafico (
                ip, pais, compania, puerto, protocolo, motivo_decision, score_ia, feedback_usuario,
                estado, origen, app_origen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            ip, pais, compania, puerto, protocolo, motivo_decision, score_ia, feedback_usuario,
            estado, origen, app_origen
        ))

        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"[❌] Error al registrar evento: {e}")
        return False
    finally:
        conn.close()


def obtener_historial(limite: int = 100):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ip, pais, compania, puerto, protocolo, motivo_decision, score_ia, feedback_usuario,
                   fecha_hora, estado, origen, app_origen
            FROM registro_trafico
            ORDER BY fecha_hora DESC
            LIMIT ?;
        """, (limite,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"[❌] Error al obtener historial: {e}")
        return []
    finally:
        conn.close()


def obtener_origen_ip(ip):
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT origen FROM eventos WHERE ip = ? ORDER BY fecha DESC LIMIT 1",
        (ip,)
    )
    fila = cursor.fetchone()
    conn.close()
    if fila:
        return fila[0]
    return "Desconocido"


def agregar_a_lista_blanca(ip: str, expira: int = None, comentario: str = None) -> bool:
    """Agrega una IP a la lista blanca. Si ya existe, la actualiza. Devuelve True si hubo cambios."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO lista_blanca (ip, expira, comentario) VALUES (?, ?, ?);",
            (ip, expira, comentario)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[❌] Error al agregar IP a lista blanca: {e}")
        return False
    finally:
        conn.close()


def esta_en_lista_blanca(ip: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM lista_blanca WHERE ip = ? LIMIT 1;",
            (ip,)
        )
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"[❌] Error al consultar lista blanca: {e}")
        return False
    finally:
        conn.close()


def agregar_app_a_lista_blanca(app_origen: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO lista_blanca_apps (app_origen) VALUES (?);",
            (app_origen,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"[❌] Error al agregar app a lista blanca: {e}")
        return False
    finally:
        conn.close()


def esta_app_en_lista_blanca(app_origen: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM lista_blanca_apps WHERE app_origen = ? LIMIT 1;",
            (app_origen,)
        )
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"[❌] Error al consultar lista blanca de apps: {e}")
        return False
    finally:
        conn.close()


def agregar_app_lista_blanca_temporal(app_nombre, duracion=15*60):
    """Agrega una app a la lista blanca temporal (por defecto 15 minutos)."""
    ahora = time.time()
    expiracion = ahora + duracion
    _app_lista_blanca_temporal[app_nombre.lower()] = expiracion


def esta_app_en_lista_blanca_temporal(app_nombre):
    """Devuelve True si la app está en lista blanca temporal"""
    ahora = time.time()
    app_key = app_nombre.lower()
    expiracion = _app_lista_blanca_temporal.get(app_key)
    if expiracion:
        if expiracion > ahora:
            return True
        else:
            # Expiró, eliminar de la lista
            del _app_lista_blanca_temporal[app_key]
    return False


def obtener_ips_registradas():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT ip FROM registro_trafico;")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[❌] Error al obtener IPs registradas: {e}")
        return []
    finally:
        conn.close()


def obtener_eventos_por_app(app_nombre: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ip, pais, compania, fecha_hora, estado, origen, app_origen
            FROM registro_trafico
            WHERE app_origen = ?;
        """, (app_nombre,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"[❌] Error al obtener eventos por app: {e}")
        return []
    finally:
        conn.close()


def contar_registros_ip(ip: str, minutos: int = 5) -> int:
    """Cuenta cuántos registros tiene una IP en los últimos X minutos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM registro_trafico
            WHERE ip = ? AND fecha_hora >= datetime('now', ? || ' minutes');
        """, (ip, f'-{minutos}'))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else 0
    except sqlite3.Error as e:
        print(f"[❌] Error al contar registros de IP {ip}: {e}")
        return 0
    finally:
        conn.close()


def obtener_registros_ip(ip: str, limite: int = 10):
    """Obtiene los últimos registros de una IP."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fecha_hora FROM registro_trafico
            WHERE ip = ?
            ORDER BY fecha_hora DESC
            LIMIT ?;
        """, (ip, limite))
        filas = cursor.fetchall()
        return [{"hora": fila[0]} for fila in filas]
    except sqlite3.Error as e:
        print(f"[❌] Error al obtener registros de IP {ip}: {e}")
        return []
    finally:
        conn.close()


def obtener_registros_entrenamiento():
    """Obtiene todos los registros que no están en la lista blanca para entrenamiento de la IA."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ip, pais, compania, fecha_hora, estado, origen, app_origen
            FROM registro_trafico
            WHERE estado IS NOT NULL
            AND ip NOT IN (SELECT ip FROM lista_blanca)
        """)
        registros = cursor.fetchall()
        return registros
    except sqlite3.Error as e:
        print(f"[❌] Error al obtener registros de entrenamiento: {e}")
        return []
    finally:
        conn.close()


def obtener_ips_lista_blanca():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT ip FROM lista_blanca;")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[❌] Error al obtener IPs de lista blanca: {e}")
        return []
    finally:
        conn.close()


def obtener_lista_blanca():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ip FROM lista_blanca")
    resultado = [fila[0] for fila in cursor.fetchall()]
    conn.close()
    return resultado


def eliminar_de_lista_blanca(ip):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lista_blanca WHERE ip = ?", (ip,))
    conn.commit()
    cambios = cursor.rowcount
    conn.close()
    return cambios > 0


def obtener_lista_blanca_detallada():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ip, expira, comentario FROM lista_blanca")
    resultado = cursor.fetchall()
    conn.close()
    return resultado


def obtener_lista_negra_detallada():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ip, expira, comentario FROM lista_negra")
    resultado = cursor.fetchall()
    conn.close()
    return resultado


def obtener_conexion():
    return sqlite3.connect(DB_PATH)
