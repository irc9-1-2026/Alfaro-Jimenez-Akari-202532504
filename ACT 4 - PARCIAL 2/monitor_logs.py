import re
import json
from collections import Counter

# ── Expresiones regulares ──────────────────────────────────────────────────────
# Formato esperado: "2026-06-15 08:15:47 ERROR: descripción del evento"
REGEX_ENTRADA = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+): (.+)"
)
REGEX_DIRECCION_IP = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


# ── Funciones de parseo ────────────────────────────────────────────────────────

def parsear_texto(contenido: str) -> list[dict]:
    """Convierte el texto de un log en una lista de eventos estructurados."""
    registros = []
    for linea in contenido.splitlines():
        coincidencia = REGEX_ENTRADA.match(linea.strip())
        if coincidencia:
            registros.append({
                "timestamp": coincidencia.group(1),
                "nivel":     coincidencia.group(2),
                "mensaje":   coincidencia.group(3),
            })
    return registros


def parsear_log(ruta: str = "servidor.log") -> list[dict]:
    """Lee un archivo de log local y retorna sus eventos parseados."""
    with open(ruta, encoding="utf-8") as archivo:
        return parsear_texto(archivo.read())


# ── Análisis de eventos ────────────────────────────────────────────────────────

def contar_por_nivel(eventos: list[dict]) -> dict:
    """Agrupa y cuenta los eventos según su nivel de severidad."""
    return dict(Counter(ev["nivel"] for ev in eventos))


def detectar_fuerza_bruta(eventos: list[dict], umbral: int = 3) -> list[str]:
    """
    Identifica direcciones IP con múltiples intentos de login fallidos.
    Una IP se considera sospechosa si supera el umbral de intentos.
    """
    ips_detectadas = []

    for ev in eventos:
        es_error_login = (
            ev["nivel"] == "ERROR" and "login fallido" in ev["mensaje"]
        )
        if es_error_login:
            encontrada = REGEX_DIRECCION_IP.search(ev["mensaje"])
            if encontrada:
                ips_detectadas.append(encontrada.group())

    conteo_ips = Counter(ips_detectadas)
    return [ip for ip, intentos in conteo_ips.items() if intentos >= umbral]


# ── Generación del reporte ─────────────────────────────────────────────────────

def generar_reporte(
    ruta_log: str = "servidor.log",
    ruta_salida: str = "reporte.json",
    contenido: str = None,
) -> dict:
    """
    Genera un reporte de seguridad a partir de un log.
    Acepta el contenido directamente (vía SSH) o una ruta de archivo local.
    Si ruta_salida es None, el reporte no se escribe a disco.
    """
    if contenido is not None:
        eventos = parsear_texto(contenido)
    else:
        eventos = parsear_log(ruta_log)

    reporte = {
        "total_eventos":     len(eventos),
        "eventos_por_nivel": contar_por_nivel(eventos),
        "ips_sospechosas":   detectar_fuerza_bruta(eventos),
    }

    if ruta_salida:
        with open(ruta_salida, "w", encoding="utf-8") as salida:
            json.dump(reporte, salida, indent=2, ensure_ascii=False)

    return reporte


# ── Ejecución directa ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    resultado = generar_reporte()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))