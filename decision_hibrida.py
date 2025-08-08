from datetime import datetime

from base_datos import (
    obtener_ips_lista_blanca,
    obtener_lista_negra,
    obtener_paises_bloqueados,
    crear_tablas_listas_negra_paises
)

# Inicializar tablas si no existen
crear_tablas_listas_negra_paises()

# --- Puertos críticos por IP ---
PUERTOS_CRITICOS = {3389, 22, 23, 3306, 5432, 8080, 5900}
PUERTOS_PERMITIDOS_POR_IP = {
    # "192.168.0.10": {3389, 22},
    # "10.0.0.5": {3306}
}

# --- Umbrales de frecuencia por IP ---
UMBRAL_FRECUENCIA_GLOBAL = 100
UMBRAL_FRECUENCIA_POR_IP = {
    # "192.168.0.10": 200,
}


def evaluar_conexion(ip, puerto, pais, compania, detector_ia, intentos, permitir_puertos=None):
    """
    Arquitectura híbrida: reglas fijas + IA.
    Devuelve (decision, motivo):
    - decision: 'permitir', 'bloquear', 'revisar'
    - motivo: texto explicativo
    """
    # 1. Lista blanca
    lista_blanca = set(obtener_ips_lista_blanca())
    if ip in lista_blanca:
        return 'permitir', 'IP en lista blanca'


    # 2. Lista negra
    lista_negra = set(obtener_lista_negra())
    if ip in lista_negra:
        return 'bloquear', 'IP en lista negra'

    # 3. País bloqueado
    paises_bloqueados = set(obtener_paises_bloqueados())
    if pais in paises_bloqueados:
        return 'bloquear', f'Tráfico desde país bloqueado: {pais}'

    # 4. Frecuencia anómala (por IP o global)
    umbral = UMBRAL_FRECUENCIA_POR_IP.get(ip, UMBRAL_FRECUENCIA_GLOBAL)
    if intentos >= umbral:
        return 'bloquear', f'Frecuencia anómala: {intentos} conexiones/10s'

    # 5. Puerto crítico por IP
    if puerto in PUERTOS_CRITICOS:
        permitidos = PUERTOS_PERMITIDOS_POR_IP.get(ip, set())
        if not permitir_puertos:
            permitir_puertos = set()
        if puerto not in permitidos and puerto not in permitir_puertos:
            return 'bloquear', f'Puerto crítico no permitido: {puerto}'

    # 6. IA
    ahora = datetime.now()
    # Obtener protocolo si está en el contexto (por compatibilidad)
    protocolo = locals().get('protocolo', 'Desconocido')
    sospechoso = detector_ia.analizar_ip(ahora, pais, compania, puerto, protocolo, intentos=intentos)
    if sospechoso:
        return 'revisar', 'IA detecta comportamiento sospechoso'

    # 7. Permitir por defecto
    return 'permitir', 'Tráfico permitido por reglas e IA'

# --- Ejemplo de uso ---
# decision, motivo = evaluar_conexion(
#     ip, puerto, pais, compania, detector_ia, intentos,
#     permitir_puertos={80,443}
# )
# if decision == 'bloquear':
#     ...
