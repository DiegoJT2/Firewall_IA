import tkinter as tk
from tkinter import messagebox
import sys
import winreg
import config
import base_datos


class ConfigWindow(tk.Toplevel):
    def eliminar_ip_lista_negra(self):
        seleccion = self.listbox_ips_negra.curselection()
        if seleccion:
            ip = self.listbox_ips_negra.get(seleccion)
            if base_datos.eliminar_de_lista_negra(ip):
                self.listbox_ips_negra.delete(seleccion)
                messagebox.showinfo("Éxito", f"La IP {ip} fue eliminada de la lista negra.")
            else:
                messagebox.showwarning("Advertencia", f"No se pudo eliminar la IP {ip} de la lista negra.")
        else:
            messagebox.showwarning(
                "Advertencia",
                "Selecciona una IP para eliminar de la lista negra."
            )

    def __init__(self, parent, temas: dict, cambiar_tema_callback):
        super().__init__(parent)
        self.title("Configuración")
        self.geometry("400x300")
        self.resizable(False, False)

        self.temas = temas
        self.tema_actual = self.temas[config.get_tema()]
        self.cambiar_tema = cambiar_tema_callback

        self.configure(bg=self.tema_actual["bg"])

        self.var_auto_inicio = tk.BooleanVar(value=config.get_auto_start())
        self.var_minimizar_bandeja = tk.BooleanVar(value=config.get_minimize_to_tray())

        tk.Label(
            self,
            text="Opciones de ejecución",
            font=("Segoe UI", 12),
            bg=self.tema_actual["bg"],
            fg=self.tema_actual["fg"]
            ).pack(pady=(10, 10))

        tk.Label(
            self,
            text="Tema",
            bg=self.tema_actual["bg"],
            fg=self.tema_actual["fg"]
        ).pack(anchor="w", padx=20, pady=(5, 2))

        self.tema_var = tk.StringVar(value=config.get_tema())
        tema_menu = tk.OptionMenu(
            self,
            self.tema_var,
            *self.temas.keys(),
            command=self.guardar_tema
        )
        tema_menu.pack(anchor="w", padx=20)
        tema_menu.configure(
            bg=self.tema_actual["button_bg"],
            fg=self.tema_actual["button_fg"],
            highlightbackground=self.tema_actual["border_color"],
            activebackground=self.tema_actual["highlight"],
            activeforeground=self.tema_actual["button_fg"]
        )

        # Selector de modelo IA
        tk.Label(
            self,
            text="Modelo de IA",
            bg=self.tema_actual["bg"],
            fg=self.tema_actual["fg"]
        ).pack(anchor="w", padx=20, pady=(10, 2))
        self.modelos_ia = ["RandomForest", "XGBoost", "LightGBM", "IsolationForest"]
        self.modelo_ia_var = tk.StringVar(value=config.get_modelo_ia())

        modelo_menu = tk.OptionMenu(
            self,
            self.modelo_ia_var,
            *self.modelos_ia,
            command=self.guardar_modelo_ia
        )
        modelo_menu.pack(anchor="w", padx=20)
        modelo_menu.configure(
            bg=self.tema_actual["button_bg"],
            fg=self.tema_actual["button_fg"],
            highlightbackground=self.tema_actual["border_color"],
            activebackground=self.tema_actual["highlight"],
            activeforeground=self.tema_actual["button_fg"]
        )

        tk.Checkbutton(
            self,
            text="Iniciar con Windows",
            variable=self.var_auto_inicio,
            command=self.guardar_config_auto_inicio,
            bg=self.tema_actual["bg"],
            fg=self.tema_actual["fg"],
            selectcolor=self.tema_actual["bg"],
            activebackground=self.tema_actual["bg"],
            activeforeground=self.tema_actual["fg"]
        ).pack(anchor="w", padx=20, pady=5)

        tk.Checkbutton(
            self,
            text="Minimizar a bandeja al cerrar",
            variable=self.var_minimizar_bandeja,
            command=self.guardar_config_minimizar_bandeja,
            bg=self.tema_actual["bg"],
            fg=self.tema_actual["fg"],
            selectcolor=self.tema_actual["bg"],
            activebackground=self.tema_actual["bg"],
            activeforeground=self.tema_actual["fg"]
        ).pack(anchor="w", padx=20, pady=5)

        tk.Button(
            self,
            text="Mostrar lista blanca/negra",
            bg=self.tema_actual["button_bg"],
            fg=self.tema_actual["button_fg"],
            activebackground=self.tema_actual["highlight"],
            activeforeground=self.tema_actual["fg"],
            command=self.mostrar_lista_blanca
        ).pack(pady=(10, 0))

        tk.Button(
            self,
            text="Cerrar",
            bg=self.tema_actual["button_bg"],
            fg=self.tema_actual["button_fg"],
            activebackground=self.tema_actual["highlight"],
            activeforeground=self.tema_actual["fg"],
            command=self.destroy
        ).pack(pady=15)

    def guardar_modelo_ia(self, seleccion):
        import config
        config.set_modelo_ia(seleccion)
        # Aquí se podría notificar a la app principal para recargar el modelo si es necesario

    def guardar_tema(self, seleccion):
        config.set_tema(seleccion)
        self.tema_actual = self.temas[seleccion]
        self.cambiar_tema(seleccion)
        self.configure(bg=self.tema_actual["bg"])

    def guardar_config_auto_inicio(self):
        estado = self.var_auto_inicio.get()
        config.set_auto_start(estado)
        if estado:
            self.crear_inicio_auto()
        else:
            self.eliminar_inicio_auto()

    def guardar_config_minimizar_bandeja(self):
        estado = self.var_minimizar_bandeja.get()
        config.set_minimize_to_tray(estado)

    def crear_inicio_auto(self):
        try:
            ruta_app = sys.executable
            clave = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(clave, "FirewallIA", 0, winreg.REG_SZ, ruta_app)
            winreg.CloseKey(clave)
            print("[✔] Añadido a inicio automático con Windows.")
        except Exception as e:
            print(f"[❌] Error al configurar inicio automático: {e}")

    def eliminar_inicio_auto(self):
        try:
            clave = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(clave, "FirewallIA")
            winreg.CloseKey(clave)
            print("[✔] Eliminado del inicio automático con Windows.")
        except FileNotFoundError:
            print("[ℹ️] La entrada de inicio automático no existe.")
        except Exception as e:
            print(f"[❌] Error al eliminar del inicio automático: {e}")

    def mostrar_lista_blanca(self):
        ventana = tk.Toplevel(self)
        ventana.title("Listas blanca y negra")
        ventana.geometry("800x600")
        ventana.resizable(True, True)
        ventana.configure(bg=self.tema_actual["bg"])

        # Filtro avanzado
        filtro_frame = tk.Frame(ventana, bg=self.tema_actual["bg"])
        filtro_frame.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(filtro_frame, text="Filtro avanzado:", bg=self.tema_actual["bg"], fg=self.tema_actual["fg"], font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self.filtro_var = tk.StringVar()
        filtro_entry = tk.Entry(filtro_frame, textvariable=self.filtro_var, bg=self.tema_actual["entry_bg"], fg=self.tema_actual["entry_fg"])
        filtro_entry.pack(side=tk.LEFT, padx=10, fill="x", expand=True)
        tk.Button(filtro_frame, text="Filtrar", command=self.aplicar_filtro_listas, bg=self.tema_actual["button_bg"], fg=self.tema_actual["button_fg"], activebackground=self.tema_actual["highlight"], activeforeground=self.tema_actual["fg"], relief="flat").pack(side=tk.LEFT, padx=5)
        tk.Button(filtro_frame, text="Limpiar", command=self.limpiar_filtro_listas, bg=self.tema_actual["button_bg"], fg=self.tema_actual["button_fg"], activebackground=self.tema_actual["highlight"], activeforeground=self.tema_actual["fg"], relief="flat").pack(side=tk.LEFT)

        frame_blanca = tk.Frame(ventana, bg=self.tema_actual["bg"])
        frame_blanca.pack(side=tk.LEFT, fill="both", expand=True, padx=(10,5), pady=10)
        frame_negra = tk.Frame(ventana, bg=self.tema_actual["bg"])
        frame_negra.pack(side=tk.RIGHT, fill="both", expand=True, padx=(5,10), pady=10)

        tk.Label(frame_blanca, text="Lista blanca", bg=self.tema_actual["bg"], fg=self.tema_actual["fg"], font=("Segoe UI", 11, "bold")).pack()
        tk.Label(frame_negra, text="Lista negra", bg=self.tema_actual["bg"], fg=self.tema_actual["fg"], font=("Segoe UI", 11, "bold")).pack()

        self.listbox_ips = tk.Listbox(
            frame_blanca,
            height=10,
            bg=self.tema_actual["entry_bg"],
            fg=self.tema_actual["entry_fg"],
            selectbackground=self.tema_actual["highlight"],
            selectforeground=self.tema_actual["fg"],
            relief="flat"
        )
        self.listbox_ips.pack(padx=5, pady=5, fill="both", expand=True)

        self.listbox_ips_negra = tk.Listbox(
            frame_negra,
            height=10,
            bg=self.tema_actual["entry_bg"],
            fg=self.tema_actual["entry_fg"],
            selectbackground=self.tema_actual["highlight"],
            selectforeground=self.tema_actual["fg"],
            relief="flat"
        )
        self.listbox_ips_negra.pack(padx=5, pady=5, fill="both", expand=True)

        # Guardar listas originales para filtrar
        self._lista_blanca_original = base_datos.obtener_lista_blanca_detallada()
        self._lista_negra_original = base_datos.obtener_lista_negra_detallada()
        for ip, expira, comentario in self._lista_blanca_original:
            texto = f"{ip} | expira: {expira if expira else '-'} | {comentario if comentario else ''}"
            self.listbox_ips.insert(tk.END, texto)
        for ip, expira, comentario in self._lista_negra_original:
            texto = f"{ip} | expira: {expira if expira else '-'} | {comentario if comentario else ''}"
            self.listbox_ips_negra.insert(tk.END, texto)

        btns_frame = tk.Frame(ventana, bg=self.tema_actual["bg"])
        btns_frame.pack(fill="x", pady=(0,10))

        btn_eliminar_blanca = tk.Button(
            btns_frame,
            command=self.eliminar_ip_lista_blanca,
            text="Eliminar IP blanca seleccionada",
            bg=self.tema_actual["button_bg"],
            fg=self.tema_actual["button_fg"],
            activebackground=self.tema_actual["highlight"],
            activeforeground=self.tema_actual["fg"],
            relief="flat",
            padx=10, pady=5
        )
        btn_eliminar_blanca.pack(side=tk.LEFT, padx=20)

        btn_eliminar_negra = tk.Button(
            btns_frame,
            command=self.eliminar_ip_lista_negra,
            text="Eliminar IP negra seleccionada",
            bg=self.tema_actual["button_bg"],
            fg=self.tema_actual["button_fg"],
            activebackground=self.tema_actual["highlight"],
            activeforeground=self.tema_actual["fg"],
            relief="flat",
            padx=10, pady=5
        )
        btn_eliminar_negra.pack(side=tk.RIGHT, padx=20)

    def aplicar_filtro_listas(self):
        filtro = self.filtro_var.get().strip().lower()
        self.listbox_ips.delete(0, tk.END)
        self.listbox_ips_negra.delete(0, tk.END)
        if filtro:
            for ip, expira, comentario in self._lista_blanca_original:
                texto = f"{ip} | expira: {expira if expira else '-'} | {comentario if comentario else ''}"
                if (filtro in ip.lower() or (expira and filtro in str(expira)) or (comentario and filtro in comentario.lower())):
                    self.listbox_ips.insert(tk.END, texto)
            for ip, expira, comentario in self._lista_negra_original:
                texto = f"{ip} | expira: {expira if expira else '-'} | {comentario if comentario else ''}"
                if (filtro in ip.lower() or (expira and filtro in str(expira)) or (comentario and filtro in comentario.lower())):
                    self.listbox_ips_negra.insert(tk.END, texto)
        else:
            for ip, expira, comentario in self._lista_blanca_original:
                texto = f"{ip} | expira: {expira if expira else '-'} | {comentario if comentario else ''}"
                self.listbox_ips.insert(tk.END, texto)
            for ip, expira, comentario in self._lista_negra_original:
                texto = f"{ip} | expira: {expira if expira else '-'} | {comentario if comentario else ''}"
                self.listbox_ips_negra.insert(tk.END, texto)

    def limpiar_filtro_listas(self):
        self.filtro_var.set("")
        self.aplicar_filtro_listas()

    def eliminar_ip_lista_blanca(self):
        seleccion = self.listbox_ips.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una IP para eliminar.")
            return

        ip = self.listbox_ips.get(seleccion)
        confirmado = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Eliminar la IP {ip} de la lista blanca?"
        )
        if confirmado:
            base_datos.eliminar_de_lista_blanca(ip)
            self.listbox_ips.delete(seleccion)
            messagebox.showinfo("Éxito", f"La IP {ip} fue eliminada.")
