param(
    [string]$Port
)

$ErrorActionPreference = 'Stop'

$expressions = @(
    'idle', 'listening', 'thinking', 'happy', 'happy-work', 'excited', 'curious',
    'confused', 'angry', 'surprised', 'sad', 'sleepy', 'dizzy',
    'sleeping', 'waking', 'searching', 'working', 'bored', 'suspicious',
    'proud', 'shy', 'laughing', 'scared', 'celebrate'
)

function Show-Help {
    Write-Host 'Commands: happy | happy-work | thinking | celebrate | idle'
    Write-Host 'Playback: once happy | loop happy | pingpong happy'
    Write-Host 'Type :list for all expressions, :q to quit.'
    Write-Host 'Use 115200 baud; close Settings on the device first.'
}

if (-not $Port) {
    $ports = @(
        Get-CimInstance Win32_SerialPort |
            Where-Object { $_.PNPDeviceID -like 'USB\VID_303A&PID_1001*' }
    )
    if ($ports.Count -ne 1) {
        Write-Error "Expected one StopWatch USB serial port, found $($ports.Count). Reconnect the device or run with -Port COMx."
        exit 1
    }
    $Port = $ports[0].DeviceID
}

$serial = New-Object System.IO.Ports.SerialPort
$serial.PortName = $Port
$serial.BaudRate = 115200
$serial.NewLine = "`n"
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.ReadTimeout = 200
$serial.WriteTimeout = 1000

try {
    $serial.Open()
    Write-Host "StopWatch expression console connected to $Port."
    Show-Help

    while ($true) {
        $command = (Read-Host 'expr').Trim().ToLowerInvariant()
        if ($command -eq ':q' -or $command -eq ':quit') { break }
        if ($command -eq ':help') { Show-Help; continue }
        if ($command -eq ':list') {
            Write-Host ($expressions -join ', ')
            continue
        }
        if (-not $command) { continue }

        $parts = @($command -split '\s+')
        $valid = ($parts.Count -eq 1 -and $expressions -contains $parts[0]) -or
                 ($parts.Count -eq 2 -and @('once', 'loop', 'pingpong') -contains $parts[0] -and
                  $expressions -contains $parts[1])
        if (-not $valid) {
            Write-Host 'Unknown expression. Type :list or :help.'
            continue
        }

        $serial.Write($command + "`n")
        Start-Sleep -Milliseconds 200
        if ($serial.BytesToRead -gt 0) {
            Write-Host ($serial.ReadExisting().TrimEnd())
        } else {
            Write-Host 'Sent. No reply yet; check that the device is running the avatar, not Settings or DOWNLOAD mode.'
        }
    }
} catch {
    Write-Error "Cannot use $Port : $($_.Exception.Message)"
    exit 1
} finally {
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
}
