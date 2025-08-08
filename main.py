import queue
import sys
import logging
import threading
import time
from interfaz_gui import FirewallGUI, verificar_comportamiento_lista_blanca
from base_datos import inicializar_db
from monitor import iniciar_monitoreo
from ia_detectora import DetectorIA

logging.basicConfig(
    filename="firewall.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def ciclo_verificacion(detector_ia, app):
    while True:
        verificar_comportamiento_lista_blanca(detector_ia, app)
        time.sleep(600)  # Espera 10 minutos


def main():
    logging.info("[🟢] Iniciando Firewall IA")

    try:
        inicializar_db()
        logging.info("[🧱] Base de datos inicializada correctamente")
    except Exception as e:
        logging.error(f"[❌] Error inicializando la base de datos: {e}")
        sys.exit(1)

    ip_queue = queue.Queue()
    detector_ia = DetectorIA()

    try:
        iniciar_monitoreo(ip_queue, detector_ia)
        logging.info("[📡] Monitor de tráfico iniciado")
    except Exception as e:
        logging.error(f"[❌] Error iniciando monitor de tráfico: {e}")
        sys.exit(1)

    try:
        monitor = iniciar_monitoreo(ip_queue, detector_ia)
        app = FirewallGUI(ip_queue, monitor=monitor)
        # Iniciar verificación de lista blanca en hilo
        threading.Thread(
            target=ciclo_verificacion, args=(detector_ia, app), daemon=True
        ).start()
        app.mainloop()
    except Exception as e:
        logging.error(f"[❌] Error al iniciar la interfaz gráfica: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
