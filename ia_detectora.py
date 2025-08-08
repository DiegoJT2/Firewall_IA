import os
import pickle
import time
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from collections import defaultdict
from base_datos import (obtener_registros_entrenamiento)
from datetime import datetime
import config
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest


MODELOS_PATH = {
    "RandomForest": "modelo_rf.pkl",
    "XGBoost": "modelo_xgb.pkl",
    "LightGBM": "modelo_lgbm.pkl",
    "IsolationForest": "modelo_iso.pkl"
}
MIN_DATOS_ENTRENAMIENTO = 30
VENTANA_TIEMPO = 60


class DetectorIA:

    def __init__(self):
        self.modelos = {
            "RandomForest": RandomForestClassifier(n_estimators=100, random_state=42),
            "XGBoost": XGBClassifier(n_estimators=100, random_state=42) if XGBClassifier else None,
            "LightGBM": LGBMClassifier(n_estimators=100, random_state=42) if LGBMClassifier else None,
            "IsolationForest": IsolationForest(n_estimators=100, random_state=42) if IsolationForest else None
        }
        self.label_encoder_pais_compania = LabelEncoder()
        self.label_encoder_protocolo = LabelEncoder()
    # self.label_encoder_proceso = LabelEncoder()
        self.entrenado = False
        self.datos = {k: [] for k in self.modelos.keys()}  # datos por modelo
        self.labels = {k: [] for k in self.modelos.keys()}  # labels por modelo
        self.intentos_por_ip = defaultdict(list)
        self.modelo_actual = config.get_modelo_ia()
        self.clf = self.modelos[self.modelo_actual]
        self._cargar_modelo()
        self.cargar_datos_previos()
        if not self.entrenado:
            self.entrenar_si_es_necesario()

    def obtener_importancia_variables(self):
        """
        Devuelve la importancia de cada variable usada por la IA.
        """
        if not self.entrenado:
            return None
        nombres = [
            "hora", "es_laboral", "intentos", "pais_compania",
            "puerto", "protocolo"
        ]
        if hasattr(self.clf, "feature_importances_"):
            importancias = self.clf.feature_importances_
            return dict(zip(nombres, importancias))
        return None

    def _guardar_modelo(self):
        try:
            path = MODELOS_PATH[self.modelo_actual]
            with open(path, "wb") as f:
                pickle.dump({
                    "clf": self.clf,
                    "encoder_pais_compania": self.label_encoder_pais_compania,
                    "encoder_protocolo": self.label_encoder_protocolo,
                    # "encoder_proceso": self.label_encoder_proceso,
                    "datos": self.datos[self.modelo_actual],
                    "labels": self.labels[self.modelo_actual]
                }, f)
            print(f"[🧠] Modelo IA guardado: {self.modelo_actual}")
        except Exception as e:
            print(f"[❌] Error al guardar modelo: {e}")

    def _cargar_modelo(self):
        path = MODELOS_PATH[self.modelo_actual]
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                    self.clf = data["clf"]
                    self.label_encoder_pais_compania = data["encoder_pais_compania"]
                    self.label_encoder_protocolo = data["encoder_protocolo"]
                    # self.label_encoder_proceso = data["encoder_proceso"]
                    self.datos[self.modelo_actual] = data.get("datos", [])
                    self.labels[self.modelo_actual] = data.get("labels", [])
                    self.entrenado = True
                    print(f"[✅] Modelo IA cargado: {self.modelo_actual}")
            except Exception as e:
                print(f"[⚠️] No se pudo cargar el modelo IA: {e}")

    def registrar_intento(self, ip: str):
        ahora = time.time()
        self.intentos_por_ip[ip].append(ahora)
        self.intentos_por_ip[ip] = [
            t for t in self.intentos_por_ip[ip]
            if ahora - t <= VENTANA_TIEMPO
        ]

    def contar_intentos_recientes(self, ip: str) -> int:
        ahora = time.time()
        intentos = [
            t for t in self.intentos_por_ip[ip]
            if ahora - t <= VENTANA_TIEMPO
        ]
        return len(intentos)

    def registrar_ip(self, hora, pais, compania, puerto, protocolo, confiable: bool, entrenar=True, intentos=1):
        # Limpieza de datos
        pais = pais if isinstance(pais, str) and pais.strip() else "Desconocido"
        compania = compania if isinstance(compania, str) and compania.strip() else "Desconocido"
        protocolo = protocolo if isinstance(protocolo, str) and protocolo.strip() and protocolo.lower() not in ["saliente", "conexión", "conexion"] else "Desconocido"
    # proceso eliminado
        es_laboral = hora.weekday() < 5 and 9 <= hora.hour <= 18
        self.datos[self.modelo_actual].append([
            hora.hour,
            int(es_laboral),
            intentos,
            pais,
            compania,
            puerto,
            protocolo,
            # proceso eliminado
        ])
        self.labels[self.modelo_actual].append(0 if confiable else 1)

        if entrenar:
            self.entrenar_si_es_necesario()

    def entrenar_si_es_necesario(self):
        datos = self.datos[self.modelo_actual]
        labels = self.labels[self.modelo_actual]
        if len(datos) < MIN_DATOS_ENTRENAMIENTO:
            print(
                f"[ℹ️] Aún no hay suficientes datos para entrenar la IA "
                f"({self.modelo_actual})."
            )
            return

        try:
            # Filtrar datos y etiquetas válidas en sincronía
            datos_validos = []
            labels_validos = []
            for d, l in zip(datos, labels):
                if isinstance(d, list) and len(d) == 8:
                    datos_validos.append(d)
                    labels_validos.append(l)
            if len(datos_validos) < MIN_DATOS_ENTRENAMIENTO:
                print(
                    f"[ℹ️] No hay suficientes datos válidos para entrenar la IA "
                    f"({self.modelo_actual})."
                )
                return
            # Codificar variables categóricas robusto
            pais_compania = [f"{d[3]}-{d[4]}" for d in datos_validos]
            protocolos = [d[6] for d in datos_validos]
            # procesos = [d[7] for d in datos_validos]
            self.label_encoder_pais_compania.fit(pais_compania)
            self.label_encoder_protocolo.fit(protocolos)
            # self.label_encoder_proceso.fit(procesos)
            encoded_pais_compania = self.label_encoder_pais_compania.transform(pais_compania)
            encoded_protocolo = self.label_encoder_protocolo.transform(protocolos)
            # encoded_proceso = self.label_encoder_proceso.transform(procesos)

            X = np.array([
                [
                    d[0], d[1], d[2], encoded_pais_compania[i], d[5],
                    encoded_protocolo[i]
                ]
                for i, d in enumerate(datos_validos)
            ])
            y = np.array(labels_validos)

            # Evitar entrenamiento con una sola clase
            if len(set(y)) < 2:
                print(f"[⚠️] No se puede entrenar IA: solo hay una clase en los datos.")
                return

            self.clf = self.modelos[self.modelo_actual]
            self.clf.fit(X, y)
            self.entrenado = True
            self._guardar_modelo()
        except Exception as e:
            print(f"[❌] Error al entrenar IA: {e}")

    def analizar_ip(self, hora, pais, compania, puerto, protocolo, intentos=1):
        """
        Analiza una conexión y retorna True si es sospechosa. Guarda score y probabilidad.
        """
        self.score_ultima_prediccion = None
        self.prob_ultima_prediccion = None
        self.importancia_variables = None
        if not self.entrenado:
            datos = self.datos[self.modelo_actual]
            if len(datos) < MIN_DATOS_ENTRENAMIENTO:
                print(
                    f"[ℹ️] No hay suficientes datos para entrenar la IA "
                    f"({self.modelo_actual})."
                )
                return False

        try:
            es_laboral = hora.weekday() < 5 and 9 <= hora.hour <= 18
            clave = f"{pais}-{compania}"
            # Manejo robusto de valores desconocidos en los encoders
            try:
                cod_pais_compania = self.label_encoder_pais_compania.transform([clave])[0]
            except Exception:
                cod_pais_compania = 0
            try:
                cod_protocolo = self.label_encoder_protocolo.transform([protocolo])[0]
            except Exception:
                cod_protocolo = 0
            # proceso eliminado
            X = np.array([
                [
                    hora.hour, int(es_laboral), intentos, cod_pais_compania,
                    puerto, cod_protocolo
                ]
            ])
            if self.modelo_actual == "IsolationForest":
                pred = self.clf.predict(X)[0]
                # IsolationForest: -1 = anómalo, 1 = normal
                self.score_ultima_prediccion = float(pred)
                self.prob_ultima_prediccion = [None, None]
                self.importancia_variables = None
                return pred == -1  # True = sospechoso
            else:
                pred = self.clf.predict(X)[0]
                # Evitar error si solo hay una clase
                probas = self.clf.predict_proba(X)[0]
                if len(probas) > 1:
                    self.score_ultima_prediccion = float(probas[1])  # probabilidad de ser sospechoso
                else:
                    self.score_ultima_prediccion = float(probas[0])
                self.prob_ultima_prediccion = probas.tolist()
                self.importancia_variables = self.obtener_importancia_variables()
                return bool(pred)  # True = sospechoso
        except Exception as e:
            print(f"[❌] Error al analizar IP con IA: {e}")
            return False

    def cargar_datos_previos(self):
        """
        Carga los registros históricos desde la base de datos y entrena la IA.
        """
        registros = obtener_registros_entrenamiento()
        cargados = 0

        for r in registros:
            try:
                # Orden: ip, pais, compania, fecha_hora, estado, origen, app_origen, puerto, protocolo
                hora = datetime.fromisoformat(r[3])
                pais = r[1] if isinstance(r[1], str) and r[1].strip() else "Desconocido"
                compania = r[2] if isinstance(r[2], str) and r[2].strip() else "Desconocido"
                estado = r[4]
                puerto = r[7] if len(r) > 7 and isinstance(r[7], int) else 0
                protocolo = r[8] if len(r) > 8 and isinstance(r[8], str) and r[8].strip() and r[8].lower() not in ["saliente", "conexión", "conexion"] else "Desconocido"

                es_confiable = estado.lower() == "permitido"
                self.registrar_ip(
                    hora, pais, compania, puerto, protocolo, es_confiable,
                    entrenar=False, intentos=1
                )
                cargados += 1
            except Exception as e:
                print(f"[⚠️] Registro omitido: {e}")

        print(f"[📊] Datos históricos cargados: {cargados}")
        self.entrenar_si_es_necesario()

    def cambiar_modelo(self, nuevo_modelo):
        if nuevo_modelo not in self.modelos:
            print(f"[❌] Modelo IA no soportado: {nuevo_modelo}")
            return
        self.modelo_actual = nuevo_modelo
        self.clf = self.modelos[nuevo_modelo]
        self.entrenado = False
        self._cargar_modelo()
        if not self.entrenado:
            self.entrenar_si_es_necesario()
