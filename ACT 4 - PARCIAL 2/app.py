import os
import paramiko
from flask import Flask, render_template, request, jsonify

from monitor_logs import generar_reporte
from ssh_logs import leer_log_remoto

# python-dotenv es opcional; si no está instalado, el formulario
# simplemente inicia vacío sin lanzar error.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)


@app.route("/")
def index():
    """Renderiza el formulario principal con valores precargados desde .env."""
    valores_iniciales = {
        "host":        os.getenv("LOG_HOST", ""),
        "usuario":     os.getenv("LOG_USER", ""),
        "ruta_remota": os.getenv("LOG_PATH", "/var/log/auth.log"),
    }
    return render_template("index.html", **valores_iniciales)


@app.route("/analizar", methods=["POST"])
def analizar():
    """
    Recibe credenciales SSH vía JSON, se conecta al servidor remoto,
    lee el log indicado y devuelve un reporte de seguridad en formato JSON.
    """
    datos = request.get_json(silent=True) or {}

    host        = datos.get("host", "").strip()
    usuario     = datos.get("usuario", "").strip()
    password    = datos.get("password", "")
    ruta_remota = datos.get("ruta_remota", "").strip()

    if not all([host, usuario, password, ruta_remota]):
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    try:
        contenido = leer_log_remoto(host, usuario, password, ruta_remota)
    except paramiko.AuthenticationException:
        return jsonify({"error": "Credenciales incorrectas. Verifica usuario y contraseña."}), 401
    except Exception as exc:
        return jsonify({"error": f"No se pudo obtener el log: {exc}"}), 500

    # ruta_salida=None → el reporte se devuelve en memoria, sin escribir a disco
    reporte = generar_reporte(contenido=contenido, ruta_salida=None)
    return jsonify(reporte)


if __name__ == "__main__":
    app.run(debug=True)