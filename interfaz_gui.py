import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import requests
import psutil
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tema
import config
import remote_detector
from base_datos import (
    registrar_evento, obtener_historial, obtener_conexion,
    obtener_origen_ip, agregar_app_lista_blanca_temporal,
    esta_app_en_lista_blanca_temporal, agregar_a_lista_blanca,
    obtener_ips_lista_blanca, contar_registros_ip,
    obtener_lista_negra, agregar_a_lista_negra
)
from utils import es_ip_valida, obtener_ip_local
from datetime import datetime
from win_config import ConfigWindow

NOMBRE_REGLA_FIREWALL = "FirewallIA_GUI"


class FirewallGUI(tk.Tk):
    def __init__(self, ip_queue, monitor=None):
        super().__init__()
        self.temas = {"Claro": tema.light, "Oscuro": tema.dark}
        self.tema_actual = self.temas.get(
            config.get_tema(),
            self.temas["Oscuro"]
        )
        self.title("Firewall IA - Monitor de IPs")
        self.geometry("900x600")

        self.ip_queue = ip_queue
        self.monitor = monitor
        self.ia_activada = tk.BooleanVar(value=True)

        # Diccionario apps -> IPs
        self.ips_por_app = {}

        # Aplicación seleccionada en la selector superior
        self.app_actual = tk.StringVar(value="Todas")

        # Frame selector tema + configuración
        selector_frame = tk.Frame(self, bg=self.tema_actual["bg"])
        selector_frame.pack(pady=5, fill="x")

        self.config_btn = ttk.Button(
            selector_frame,
            text="Configuración",
            command=self.abrir_configuracion
        )
        self.config_btn.pack(side=tk.LEFT, padx=10)

        # Etiqueta estado de la IA
        modelo_ia = self.monitor.detector_ia.modelo_actual if hasattr(self.monitor.detector_ia, 'modelo_actual') else "RandomForest"
        estado_ia = "Entrenada ✅" if self.monitor.detector_ia.entrenado else "No entrenada ⚠️"
        color_ia = "green" if self.monitor.detector_ia.entrenado else "red"

        self.etiqueta_ia = tk.Label(
            self,
            text=f"IA: {estado_ia} | Modelo: {modelo_ia}",
            bg=self.tema_actual["bg"],
            fg=color_ia,
            font=("Segoe UI", 10, "bold")
        )
        self.etiqueta_ia.pack(anchor="ne", padx=10, pady=5)

        # selector superior apps (pestañas toggle)
        self.frame_apps = tk.Frame(self, bg=self.tema_actual["bg"])
        self.frame_apps.pack(fill="x", pady=(5, 0))

        self._init_ui()
        self.aplicar_estilo_global(self.tema_actual)
        self.after(1500, self.actualizar_historial)
        self.after(2000, self.check_nuevas_ips)

    def aplicar_estilo_global(self, tema):
        self.configure(bg=tema["bg"])
        style = ttk.Style()
        style.theme_use("default")

        style.configure("TButton",
                        background=tema["button_bg"],
                        foreground=tema["button_fg"],
                        borderwidth=1,
                        focusthickness=3,
                        focuscolor=tema["highlight"])
        style.map("TButton",
                  background=[("active", tema["highlight"])],
                  foreground=[("active", tema["fg"])])

        style.configure("Treeview",
                        background=tema["tree_bg"],
                        foreground=tema["tree_fg"],
                        fieldbackground=tema["tree_bg"],
                        bordercolor=tema["border_color"],
                        borderwidth=1)
        style.map("Treeview",
                  background=[("selected", tema["highlight"])],
                  foreground=[("selected", tema["fg"])])

        style.configure("Treeview.Heading",
                        background=tema["button_bg"],
                        foreground=tema["button_fg"],
                        relief="flat")

        style.configure("TEntry",
                        fieldbackground=tema["entry_bg"],
                        foreground=tema["entry_fg"],
                        background=tema["entry_bg"],
                        bordercolor=tema["border_color"])

        for widget in self.winfo_children():
            self._aplicar_estilo_widget(widget, tema)

    def _aplicar_estilo_widget(self, widget, tema):
        cls = widget.__class__.__name__
        if cls in ["Frame", "LabelFrame"]:
            widget.configure(bg=tema["bg"])
            for child in widget.winfo_children():
                self._aplicar_estilo_widget(child, tema)
        elif cls == "Label":
            widget.configure(bg=tema["bg"], fg=tema["fg"])
        elif cls == "Button":
            if isinstance(widget, ttk.Button):
                pass  # estilos manejados por ttk.Style
            else:
                widget.configure(bg=tema["button_bg"], fg=tema["button_fg"],
                                 activebackground=tema["highlight"],
                                 activeforeground=tema["fg"])
        elif cls == "Entry":
            widget.configure(bg=tema["entry_bg"], fg=tema["entry_fg"],
                             insertbackground=tema["fg"])
        elif cls == "Text":
            widget.configure(bg=tema["entry_bg"], fg=tema["entry_fg"],
                             insertbackground=tema["fg"])

    def cambiar_tema(self, seleccion):
        self.tema_actual = self.temas[seleccion]
        self.aplicar_estilo_global(self.tema_actual)

    def _init_ui(self):
        self.configure(bg=self.tema_actual["bg"])

        columns = ("País", "Compañía", "Fecha", "Estado", "Origen")
        column_widths = (150, 150, 100, 100, 100)
        hist_columns = (
            "ID", "IP", "País", "Compañía", "Puerto", "Protocolo",
            "Motivo", "Score IA", "Feedback", "Fecha", "Estado", "Origen", "Aplicación"
        )

        # Crear tabla principal para IPs
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="tree headings",
            selectmode="browse"
        )
        self.tree.heading("#0", text="Aplicación / IP")
        self.tree.column("#0", width=300)

        # Botón de explicabilidad IA y dashboard
        btn_frame_dash = tk.Frame(self, bg=self.tema_actual["bg"])
        btn_frame_dash.pack(pady=4)
        btn_explicabilidad = tk.Button(btn_frame_dash, text="Explicabilidad IA", command=self.mostrar_explicabilidad_ia)
        btn_explicabilidad.pack(side=tk.LEFT, padx=5)
        btn_dashboard = tk.Button(btn_frame_dash, text="Dashboard", command=self.mostrar_dashboard)
        btn_dashboard.pack(side=tk.LEFT, padx=5)
        self.tree.heading("País", text="País")
        self.tree.column("País", width=150)
        self.tree.heading("Compañía", text="Compañía")
        self.tree.column("Compañía", width=150)
        self.tree.heading("Fecha", text="Fecha")
        self.tree.column("Fecha", width=100)
        self.tree.heading("Estado", text="Estado")
        self.tree.column("Estado", width=100)
        self.tree.heading("Origen", text="Origen")
        self.tree.column("Origen", width=100)

        self.tree.heading("#0", text="Aplicación / IP")
        self.tree.column("#0", width=300)

        for col, width in zip(columns, column_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)

        # Botones acciones
        btn_frame = tk.Frame(self, bg=self.tema_actual["bg"])
        btn_frame.pack(pady=5)

        self.refrescar_btn = tk.Button(
            btn_frame,
            text="Actualizar Historial",
            command=self.actualizar_historial
        )
        self.refrescar_btn.grid(row=0, column=3, padx=10)

        # Label historial y tabla historial
        hist_label = tk.Label(
            self,
            text="Historial de Eventos (Últimos 100)",
            bg=self.tema_actual["bg"],
            fg=self.tema_actual["fg"]
        )
        hist_label.pack()

        self.hist_tree = ttk.Treeview(
            self,
            columns=hist_columns,
            show="headings"
        )
        col_widths = {
            "ID": 40, "IP": 110, "País": 80, "Compañía": 100, "Puerto": 60, "Protocolo": 70,
            "Motivo": 120, "Score IA": 70, "Feedback": 80, "Fecha": 110,
            "Estado": 80, "Origen": 80, "Aplicación": 100
        }
        for col in self.hist_tree["columns"]:
            self.hist_tree.heading(col, text=col)
            self.hist_tree.column(col, width=col_widths.get(col, 100))
        self.hist_tree.pack(fill=tk.BOTH, expand=True, pady=10)

        # Inicializar selector apps
        self._crear_selector_apps()

    def _crear_selector_apps(self):
        self.app_selector = ttk.Combobox(self.frame_apps, state="readonly")
        self._actualizar_selector_apps()
        self.app_selector.pack(side=tk.LEFT, padx=5)
        self.filtro_avanzado = tk.StringVar()
        tk.Label(
            self.frame_apps,
            text="Filtro avanzado:",
            bg=self.tema_actual["bg"],
            fg=self.tema_actual["fg"]
        ).pack(side=tk.LEFT, padx=(10, 0))
        tk.Entry(
            self.frame_apps,
            textvariable=self.filtro_avanzado,
            width=30
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            self.frame_apps,
            text="Filtrar",
            command=self.aplicar_filtro_ips
        ).pack(side=tk.LEFT, padx=5)

        self.app_selector.bind("<<ComboboxSelected>>", self._seleccionar_app)

        # Menú contextual para clic derecho
        self.menu_contextual = tk.Menu(self, tearoff=0)
        self.menu_contextual.add_command(
            label="🛑 Bloquear IP (añadir a lista negra)", command=self._bloquear_ip_seleccionada
        )
        self.menu_contextual.add_command(
            label="✅ Desbloquear IP", command=self._desbloquear_ip_seleccionada
        )
        self.menu_contextual.add_command(
            label="🤍 Añadir a lista blanca", command=self.agregar_lista_blanca
        )
        self.menu_contextual.add_command(
            label="📋 Copiar IP", command=self._copiar_ip_seleccionada
        )
        self.menu_contextual.add_separator()
        self.menu_contextual.add_command(
            label="👍 Marcar como Falso Positivo (Permitir)", command=self._feedback_falso_positivo
        )
        self.menu_contextual.add_command(
            label="👎 Marcar como Falso Negativo (Bloquear)", command=self._feedback_falso_negativo
        )
    def _feedback_falso_positivo(self):
        reg = self._get_registro_historial_seleccionado()
        if not reg:
            messagebox.showinfo("Feedback", "Selecciona un evento del historial.")
            return
        self._aplicar_feedback_ia(reg, confiable=True)

    def _feedback_falso_negativo(self):
        reg = self._get_registro_historial_seleccionado()
        if not reg:
            messagebox.showinfo("Feedback", "Selecciona un evento del historial.")
            return
        self._aplicar_feedback_ia(reg, confiable=False)

    def _get_registro_historial_seleccionado(self):
        item = self.hist_tree.focus()
        if not item:
            return None
        return self.hist_tree.item(item, "values")

    def _aplicar_feedback_ia(self, reg, confiable):
        # Asume orden: ID, IP, País, Compañía, Puerto, Protocolo, Motivo, Score IA, Feedback, Fecha, Estado, Origen, Aplicación
        try:
            from ia_detectora import DetectorIA
            detector_ia = self.monitor.detector_ia if self.monitor else None
            if not detector_ia:
                messagebox.showerror("Feedback IA", "No se encontró la IA activa.")
                return
            hora = datetime.fromisoformat(reg[10]) if reg[10] else datetime.now()
            pais = reg[2]
            compania = reg[3]
            puerto = int(reg[4]) if reg[4] else 0
            protocolo = reg[5] or "Desconocido"
            # proceso eliminado
            intentos = 1  # Opcional: podrías buscar intentos reales
            detector_ia.feedback_manual(hora, pais, compania, intentos, puerto, protocolo, confiable)
            messagebox.showinfo("Feedback IA", "Feedback registrado y la IA ha sido reentrenada.")
        except Exception as e:
            messagebox.showerror("Feedback IA", f"Error al aplicar feedback: {e}")

    def _copiar_ip_seleccionada(self):
        ip = self._get_ip_seleccionada()
        if ip:
            self.clipboard_clear()
            self.clipboard_append(ip)
            self.update()
            messagebox.showinfo("Copiado", f"IP {ip} copiada al portapapeles.")

    def _actualizar_selector_apps(self):
        apps_disponibles = list(self.ips_por_app.keys())
        apps_disponibles.sort()
        self.app_selector["values"] = apps_disponibles
        if apps_disponibles:
            self.app_actual.set(apps_disponibles[0])

    def _seleccionar_app(self, event=None):
        app = self.app_selector.get()
        self._filtrar_por_app(app)
        self._mostrar_ips_de_app(app)

    def _mostrar_ips_de_app(self, app_nombre):
        if not app_nombre or app_nombre not in self.ips_por_app:
            return

        top = tk.Toplevel(self)
        top.title(f"IPs asociadas a: {app_nombre}")
        top.geometry("420x300")

        lista = tk.Listbox(top, font=("Segoe UI", 10))
        lista.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for ip, pais, compania, fecha, tipo, origen in self.ips_por_app.get(
            app_nombre, []
        ):
            texto = f"{ip} | {pais} | {compania} | {fecha} | {tipo} | {origen}"
            lista.insert(tk.END, texto)

    def _filtrar_por_app(self, app=None):
        self.tree.delete(*self.tree.get_children())

        if app and app != "Todas":
            # Mostrar solo la app seleccionada y sus IPs
            ips = self.ips_por_app.get(app, [])
            app_id = self.tree.insert(
                "", "end",
                text=f"{app} ({len(ips)})",
                open=True
            )
            for app_nombre, ips in self.ips_por_app.items():
                app_id = self.tree.insert(
                    "", "end", text=f"{app_nombre} ({len(ips)})", open=False
                )
                for ip, pais, compania, fecha, estado, origen in ips:
                    self.tree.insert(
                        app_id, "end",
                        text=ip,
                        values=(pais, compania, fecha, estado, origen)
                    )

        else:
            # Mostrar todas las apps con sus IPs
            for app_nombre, ips in self.ips_por_app.items():
                app_id = self.tree.insert(
                    "", "end",
                    text=f"{app_nombre} ({len(ips)})",
                    open=False
                )
                for ip, pais, compania, fecha, estado, origen in ips:
                    self.tree.insert(
                        app_id, "end",
                        text=ip,
                        values=(pais, compania, fecha, estado, origen)
                    )

    def bloquear_ip(self, ip=None):
        if ip is None:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Atención", "Selecciona una IP para bloquear."
                )
                return
            ip = self.tree.item(selected)["text"]

        if not es_ip_valida(ip):
            messagebox.showerror("Error", f"IP inválida: {ip}")
            return

        if agregar_a_lista_negra(ip):
            messagebox.showinfo("Lista Negra", f"IP {ip} añadida a lista negra.")
        else:
            messagebox.showinfo("Lista Negra", f"La IP {ip} ya estaba en la lista negra.")
        self.actualizar_historial()

    def desbloquear_ip(self, ip=None):
        if ip is None:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Atención", "Selecciona una IP para desbloquear."
                )
                return
            ip = self.tree.item(selected)["values"][0]

        if not es_ip_valida(ip):
            messagebox.showerror("Error", f"IP inválida: {ip}")
            return

        from base_datos import eliminar_de_lista_negra
        if eliminar_de_lista_negra(ip):
            messagebox.showinfo("Lista Negra", f"IP {ip} eliminada de la lista negra.")
        else:
            messagebox.showinfo("Lista Negra", f"La IP {ip} no estaba en la lista negra.")
        self.actualizar_historial()

    def agregar_lista_blanca(self, ip=None):
        if ip is None:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Atención", "Selecciona una IP para añadir."
                )
                return
            ip = self.tree.item(selected)["values"][0]
        if not es_ip_valida(ip):
            messagebox.showerror("Error", f"IP inválida: {ip}")
            return
        if agregar_a_lista_blanca(ip):
            messagebox.showinfo(
                "Lista Blanca",
                f"IP {ip} añadida a lista blanca."
            )
        else:
            messagebox.showinfo(
                "Lista Blanca",
                f"La IP {ip} ya estaba en la lista blanca."
            )

    def _bloquear_ip_firewall(self, ip):
        try:
            subprocess.run(
                [
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    f"name={NOMBRE_REGLA_FIREWALL}", "dir=in",
                    "action=block", f"remoteip={ip}"
                ],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            messagebox.showerror(
                "Error",
                f"No se pudo bloquear la IP {ip}. "
                "Ejecuta como administrador."
            )
            return False

    def _desbloquear_ip_firewall(self, ip):
        try:
            subprocess.run(
                [
                    "netsh", "advfirewall", "firewall", "delete", "rule",
                    f"name={NOMBRE_REGLA_FIREWALL}", f"remoteip={ip}"
                ],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            messagebox.showerror(
                "Error",
                f"No se pudo desbloquear la IP {ip}. "
                "Ejecuta como administrador."
            )
            return False

    def _mostrar_menu_contextual(self, event):
        row_id = self.hist_tree.identify_row(event.y)
        if row_id:
            self.hist_tree.selection_set(row_id)
            self.menu_contextual.post(event.x_root, event.y_root)

    def _get_ip_seleccionada(self):
        seleccion = self.hist_tree.selection()
        if not seleccion:
            return None
        valores = self.hist_tree.item(seleccion[0], "values")
        return valores[1]  # Asumiendo que la IP está en la segunda columna

    def _bloquear_ip_seleccionada(self):
        ip = self._get_ip_seleccionada()
        if ip:
            self.bloquear_ip(ip)

    def _desbloquear_ip_seleccionada(self):
        ip = self._get_ip_seleccionada()
        if ip:
            self.desbloquear_ip(ip)

    def actualizar_historial(self):
        try:
            # Limitar a los últimos 100 registros para mantener coherencia con la interfaz
            registros = obtener_historial(100)
        except Exception as e:
            print(f"[❌] Error al cargar historial: {e}")
            messagebox.showerror("Error", "No se pudo cargar historial.")
            return

        # Guardar el último id mostrado para evitar refresco innecesario
        if not hasattr(self, '_ultimo_id_historial'):
            self._ultimo_id_historial = None
        if registros:
            id_mas_reciente = registros[0][0]
        else:
            id_mas_reciente = None
        if self._ultimo_id_historial == id_mas_reciente:
            return  # No hay cambios, no refrescar
        self._ultimo_id_historial = id_mas_reciente

        self.hist_tree.delete(*self.hist_tree.get_children())
        for reg in registros:
            fila = {
                "ID": reg[0],
                "IP": reg[1],
                "País": reg[2],
                "Compañía": reg[3],
                "Puerto": reg[4],
                "Protocolo": reg[5],
                "Motivo": reg[6],
                "Score IA": reg[7],
                "Feedback": reg[8],
                "Fecha": reg[9],
                "Estado": reg[10],
                "Origen": reg[11],
                "Aplicación": reg[12]
            }
            columnas = self.hist_tree["columns"]
            valores = [fila.get(col, "") for col in columnas]
            self.hist_tree.insert("", tk.END, values=valores)

    def check_nuevas_ips(self):
        from decision_hibrida import evaluar_conexion
        updated = False
        try:
            obtener_conexion().close()
        except Exception:
            self.after(2000, self.check_nuevas_ips)
            return

        while not self.ip_queue.empty():
            data = self.ip_queue.get()
            ip = data.get("ip")
            tipo = data.get("estado", "SIN_ACCION")
            app = data.get("aplicacion")
            if not app or app == "Desconocida":
                app = self._obtener_app_desde_ip(ip)
            origen = data.get("origen", "Desconocido")

            if not es_ip_valida(ip):
                continue

            # Obtener info para decisión híbrida
            pais, compania, fecha = self._obtener_info_ip(ip)
            intentos = contar_registros_ip(ip, minutos=1)
            detector_ia = self.monitor.detector_ia if self.monitor else None
            puerto = data.get("puerto", 0)
            protocolo = data.get("protocolo", "Desconocido")
            # proceso = data.get("proceso", app)
            feedback_usuario = data.get("feedback_usuario")

            # Decisión híbrida
            decision, motivo = evaluar_conexion(
                ip, puerto, pais, compania, detector_ia, intentos, None
            )
            # Pasar protocolo a la IA si es necesario
            if hasattr(detector_ia, 'analizar_ip'):
                detector_ia.analizar_ip(
                    datetime.now(), pais, compania, puerto, protocolo, intentos=intentos
                )
            score_ia = None
            importancia_ia = None
            if hasattr(detector_ia, "score_ultima_prediccion"):
                score_ia = getattr(detector_ia, "score_ultima_prediccion", None)
            if hasattr(detector_ia, "importancia_variables"):
                importancia_ia = getattr(detector_ia, "importancia_variables", None)

            # Añadir a ips_por_app si no está
            if app not in self.ips_por_app:
                self.ips_por_app[app] = []
            if ip not in [x[0] for x in self.ips_por_app[app]]:
                self.ips_por_app[app].append((
                    ip, pais, compania, fecha, tipo, origen
                ))
                updated = True

            # Actuar según decisión
            if decision == 'bloquear':
                agregar_a_lista_negra(ip)
                messagebox.showwarning("Bloqueo", f"{motivo}\nIP: {ip}")
            elif decision == 'revisar':
                messagebox.showwarning("Revisión IA", f"{motivo}\nIP: {ip}")
            # Si es permitir, no se hace nada especial

            data["pais"] = pais
            data["compania"] = compania
            data["fecha"] = fecha
            data["puerto"] = puerto
            data["protocolo"] = protocolo
            # data["proceso"] = proceso
            data["motivo_decision"] = motivo
            data["score_ia"] = score_ia
            data["importancia_ia"] = importancia_ia
            data["feedback_usuario"] = feedback_usuario
            registrar_evento(data)

        if updated:
            self._actualizar_selector_apps()
            self._filtrar_por_app(self.app_actual.get())
            self.actualizar_estado_ia()

        if self.ia_activada.get():
            self.check_herramientas_remotas()

        self.after(1000, self.check_nuevas_ips)

    def check_herramientas_remotas(self):
        sospechosos = remote_detector.detectar_herramientas_remotas()
        if not sospechosos:
            return

        for proc in sospechosos:
            nombre = proc["name"]
            pid = proc["pid"]

            if esta_app_en_lista_blanca_temporal(nombre):
                continue

            mensaje = (
                f"Se detectó una herramienta de control remoto activa:\n"
                f"{nombre} (PID {pid})\n\n¿Eres tú quien la está usando?"
            )
            respuesta = messagebox.askyesno(
                "⚠️ Control remoto detectado",
                mensaje
            )

            ip_local = obtener_ip_local()

            if respuesta:
                agregar_app_lista_blanca_temporal(nombre)
                messagebox.showinfo(
                    "Aplicación confiable",
                    (
                        f"{nombre} se ha marcado como confiable "
                        "durante 15 minutos."
                    )
                )
            else:
                if self._bloquear_ip_firewall(ip_local):
                    origen_real = obtener_origen_ip(ip_local)
                    registrar_evento({
                        "ip": ip_local,
                        "pais": "Local",
                        "compania": "Desconocida",
                        "estado": "BLOQUEADA_REMOTA",
                        "origen": origen_real,
                        "aplicacion": "Sistema"
                    })
                    messagebox.showwarning(
                        "Alerta",
                        "IP local bloqueada por control remoto no autorizado."
                    )
                    self.actualizar_historial()

    def _obtener_info_ip(self, ip):
        try:
            r = requests.get(
                f"http://ip-api.com/json/{ip}?fields=country,isp",
                timeout=3
            )
            data = r.json()
            fecha_actual = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            return (
                data.get("country", "Desconocido"),
                data.get("isp", "Desconocido"),
                fecha_actual
            )
        except Exception:
            return (
                "Desconocido",
                "Desconocido",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

    def _obtener_app_desde_ip(self, ip_remota):
        try:
            conexiones = psutil.net_connections(kind='all')
            for c in conexiones:
                if c.raddr and c.raddr.ip == ip_remota:
                    try:
                        p = psutil.Process(c.pid)
                        return p.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
        except Exception:
            pass
        return "Desconocida"

    def aplicar_filtro_ips(self):
        filtro = self.filtro_avanzado.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        for app_nombre, ips in self.ips_por_app.items():
            app_id = self.tree.insert(
                "", "end",
                text=f"{app_nombre} ({len(ips)})",
                open=False
            )
            for ip, pais, compania, fecha, estado, origen in ips:
                texto_busqueda = f"{ip} {pais} {compania} {fecha} {estado} {origen} {app_nombre}".lower()
                if filtro in texto_busqueda:
                    self.tree.insert(
                        app_id, "end",
                        text=ip,
                        values=(pais, compania, fecha, estado, origen)
                    )

    def avisar_usuario_lista_blanca(self, ip_sospechosa):
        respuesta = messagebox.askquestion(
            "⚠️ IP sospechosa en lista blanca",
            f"La IP {ip_sospechosa} está en la lista blanca pero su comportamiento es anómalo.\n"
            "¿Deseas bloquearla?"
        )
        if respuesta == "yes":
            if self._bloquear_ip_firewall(ip_sospechosa):
                self.bloquear_ip(ip_sospechosa)
        else:
            print(f"[🟡] Se permitió continuar a la IP {ip_sospechosa}.")

    def actualizar_estado_ia(self):
        if not self.etiqueta_ia:
            return
        entrenada = self.monitor.detector_ia.entrenado
        modelo_ia = self.monitor.detector_ia.modelo_actual if hasattr(self.monitor.detector_ia, 'modelo_actual') else "RandomForest"
        texto = "Entrenada ✅" if entrenada else "No entrenada ⚠️"
        color = "green" if entrenada else "red"
        self.etiqueta_ia.config(text=f"IA: {texto} | Modelo: {modelo_ia}", fg=color)

    def mostrar_dashboard(self):
        import base_datos
        import collections
        win = tk.Toplevel(self)
        win.title("Dashboard de Actividad")
        win.geometry("1000x700")

        # Obtener datos
        eventos = base_datos.obtener_historial(500)
        fechas = []
        estados = []
        paises = []
        companias = []
        ips_bloqueadas = []
        for ev in eventos:
            # id, ip, pais, compania, puerto, protocolo, motivo_decision, score_ia, feedback_usuario, fecha_hora, estado, origen, app_origen
            fechas.append(ev[9][:10])
            estados.append(ev[10])
            paises.append(ev[2])
            companias.append(ev[3])
            if ev[10] and ev[10].lower() == 'bloqueado':
                ips_bloqueadas.append(ev[1])

        # Gráfica 1: Eventos por día y estado
        fig, axs = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle('Dashboard de Actividad Firewall IA', fontsize=16)
        # Subplot 1: Eventos por día y estado
        conteo = collections.Counter(zip(fechas, estados))
        dias = sorted(set(fechas))
        estados_unicos = sorted(set(estados))
        for estado in estados_unicos:
            y = [conteo.get((dia, estado), 0) for dia in dias]
            axs[0, 0].plot(dias, y, label=estado)
        axs[0, 0].set_title('Eventos por día y estado')
        axs[0, 0].set_xlabel('Fecha')
        axs[0, 0].set_ylabel('Cantidad')
        axs[0, 0].legend()
        axs[0, 0].tick_params(axis='x', rotation=45)

        # Subplot 2: Top países
        top_paises = collections.Counter(paises).most_common(10)
        if top_paises:
            axs[0, 1].bar([x[0] for x in top_paises], [x[1] for x in top_paises], color='tab:blue')
            axs[0, 1].set_title('Top países')
            axs[0, 1].tick_params(axis='x', rotation=45)

        # Subplot 3: Top compañías
        top_companias = collections.Counter(companias).most_common(10)
        if top_companias:
            axs[1, 0].bar([x[0] for x in top_companias], [x[1] for x in top_companias], color='tab:green')
            axs[1, 0].set_title('Top compañías')
            axs[1, 0].tick_params(axis='x', rotation=45)

        # Subplot 4: Top IPs bloqueadas
        top_ips = collections.Counter(ips_bloqueadas).most_common(10)
        if top_ips:
            axs[1, 1].bar([x[0] for x in top_ips], [x[1] for x in top_ips], color='tab:red')
            axs[1, 1].set_title('Top IPs bloqueadas')
            axs[1, 1].tick_params(axis='x', rotation=45)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        tk.Button(win, text="Cerrar", command=win.destroy).pack(pady=8)

    def mostrar_explicabilidad_ia(self):
        detector_ia = self.monitor.detector_ia if self.monitor else None
        if not detector_ia or not hasattr(detector_ia, 'obtener_importancia_variables'):
            messagebox.showinfo("Explicabilidad IA", "La IA no está entrenada o no soporta explicabilidad.")
            return
        importancias = detector_ia.obtener_importancia_variables()
        if not importancias:
            messagebox.showinfo("Explicabilidad IA", "La IA aún no tiene datos suficientes para mostrar importancia de variables.")
            return
        texto = "Importancia de variables en la decisión IA:\n\n"
        for k, v in importancias.items():
            texto += f"{k}: {v:.3f}\n"
        score = getattr(detector_ia, 'score_ultima_prediccion', None)
        if score is not None:
            texto += f"\nScore última predicción (prob. sospechoso): {score:.2f}"
        messagebox.showinfo("Explicabilidad IA", texto)

    def mostrar_lista_negra(self):
        top = tk.Toplevel(self)
        top.title("Lista Negra de IPs")
        top.geometry("400x400")
        lista = tk.Listbox(top, font=("Segoe UI", 10))
        lista.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for ip in obtener_lista_negra():
            lista.insert(tk.END, ip)
        tk.Button(top, text="Cerrar", command=top.destroy).pack(pady=5)

    # --- Ventana configuración ---
    def abrir_configuracion(self):
        ConfigWindow(self, self.temas, self.cambiar_tema)


def verificar_comportamiento_lista_blanca(detector, gui=None):
    lista = obtener_ips_lista_blanca()
    for ip in lista:
        ahora = datetime.now()
        intentos = detector.contar_intentos_recientes(ip)
    # Se asume puerto/protocolo desconocidos para lista blanca
    if detector.analizar_ip(ahora, "Desconocido", "Desconocido", 0, "Desconocido", intentos=intentos):
        print(f"[⚠️] IP en lista blanca sospechosa: {ip}")
        if gui:
            gui.avisar_usuario_lista_blanca(ip)
