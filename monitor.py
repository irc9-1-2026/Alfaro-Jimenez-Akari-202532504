import platform 
import psutil 
import time, os
from datetime import datetime
import urllib.request
import urllib.parse

UMBRAL_DISCO = 90
UMBRAL_RAM = 85
UMBRAL_CPU = 80
INTERVALO = 3  
REPORTAR_CADA_X_CICLOS = 20  

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HOSTNAME = os.getenv('COMPUTERNAME', os.getenv('HOSTNAME', 'Servidor_Local'))

def escribir_log(mensaje):
    fecha_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{fecha_hora}] {mensaje}")

def enviar_telegram(mensaje):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'parse_mode': 'Markdown', 'text': mensaje}
    try:
        data = urllib.parse.urlencode(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=10) as response: pass
    except Exception as e:
        escribir_log(f"Error Telegram: {e}")

if __name__ == "__main__":
    escribir_log(f"Monitor V1 de Consola Activo | Host: {HOSTNAME}")
    contador_ciclos = 0
    
    while True:  
        os.system('cls' if os.name == 'nt' else 'clear')
        contador_ciclos += 1
        
        uso_cpu = int(psutil.cpu_percent(interval=1))
        uso_ram = int(psutil.virtual_memory().percent)
        
        print(f"=== MONITOR DE CONSOLA INDEPENDIENTE ===")
        print(f"Host    : {HOSTNAME}")
        print(f"Sistema : {platform.system()}")
        print(f"CPU     : {uso_cpu}%")
        print(f"RAM     : {uso_ram}%")
        print(f"Ciclos  : {contador_ciclos}/{REPORTAR_CADA_X_CICLOS}")
        
        if contador_ciclos >= REPORTAR_CADA_X_CICLOS:
            reporte = (
                f"📊 *REPORTE DE CONSOLA ({HOSTNAME})*\n"
                f"💻 *CPU:* {uso_cpu}%\n"
                f"🧠 *RAM:* {uso_ram}%\n"
            )
            enviar_telegram(reporte)
            contador_ciclos = 0
            
        time.sleep(INTERVALO)