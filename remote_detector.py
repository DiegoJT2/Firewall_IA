import psutil
import os
import win32security
from remote_apps import REMOTE_APPS


def ruta_svchost_permitida(ruta):

    RUTAS_SVCHOST_VALIDAS = [
        os.path.expandvars(r"%SystemRoot%\System32\svchost.exe").lower(),
        os.path.expandvars(r"%SystemRoot%\SysWOW64\svchost.exe").lower(),
    ]

    ruta = os.path.normpath(ruta).lower()
    if ruta in [r.lower() for r in RUTAS_SVCHOST_VALIDAS]:
        return True
    if "winsxs" in ruta and ruta.endswith("svchost.exe"):
        return True
    return False


def firmado_por_microsoft(path):
    try:
        sd = win32security.GetFileSecurity(
            path, win32security.OWNER_SECURITY_INFORMATION
        )
        owner_sid = sd.GetSecurityDescriptorOwner()
        name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
        propietario = f"{domain}\\{name}".upper()
        return "MICROSOFT" in propietario
    except Exception as e:
        print(f"[⚠️] No se pudo verificar firma en {path}: {e}")
        return False


def detectar_svchost_sospechosos():
    sospechosos = []
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            if proc.info['name'].lower() == "svchost.exe":
                exe_path = proc.info['exe']
                if not exe_path:
                    continue
                ruta_valida = ruta_svchost_permitida(exe_path)
                firma_valida = firmado_por_microsoft(exe_path)
                if not ruta_valida or not firma_valida:
                    sospechosos.append({
                        "pid": proc.info['pid'],
                        "ruta": exe_path,
                        "ruta_valida": ruta_valida,
                        "firma_valida": firma_valida
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sospechosos


def detectar_herramientas_remotas():
    procesos_remotos = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info.get('name', '').lower()
            for app in REMOTE_APPS:
                if app.lower() in name:
                    procesos_remotos.append({
                        "pid": proc.info['pid'],
                        "name": name,
                        "coincidencia": app
                    })
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procesos_remotos


def ejecutar_analisis():
    print("\n[🕵️‍♂️] Análisis de herramientas remotas:")
    remotos = detectar_herramientas_remotas()
    if remotos:
        for p in remotos:
            print(
                f"  ⚠️ {p['name']} (PID {p['pid']}) - "
                f"Coincidencia: {p['coincidencia']}"
            )
    else:
        print("  ✅ No se detectaron herramientas remotas activas.")

    print("\n[🧪] Análisis de procesos svchost sospechosos:")
    sospechosos = detectar_svchost_sospechosos()
    if sospechosos:
        for s in sospechosos:
            print(f"  ⚠️ svchost.exe sospechoso en PID {s['pid']}:")
            print(f"     Ruta: {s['ruta']}")
            print(f"     Ruta válida: {'✅' if s['ruta_valida'] else '❌'}")
            print(f"     Firma Microsoft: {'✅' if s['firma_valida'] else '❌'}")
    else:
        print("  ✅ Todos los svchost.exe son válidos.")


if __name__ == "__main__":
    ejecutar_analisis()
