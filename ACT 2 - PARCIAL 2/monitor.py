import os
import sys
import time
from datetime import datetime
import urllib.request
import urllib.parse
import json
import psutil
from dotenv import load_dotenv

# ----- Configuración -----
UMBRAL_DISCO = 90
UMBRAL_RAM = 85
UMBRAL_CPU = 80
INTERVALO = 5
REPORTAR_CADA_X_CICLOS = 12  # 12 ciclos * 5s = Cada 60 segundos (1 minuto) enviar reporte

# Intentar cargar archivo .env local
if os.path.exists('.env'):
    load_dotenv('.env')
    CONFIG_ENV = True
else:
    CONFIG_ENV = False

# Variables de entorno para Telegram
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HOSTNAME = os.getenv('COMPUTERNAME', os.getenv('HOSTNAME', 'Servidor_GitLab'))
MODO = os.getenv('MODO', 'loop')

# Estado de las alertas
ESTADO = {
    'disco': 'OK',
    'ram': 'OK',
    'cpu': 'OK'
}

# ----- Funciones de Soporte -----

def escribir_log(mensaje):
    fecha_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{fecha_hora}] {mensaje}")

def enviar_telegram(mensaje):
    if not BOT_TOKEN or not CHAT_ID:
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'parse_mode': 'Markdown',
        'text': mensaje
    }
    
    try:
        data = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=10) as response:
            pass
    except Exception as e:
        escribir_log(f"ERROR: Fallo al enviar a Telegram: {e}")

def obtener_reporte_actual():
    uso_disco = int(psutil.disk_usage('/').percent)
    uso_ram = int(psutil.virtual_memory().percent)
    uso_cpu = int(psutil.cpu_percent(interval=0.5))
    
    reporte = (
        f"📊 *REPORTE PERIODICO ({HOSTNAME})*\n"
        f"----------------------------------\n"
        f"💾 *Disco (C:):* {uso_disco}%\n"
        f"🧠 *Memoria RAM:* {uso_ram}%\n"
        f"⚙️ *Uso de CPU:* {uso_cpu}%\n"
    )
    return reporte, uso_disco, uso_ram, uso_cpu

# ----- Monitores -----

def checar_recursos(ciclo_actual):
    reporte, uso_disco, uso_ram, uso_cpu = obtener_reporte_actual()
    
    # Mostrar siempre en la terminal de VS Code
    print(f"[MONITOR] Ciclo: {ciclo_actual}/{REPORTAR_CADA_X_CICLOS} | CPU: {uso_cpu}% | RAM: {uso_ram}% | Disco: {uso_disco}%")
    
    # ENVIAR REPORTE PERIÓDICO A TELEGRAM
    if ciclo_actual >= REPORTAR_CADA_X_CICLOS:
        enviar_telegram(reporte)
        return True # Indica que se debe reiniciar el contador de ciclos

    # 1. Validar Disco (Alertas críticas)
    if uso_disco > UMBRAL_DISCO and ESTADO['disco'] == 'OK':
        enviar_telegram(f"🚨 *ALERT DISCO en {HOSTNAME}*\nUso: {uso_disco}% (Umbral: {UMBRAL_DISCO}%)")
        ESTADO['disco'] = 'ALERT'
    elif uso_disco <= UMBRAL_DISCO and ESTADO['disco'] == 'ALERT':
        enviar_telegram(f"✅ *OK:* Disco recuperado en {HOSTNAME}: {uso_disco}%")
        ESTADO['disco'] = 'OK'
        
    # 2. Validar RAM
    if uso_ram > UMBRAL_RAM:
        procesos = []
        for proc in sorted(psutil.process_iter(['pid', 'name', 'memory_info']), 
                           key=lambda p: p.info['memory_info'].rss if p.info['memory_info'] else 0, 
                           reverse=True)[:5]:
            mb = int(proc.info['memory_info'].rss / 1024 / 1024)
            procesos.append(f"{proc.info['pid']} - {proc.info['name']} - {mb}MB")
        top_str = "\n".join(procesos)
        
        if ESTADO['ram'] == 'OK':
            enviar_telegram(f"🚨 *ALERT RAM en {HOSTNAME}*\nUso: {uso_ram}%\n\n```\n{top_str}\n```")
            ESTADO['ram'] = 'ALERT'
    elif uso_ram <= UMBRAL_RAM and ESTADO['ram'] == 'ALERT':
        enviar_telegram(f"✅ *OK:* RAM recuperada en {HOSTNAME}: {uso_ram}%")
        ESTADO['ram'] = 'OK'

    # 3. Validar CPU
    if uso_cpu > UMBRAL_CPU:
        procesos = []
        for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']), 
                           key=lambda p: p.info['cpu_percent'] if p.info['cpu_percent'] else 0, 
                           reverse=True)[:5]:
            procesos.append(f"{proc.info['pid']} - {proc.info['name']} - {proc.info['cpu_percent']}%")
        top_str = "\n".join(procesos)
        
        if ESTADO['cpu'] == 'OK':
            enviar_telegram(f"🚨 *ALERT CPU en {HOSTNAME}*\nUso: {uso_cpu}%\n\n```\n{top_str}\n```")
            ESTADO['cpu'] = 'ALERT'
    elif uso_cpu <= UMBRAL_CPU and ESTADO['cpu'] == 'ALERT':
        enviar_telegram(f"✅ *OK:* CPU recuperada en {HOSTNAME}: {uso_cpu}%")
        ESTADO['cpu'] = 'OK'
        
    return False

# ----- Inicialización -----

print("\n")
if CONFIG_ENV:
    escribir_log("Archivo .env detectado correctamente.")
else:
    escribir_log("AVISO: No se encontro el archivo .env - Las alertas estan desactivadas.")

escribir_log("====================================================")
escribir_log(f"Monitor Python Activo | Host: {HOSTNAME}")
escribir_log(f"Umbrales -> Disco: {UMBRAL_DISCO}% | RAM: {UMBRAL_RAM}% | CPU: {UMBRAL_CPU}%")
escribir_log(f"Reporte programado cada: {REPORTAR_CADA_X_CICLOS * INTERVALO} segundos")
escribir_log("====================================================")

reporte_inicial, _, _, _ = obtener_reporte_actual()
mensaje_inicio = (
    f"🟢 *Monitor iniciado con éxito en {HOSTNAME}*\n\n"
    f"{reporte_inicial}\n"
    f"Recibirás un reporte automático cada {REPORTAR_CADA_X_CICLOS * INTERVALO}s o ante emergencias."
)
enviar_telegram(mensaje_inicio)

if MODO == 'once':
    checar_recursos(REPORTAR_CADA_X_CICLOS)
    sys.exit(0)

contador_ciclos = 0

try:
    while True:
        contador_ciclos += 1
        se_envio_reporte = checar_recursos(contador_ciclos)
        
        if se_envio_reporte:
            contador_ciclos = 0 # Reiniciar contador tras enviar reporte periódico
            
        time.sleep(INTERVALO)
except KeyboardInterrupt:
    escribir_log("Monitor detenido por el usuario.")