import psutil
import requests
import threading
import time
import socket
from base_datos import (
    registrar_evento,
    obtener_ips_registradas,
    esta_app_en_lista_blanca,
    contar_registros_ip,
    obtener_registros_ip
)
from ia_detectora import DetectorIA
from remote_apps import REMOTE_APPS
from utils import obtener_ip_local


class MonitorTrafico(threading.Thread):
    def __init__(self, ip_queue, ia_activada=False, detector_ia=None):
        super().__init__(daemon=True)
        self.ip_queue = ip_queue
        self.ia_activada = ia_activada
        self.detector_ia = detector_ia if detector_ia else DetectorIA()
        self.ips_registradas = set(obtener_ips_registradas())

    def run(self):
        while True:
            conexiones = psutil.net_connections(kind='inet')
            for conn in conexiones:
                if conn.status != psutil.CONN_ESTABLISHED:
                    continue

                ip = self.obtener_ip_remota(conn)
                if not ip or self.es_local(ip) or ip in self.ips_registradas:
                    continue

                app = self.obtener_app_desde_ip(ip)
                if esta_app_en_lista_blanca(app):
                    continue

                pais, compania = self.obtener_info_ip(ip)
                app_remota = self.detectar_aplicacion_remota(conn)
                origen = self.obtener_origen_conexion(conn)

                # Obtener puerto y protocolo reales de la conexión
                puerto = 0
                protocolo = "Desconocido"
                try:
                    if conn.raddr:
                        puerto = conn.raddr.port
                    tipo = getattr(conn, 'type', None)
                    print(f"[LOG monitor] conn.type: {tipo} para IP {ip} (puerto {puerto})")
                    if tipo == socket.SOCK_STREAM:
                        protocolo = "TCP"
                    elif tipo == socket.SOCK_DGRAM:
                        protocolo = "UDP"
                except Exception as e:
                    print(f"[LOG monitor] Error obteniendo protocolo: {e}")

                estado = "CONEXION"
                if self.ia_activada and self._deberia_analizar(ip):
                    try:
                        hora, intentos = self._obtener_contexto_ip(ip)
                        if self.detector_ia.analizar_ip(
                            hora, pais, compania, puerto, protocolo, intentos=intentos
                        ):
                            estado = "ANOMALIA"
                    except Exception as e:
                        print(f"[❌] Error al analizar IP con IA: {e}")

                self.procesar_ip(
                    ip, pais, compania, estado, origen, app,
                    puerto=puerto,
                    protocolo=protocolo,
                    motivo_decision="",
                    score_ia=getattr(
                        self.detector_ia, "score_ultima_prediccion", None
                    ),
                    feedback_usuario=None
                )

                # ✅ Entrenar IA si es necesario
                self.detector_ia.entrenar_si_es_necesario()

                if app_remota:
                    self.alertar_usuario(ip, app_remota)

                self.ips_registradas.add(ip)

            time.sleep(1)

    def obtener_ip_remota(self, conn):
        try:
            if conn.raddr:
                return conn.raddr.ip
        except Exception:
            pass
        return None

    def obtener_info_ip(self, ip):
        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,country,isp"
            response = requests.get(url, timeout=2)
            data = response.json()
            if data["status"] == "success":
                pais = data.get("country", "Desconocido")
                compania = data.get("isp", "Desconocido")
                return pais, compania
        except Exception:
            pass
        return "Desconocido", "Desconocido"

    def detectar_aplicacion_remota(self, conn):
        try:
            pid = conn.pid
            proceso = psutil.Process(pid)
            nombre = proceso.name().lower()
            for app in REMOTE_APPS:
                if app.lower() in nombre:
                    return app
        except Exception:
            pass
        return None

    def obtener_app_desde_ip(self, ip):
        conexiones = psutil.net_connections(kind='inet')
        for conn in conexiones:
            if not conn.raddr or conn.raddr.ip != ip:
                continue
            try:
                pid = conn.pid
                if not pid:
                    continue
                proceso = psutil.Process(pid)
                return proceso.name()
            except Exception:
                continue
        return "DESCONOCIDA"

    def obtener_origen_conexion(self, conn):
        try:
            if conn.status == psutil.CONN_LISTEN:
                return "Escuchando"

            if conn.laddr and conn.raddr:
                mi_ip = obtener_ip_local()
                ip_local = conn.laddr.ip
                ip_remota = conn.raddr.ip

                # Si nuestra IP está como local, asumimos saliente
                if ip_local == mi_ip:
                    return "Saliente"
                # Si nuestra IP está como remota, es entrante
                elif ip_remota == mi_ip:
                    return "Entrante"
                # En otros casos, posiblemente redirección NAT o VPN
                else:
                    return "Entrante"
            elif conn.laddr and not conn.raddr:
                return "Local"  # Posiblemente servicio en escucha

        except Exception:
            pass

        return "Desconocido"

    def procesar_ip(
        self, ip, pais, compania, estado, origen, app,
        puerto=0, protocolo="Desconocido",
        motivo_decision="", score_ia=None, feedback_usuario=None
    ):
        data = {
            "ip": ip,
            "estado": estado,
            "origen": origen,
            "tipo": "DESCONOCIDO",
            "pais": pais,
            "compania": compania,
            "app_origen": app,
            "puerto": puerto,
            "protocolo": protocolo,
            "motivo_decision": motivo_decision,
            "score_ia": score_ia,
            "feedback_usuario": feedback_usuario
        }
        self.ip_queue.put(data)
        registrar_evento(data)

    def alertar_usuario(self, ip, app):
        print(f"[⚠️] Posible control remoto detectado: {app} desde {ip}")

    def es_local(self, ip):
        return (
            ip.startswith("192.168.")
            or ip.startswith("10.")
            or ip.startswith("172.")
            or ip == "127.0.0.1"
        )

    def _deberia_analizar(self, ip):
        try:
            return contar_registros_ip(ip) >= 3
        except Exception as e:
            print(f"[⚠️] Error al contar registros de IP {ip}: {e}")
            return False

    def _obtener_contexto_ip(self, ip):
        registros = obtener_registros_ip(ip)
        if not registros:
            raise ValueError("No hay registros suficientes para analizar.")
        hora = registros[-1]["hora"]
        intentos = len(registros)
        return hora, intentos

    def _evaluar_ia(
        self, ip, hora, intentos, pais, compania,
        puerto=0, protocolo="Desconocido"
    ):
        return self.detector_ia.analizar_ip(
            hora, pais, compania, puerto, protocolo, intentos=intentos
        )


def iniciar_monitoreo(ip_queue, detector_ia, ia_activada=True):
    monitor = MonitorTrafico(ip_queue, ia_activada, detector_ia)
    monitor.start()
    return monitor
