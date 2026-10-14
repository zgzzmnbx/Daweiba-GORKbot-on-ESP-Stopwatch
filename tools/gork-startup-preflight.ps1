param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [ValidateRange(1, 65535)][int]$Port = 8766,
    [switch]$InspectOnly
)

$ErrorActionPreference = 'Stop'
# Keep the launcher's existing custom-port environment setting consistent with Electron.
if (-not $PSBoundParameters.ContainsKey('Port') -and $env:GORK_BACKEND_PORT) {
    $configuredPort = 0
    if (-not [int]::TryParse($env:GORK_BACKEND_PORT, [ref]$configuredPort) -or
        $configuredPort -lt 1024 -or $configuredPort -gt 65535) {
        Write-Host 'Gork 自定义端口无效，已停止启动。'; exit 1
    }
    $Port = $configuredPort
}

# Parse Windows argv without evaluating command text or accepting path substrings.
function Initialize-GorkArgv {
    if ('GorkStartup.NativeArgv' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace GorkStartup {
  public static class NativeArgv {
    [DllImport("shell32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern IntPtr CommandLineToArgvW(string text, out int count);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr pointer);
    public static string[] Parse(string text) {
      if (String.IsNullOrWhiteSpace(text)) return new string[0];
      int count; IntPtr pointer=CommandLineToArgvW(text, out count);
      if (pointer==IntPtr.Zero) throw new InvalidOperationException("Cannot read process arguments");
      try {
        var args=new string[count];
        for(int i=0;i<count;i++) args[i]=Marshal.PtrToStringUni(Marshal.ReadIntPtr(pointer,i*IntPtr.Size));
        return args;
      } finally { LocalFree(pointer); }
    }
  }
}
'@
}

function Test-GorkBackendProcess($Process, $Spec) {
    return ($null -ne $Process -and @($Process.Args).Count -ge 3 -and
        $Spec.PythonExecutables -contains $Process.ExecutablePath -and
        $Process.Args[0] -eq $Spec.Python -and $Process.Args[1] -eq $Spec.Script -and
        $Process.Args -contains '--no-browser')
}

function New-GorkStartupPlan($Spec, $Processes, $ListenerIds, $Health) {
    $listeners = @($ListenerIds | Select-Object -Unique)
    $mains = @($Processes | Where-Object {
        $_.ExecutablePath -eq $Spec.Electron -and @($_.Args).Count -ge 2 -and
        $_.Args[1] -eq $Spec.AppDirectory -and -not ($_.Args -match '^--type=')
    })
    $result = [ordered]@{ Action = 'start'; Reason = 'free'; Targets = @() }
    if ($listeners.Count -gt 1) {
        $result.Action = 'block'; $result.Reason = 'foreign-port'; return [pscustomobject]$result
    }
    $server = $null
    if ($listeners.Count -eq 1) {
        $server = $Processes | Where-Object { $_.Id -eq $listeners[0] } | Select-Object -First 1
        if (-not (Test-GorkBackendProcess $server $Spec) -or $null -eq $Health -or
            $Health.app -ne 'stopwatch-voice-companion' -or -not $Health.instance -or
            $Health.pid -ne $server.Id) {
            $result.Action = 'block'; $result.Reason = 'foreign-port'; return [pscustomobject]$result
        }
    }
    if ($mains.Count -gt 0) {
        $result.Action = 'reuse'; $result.Reason = 'active-main'
        if ($null -ne $Health -and $Health.version -ne $Spec.Version) {
            $result.Action = 'block'; $result.Reason = 'active-old-main'
        }
        return [pscustomobject]$result
    }
    if ($null -eq $server) { return [pscustomobject]$result }

    # An independently started server is preserved. Electron sets a UUID launch token.
    $launchGuid = [guid]::Empty
    if (-not [guid]::TryParse([string]$Health.launch, [ref]$launchGuid) -or $launchGuid -eq [guid]::Empty) {
        $result.Action = 'reuse'; $result.Reason = 'external-backend'
        if ($Health.version -ne $Spec.Version) { $result.Action = 'block'; $result.Reason = 'external-old-backend' }
        return [pscustomobject]$result
    }
    $targets = @($server)
    $ancestor = $server
    # Windows venv Python may have one wrapper. An existing parent is never assumed dead.
    for ($depth = 0; $depth -lt 2; $depth++) {
        $parent = $Processes | Where-Object { $_.Id -eq $ancestor.ParentId } | Select-Object -First 1
        if ($null -eq $parent -or $parent.Created -gt $ancestor.Created) {
            $result.Action = 'clean'; $result.Reason = 'owned-orphan'; $result.Targets = $targets
            return [pscustomobject]$result
        }
        if ($depth -eq 0 -and (Test-GorkBackendProcess $parent $Spec)) {
            $targets += $parent; $ancestor = $parent; continue
        }
        $result.Action = 'block'; $result.Reason = 'active-owner'; return [pscustomobject]$result
    }
    $result.Action = 'block'; $result.Reason = 'unverified-owner'; return [pscustomobject]$result
}

function Get-GorkProcesses {
    return @(Get-CimInstance Win32_Process | ForEach-Object {
        [pscustomobject]@{
            Id = [int]$_.ProcessId; ParentId = [int]$_.ParentProcessId
            Created = $_.CreationDate; ExecutablePath = $_.ExecutablePath
            CommandLine = $_.CommandLine; Args = [GorkStartup.NativeArgv]::Parse($_.CommandLine)
        }
    })
}

function Get-GorkListeners([int]$ListenPort) {
    return @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object {
        $_.LocalPort -eq $ListenPort
    } | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Get-GorkHealth([int]$ListenPort) {
    try { return Invoke-RestMethod -Uri "http://127.0.0.1:$ListenPort/api/health" -TimeoutSec 3 }
    catch { return $null }
}

function Get-GorkStartupPlan($Spec, [int]$ListenPort) {
    $listeners = @(Get-GorkListeners $ListenPort)
    $health = $null
    if ($listeners.Count -gt 0) { $health = Get-GorkHealth $ListenPort }
    return New-GorkStartupPlan $Spec (Get-GorkProcesses) $listeners $health
}

function Write-GorkStartupRecord($Root, $Plan, $Cleaned) {
    $directory = Join-Path $Root 'Codex-Temp\gork-startup'
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $record = [ordered]@{ version = 1; time = [DateTimeOffset]::Now.ToString('o'); action = $Plan.Action;
        reason = $Plan.Reason; cleaned_pids = @($Cleaned) }
    $record | ConvertTo-Json -Depth 3 |
        Set-Content -LiteralPath (Join-Path $directory 'preflight-last.json') -Encoding UTF8
    $record | ConvertTo-Json -Depth 3 -Compress |
        Add-Content -LiteralPath (Join-Path $directory 'preflight-history.jsonl') -Encoding UTF8
}

function Invoke-GorkStartupPreflight {
    $root = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd('\')
    $appDirectory = Join-Path $root '03-Src\gork-desktop'
    $python = Join-Path $root 'Codex-Temp\.venv-companion\Scripts\python.exe'
    $pythonExecutables = @($python)
    $venvConfig = Join-Path $root 'Codex-Temp\.venv-companion\pyvenv.cfg'
    if (Test-Path -LiteralPath $venvConfig) {
        foreach ($line in (Get-Content -LiteralPath $venvConfig)) {
            if ($line -match '^executable\s*=\s*(.+)$') { $pythonExecutables += $Matches[1].Trim() }
        }
    }
    $spec = [pscustomobject]@{
        AppDirectory = $appDirectory; Electron = Join-Path $appDirectory 'node_modules\electron\dist\electron.exe'
        Python = $python; PythonExecutables = $pythonExecutables
        Script = Join-Path $root '03-Src\stopwatch-voice-companion\run_companion.py'
        Version = (Get-Content -LiteralPath (Join-Path $appDirectory 'package.json') -Raw | ConvertFrom-Json).version
    }
    Initialize-GorkArgv
    # Serialize recovery by project path. No global service or Bluetooth state is changed.
    $digest = [System.Security.Cryptography.SHA256]::Create()
    try { $name = [BitConverter]::ToString($digest.ComputeHash([Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))).Replace('-', '') }
    finally { $digest.Dispose() }
    $mutex = New-Object Threading.Mutex($false, "Local\GorkStartup-$name")
    $acquired = $false
    try {
        try { $acquired = $mutex.WaitOne(10000) } catch [Threading.AbandonedMutexException] { $acquired = $true }
        if (-not $acquired) { throw 'Startup check is already running' }
        $plan = Get-GorkStartupPlan $spec $Port
        if ($InspectOnly) { Write-Host ($plan | Select-Object Action, Reason | ConvertTo-Json -Compress); return 0 }
        $cleaned = @()
        if ($plan.Action -eq 'clean') {
            # Recheck the full ownership decision immediately before modifying processes.
            $fresh = Get-GorkStartupPlan $spec $Port
            if ($fresh.Action -ne 'clean' -or @($fresh.Targets).Count -ne @($plan.Targets).Count) {
                throw 'Process ownership changed; no cleanup performed'
            }
            for ($index = 0; $index -lt $plan.Targets.Count; $index++) {
                $old = $plan.Targets[$index]; $current = $fresh.Targets[$index]
                if ($old.Id -ne $current.Id -or $old.Created -ne $current.Created -or
                    $old.CommandLine -ne $current.CommandLine -or $old.ExecutablePath -ne $current.ExecutablePath) {
                    throw 'Process identity changed; no cleanup performed'
                }
            }
            foreach ($target in $plan.Targets) {
                $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($target.Id)"
                if ($null -eq $current) { continue }
                if ($current.CreationDate -ne $target.Created -or $current.ExecutablePath -ne $target.ExecutablePath -or
                    $current.CommandLine -ne $target.CommandLine) { throw 'Process identity changed; cleanup stopped' }
                $handle = Get-Process -Id $target.Id -ErrorAction Stop
                if ([Math]::Abs(($handle.StartTime - $target.Created).TotalMilliseconds) -gt 1) {
                    throw 'Process identity changed; cleanup stopped'
                }
                Stop-Process -InputObject $handle -ErrorAction Stop
                $cleaned += $target.Id
                if (-not $handle.WaitForExit(2000)) { throw 'Process did not exit after cleanup' }
            }
            for ($attempt = 0; $attempt -lt 20; $attempt++) {
                if (@(Get-GorkListeners $Port).Count -eq 0) { break }
                Start-Sleep -Milliseconds 100
            }
            if (@(Get-GorkListeners $Port).Count -gt 0) { throw 'Port is still occupied after cleanup' }
            Write-Host 'Gork 已清理本项目的孤立后台，正在重新启动。'
        }
        Write-GorkStartupRecord $root $plan $cleaned
        if ($plan.Action -eq 'block') {
            switch ($plan.Reason) {
                'active-old-main' { Write-Host '旧版 Gork 仍在运行，请右击系统托盘 Gork → 退出，再打开此快捷方式。' }
                'external-old-backend' { Write-Host '本项目的独立旧后台仍在运行，请先从它的启动终端退出，再打开 Gork。' }
                'active-owner' { Write-Host '后台的启动进程仍在运行，已保留。请先退出对应 Gork 或后台启动程序。' }
                default { Write-Host "$Port 端口被其他程序或无法确认归属的后台占用，已保留；请关闭该程序后重试。" }
            }
            return 1
        }
        if ($plan.Reason -eq 'active-main') { Write-Host 'Gork 已在运行，将显示现有窗口。' }
        return 0
    } finally {
        if ($acquired) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

# Dot-sourcing exposes only the decision functions for verification.
if ($MyInvocation.InvocationName -ne '.') {
    try { exit (Invoke-GorkStartupPreflight) }
    catch { Write-Host 'Gork 启动检查未完成，已停止启动；请稍后重试或检查本项目的后台进程。'; exit 1 }
}
