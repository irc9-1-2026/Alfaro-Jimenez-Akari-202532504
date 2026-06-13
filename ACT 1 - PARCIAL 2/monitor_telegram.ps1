# ============================================================
# monitor.ps1 — Monitor de recursos Windows con alertas Telegram
# Uso: .\monitor.ps1
# ============================================================

# ----- Configuración -----
$UmbralDisco = 90
$UmbralRam   = 85
$UmbralCpu   = 80

$Intervalo   = 10
$LogBase     = if ($env:LOG_BASE) { $env:LOG_BASE } else { Join-Path $env:TEMP 'monitor_recursos' }
$EnvFile     = if ($env:ENV_FILE) { $env:ENV_FILE } else { Join-Path $PSScriptRoot '.env' }
$MaxLogs     = 7

# ----- Estado (alertas solo al cambiar de estado, no en cada ciclo) -----
$Script:EstadoDisco = 'OK'
$Script:EstadoRam   = 'OK'
$Script:EstadoCpu   = 'OK'

# Constante para code fences en mensajes Markdown
$CodeFence = '```'

# ----- Logging -----
function Write-MonitorLog {
    param([Parameter(Mandatory)][string]$Mensaje)
    $fechaHora = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $logHoy    = "{0}_{1}.log" -f $LogBase, (Get-Date -Format 'yyyy-MM-dd')
    $linea     = "[$fechaHora] $Mensaje"
    Write-Host $linea
    try {
        Add-Content -Path $logHoy -Value $linea -ErrorAction Stop
    } catch {
        # si no se puede escribir, seguimos solo con consola
    }
}

# ----- Carga segura de .env -----
# No usamos Invoke-Expression. Parseamos línea por línea solo asignaciones CLAVE=VALOR.
function Import-EnvFile {
    if (-not (Test-Path $EnvFile)) { return $false }
    Get-Content $EnvFile | ForEach-Object {
        $linea = $_.Trim()
        if ($linea -match '^\s*#' -or [string]::IsNullOrWhiteSpace($linea)) { return }
        $partes = $linea -split '=', 2
        if ($partes.Length -ne 2) { return }
        $clave = $partes[0].Trim()
        $valor = $partes[1].Trim().Trim("'").Trim('"')
        Set-Item -Path "env:$clave" -Value $valor
    }
    return $true
}

# ----- Rotación de logs -----
function Invoke-LogRotation {
    $logDir    = Split-Path $LogBase -Parent
    $logPrefix = (Split-Path $LogBase -Leaf) + '*.log'
    $umbral    = (Get-Date).AddDays(-$MaxLogs)
    Get-ChildItem -Path $logDir -Filter $logPrefix -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $umbral } |
        Remove-Item -Force -ErrorAction SilentlyContinue
    Write-MonitorLog "Rotación de logs: eliminados registros con más de $MaxLogs días."
}

# ----- Telegram -----
function Send-TelegramAlert {
    param([Parameter(Mandatory)][string]$Mensaje)
    if (-not $env:TELEGRAM_BOT_TOKEN -or -not $env:TELEGRAM_CHAT_ID) {
        return # modo silencioso si no hay credenciales
    }
    $url = "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/sendMessage"
    try {
        $null = Invoke-RestMethod -Method Post -Uri $url -TimeoutSec 10 -Body @{
            chat_id    = $env:TELEGRAM_CHAT_ID
            parse_mode = 'Markdown'
            text       = $Mensaje
        }
    } catch {
        Write-MonitorLog "ERROR enviando alerta a Telegram: $($_.Exception.Message)"
    }
}

# ----- Monitores -----
function Test-DiscoUsage {
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $uso  = [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100)
    Write-MonitorLog "Disco (C:): uso $uso%"

    # NOTA: en Windows NO hacemos limpieza automática del sistema.
    # Solo alertamos; la decisión de limpiar queda en manos del admin.

    if ($uso -gt $UmbralDisco -and $Script:EstadoDisco -eq 'OK') {
        $msg = @"
🚨 *ALERTA DISCO en $env:COMPUTERNAME*
Uso: $uso% (umbral $UmbralDisco%)
"@
        Send-TelegramAlert -Mensaje $msg
        $Script:EstadoDisco = 'ALERTA'
    }
    elseif ($uso -le $UmbralDisco -and $Script:EstadoDisco -eq 'ALERTA') {
        Send-TelegramAlert -Mensaje "✅ Disco recuperado en $env:COMPUTERNAME: $uso%"
        $Script:EstadoDisco = 'OK'
    }
}

function Test-RamUsage {
    $os  = Get-CimInstance Win32_OperatingSystem
    $uso = [math]::Round((1 - ($os.FreePhysicalMemory / $os.TotalVisibleMemorySize)) * 100)
    Write-MonitorLog "RAM: uso $uso%"

    if ($uso -gt $UmbralRam) {
        $procesos = Get-Process |
            Sort-Object -Property WorkingSet -Descending |
            Select-Object -First 5 Id, ProcessName,
                @{ N = 'MB'; E = { [math]::Round($_.WorkingSet / 1MB) } } |
            Format-Table -AutoSize | Out-String

        Write-MonitorLog "RAM supera el $UmbralRam%. Top procesos por memoria:"
        $procesos -split "`r?`n" | Where-Object { $_ } | ForEach-Object {
            Write-MonitorLog "   $_"
        }

        if ($Script:EstadoRam -eq 'OK') {
            $msg = @"
🚨 *ALERTA RAM en $env:COMPUTERNAME*
Uso: $uso% (umbral $UmbralRam%)

$CodeFence
$procesos
$CodeFence
"@
            Send-TelegramAlert -Mensaje $msg
            $Script:EstadoRam = 'ALERTA'
        }
    }
    elseif ($Script:EstadoRam -eq 'ALERTA') {
        Send-TelegramAlert -Mensaje "✅ RAM recuperada en $env:COMPUTERNAME: $uso%"
        $Script:EstadoRam = 'OK'
    }
}

function Test-CpuUsage {
    # Intentamos el contador en inglés y español (Windows localizado)
    $uso = 0
    $contadores = @(
        '\Processor(_Total)\% Processor Time',
        '\Procesador(_Total)\% de tiempo de procesador'
    )
    foreach ($c in $contadores) {
        try {
            $counter = Get-Counter $c -SampleInterval 1 -MaxSamples 2 -ErrorAction Stop
            $uso = [math]::Round(($counter.CounterSamples | Select-Object -Last 1).CookedValue)
            break
        } catch { }
    }
    # Fallback: WMI si Get-Counter falla en ambos idiomas
    if ($uso -eq 0) {
        try {
            $cpu = Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average
            $uso = [math]::Round($cpu.Average)
        } catch { }
    }
    Write-MonitorLog "CPU: uso $uso%"

    if ($uso -gt $UmbralCpu) {
        $procesos = Get-Process |
            Where-Object { $_.CPU -gt 0 } |
            Sort-Object -Property CPU -Descending |
            Select-Object -First 5 Id, ProcessName,
                @{ N = 'CPU(s)'; E = { [math]::Round($_.CPU, 1) } } |
            Format-Table -AutoSize | Out-String

        Write-MonitorLog "CPU supera el $UmbralCpu%. Top procesos por tiempo de CPU:"
        $procesos -split "`r?`n" | Where-Object { $_ } | ForEach-Object {
            Write-MonitorLog "   $_"
        }

        if ($Script:EstadoCpu -eq 'OK') {
            $msg = @"
🚨 *ALERTA CPU en $env:COMPUTERNAME*
Uso: $uso% (umbral $UmbralCpu%)

$CodeFence
$procesos
$CodeFence
"@
            Send-TelegramAlert -Mensaje $msg
            $Script:EstadoCpu = 'ALERTA'
        }
    }
    elseif ($Script:EstadoCpu -eq 'ALERTA') {
        Send-TelegramAlert -Mensaje "✅ CPU recuperada en $env:COMPUTERNAME: $uso%"
        $Script:EstadoCpu = 'OK'
    }
}

# ----- Arranque -----
if (Import-EnvFile) {
    Write-MonitorLog "Variables de entorno cargadas desde $EnvFile"
} else {
    Write-MonitorLog "No se encontró $EnvFile - las alertas de Telegram quedarán desactivadas."
}

Write-MonitorLog '===================================================================='
Write-MonitorLog " Monitor iniciado | PID: $PID | Host: $env:COMPUTERNAME"
Write-MonitorLog " Umbrales -> Disco:$UmbralDisco% | RAM:$UmbralRam% | CPU:$UmbralCpu%"
Write-MonitorLog " Intervalo: ${Intervalo}s"
if ($env:TELEGRAM_BOT_TOKEN -and $env:TELEGRAM_CHAT_ID) {
    Write-MonitorLog " Telegram: configurado (chat $env:TELEGRAM_CHAT_ID)"
} else {
    Write-MonitorLog " Telegram: no configurado"
}
Write-MonitorLog '===================================================================='

# ----- Modo de ejecución única (para CI / Task Scheduler) -----
if ($env:MODO -eq 'once') {
    Write-MonitorLog 'Modo: ejecución única (MODO=once)'
    Test-DiscoUsage
    Test-RamUsage
    Test-CpuUsage
    Write-MonitorLog 'Chequeo único completado. Saliendo.'
    exit 0
}

# Mensaje de arranque (solo en modo loop)
Send-TelegramAlert -Mensaje "🟢 Monitor iniciado en $env:COMPUTERNAME`nVigilando disco/RAM/CPU cada ${Intervalo}s."

# ----- Modo loop -----
$UltimoDia = Get-Date -Format 'yyyy-MM-dd'

try {
    while ($true) {
        $diaActual = Get-Date -Format 'yyyy-MM-dd'
        if ($diaActual -ne $UltimoDia) {
            Write-MonitorLog 'Nuevo día detectado. Ejecutando rotación de logs...'
            Invoke-LogRotation
            $UltimoDia = $diaActual
        }

        Test-DiscoUsage
        Test-RamUsage
        Test-CpuUsage


        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
        $usoDisco = [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100)

        $os = Get-CimInstance Win32_OperatingSystem
        $usoRam = [math]::Round((1 - ($os.FreePhysicalMemory / $os.TotalVisibleMemorySize)) * 100)

        $cpu = Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average
        $usoCpu = [math]::Round($cpu.Average)

        $mensaje = @"
MONITOR $env:COMPUTERNAME

CPU: $usoCpu%
RAM: $usoRam%
DISCO: $usoDisco%

Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"@

        Send-TelegramAlert -Mensaje $mensaje

        Write-MonitorLog "Próxima revisión en $Intervalo segundos."
        Write-MonitorLog '--------------------------------------------------'
        Start-Sleep -Seconds $Intervalo
    }
} finally {
    Write-MonitorLog 'Monitor detenido.'
}
