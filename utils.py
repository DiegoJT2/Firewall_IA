import socket
import ipaddress


def es_ip_publica(ip: str) -> bool:
    """Retorna True si la IP es pública, False si es privada o reservada."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return not (
            ip_obj.is_private or
            ip_obj.is_loopback or
            ip_obj.is_link_local
        )
    except ValueError:
        return False  # IP inválida


def es_ip_valida(ip: str) -> bool:
    """Verifica que una IP sea válida (IPv4 o IPv6)."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def obtener_ip_local() -> str:
    """
    Obtiene la IP local de la máquina (IPv4).
    Intenta conectarse a un host externo para conocer la IP usada.
    En caso de error, devuelve '127.0.0.1'.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # IP pública de Google DNS
        ip_local = s.getsockname()[0]
        s.close()
        return ip_local
    except Exception:
        return "127.0.0.1"
