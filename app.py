from flask import Flask, render_template, jsonify 
import platform, psutil, os, urllib.request, urllib.parse  # TU CÓDIGO AQUÍ — mismas librerías que en V1 

app = Flask(__name__)

# Variables de configuración de tu código
UMBRAL_RAM = 85
UMBRAL_CPU = 80
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HOSTNAME = os.getenv('COMPUTERNAME', os.getenv('HOSTNAME', 'Servidor_GitLab'))

def enviar_telegram_alerta(recurso, valor, umbral):
    if not BOT_TOKEN or not CHAT_ID: return
    mensaje = f"🚨 *ALERT {recurso} en {HOSTNAME}*\nUso: {valor}% (Umbral: {umbral}%)"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'parse_mode': 'Markdown', 'text': mensaje}
    try:
        data = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=5) as r: pass
    except: pass

# Ruta principal — carga el dashboard HTML 
@app.route("/") 
def index(): 
    return render_template("index.html")

# Ruta de datos — devuelve JSON al dashboard cada 3 segundos
@app.route("/datos")
def datos():
    # Capturas idénticas a tu lógica y V1
    sistema_operativo = platform.system()
    uso_cpu = int(psutil.cpu_percent(interval=None))
    uso_ram = int(psutil.virtual_memory().percent)
    uso_disco = int(psutil.disk_usage('/').percent)

    # Disparadores de Telegram de tu código
    if uso_cpu > UMBRAL_CPU: enviar_telegram_alerta("CPU", uso_cpu, UMBRAL_CPU)
    if uso_ram > UMBRAL_RAM: enviar_telegram_alerta("RAM", uso_ram, UMBRAL_RAM)

    # Procesos en formato Dict
    procesos = []
    for proc in psutil.process_iter():
        try:
            p_info = proc.as_dict(attrs=['pid', 'name', 'cpu_percent'])
            if p_info['cpu_percent'] is None: p_info['cpu_percent'] = 0.0
            procesos.append(p_info)
        except: pass
    top_cinco = sorted(procesos, key=lambda p: p['cpu_percent'], reverse=True)[:5]

    return jsonify({
        "os":      sistema_operativo,  
        "cpu":     uso_cpu,            
        "memoria": uso_ram,           
        "disco":   uso_disco,         
        "procesos": top_cinco         
    })

if __name__ == "__main__":
    app.run(debug=True)