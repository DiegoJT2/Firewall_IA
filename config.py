import json
import os

CONFIG_FILE = "config.json"

DEFAULTS = {
    "auto_start": True,
    "minimize_to_tray": True,
    "tema": "dark",
    "modelo_ia": "RandomForest"  # Opciones: RandomForest, XGBoost, LightGBM, IsolationForest
}


def get_modelo_ia():
    config = cargar_config()
    return config.get("modelo_ia", "RandomForest")


def set_modelo_ia(valor: str):
    config = cargar_config()
    config["modelo_ia"] = valor
    guardar_config(config)


def cargar_config():
    if not os.path.exists(CONFIG_FILE):
        guardar_config(DEFAULTS)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def guardar_config(config_dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_dict, f, indent=4)


def get_auto_start():
    config = cargar_config()
    return config.get("auto_start", False)


def set_auto_start(valor: bool):
    config = cargar_config()
    config["auto_start"] = valor
    guardar_config(config)


def get_minimize_to_tray():
    config = cargar_config()
    return config.get("minimize_to_tray", False)


def set_minimize_to_tray(valor: bool):
    config = cargar_config()
    config["minimize_to_tray"] = valor
    guardar_config(config)


def get_tema():
    config = cargar_config()
    return config.get("tema", "dark")


def set_tema(valor: str):
    config = cargar_config()
    config["tema"] = valor
    guardar_config(config)
