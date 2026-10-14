param([string]$Preflight)
$ErrorActionPreference = 'Stop'
. $Preflight
$spec = [pscustomobject]@{
    Electron='D:\项目 空间\electron.exe';AppDirectory='D:\项目 空间\app'
    Python='D:\项目 空间\python.exe';PythonExecutables=@('D:\项目 空间\python.exe','C:\Python\python.exe')
    Script='D:\项目 空间\run_companion.py';Version='0.20.8-dev'
}
$created = [datetime]'2026-10-04T09:00:00'
function Proc($Id,$Parent,$Time,$Exe,$Arguments) {
    [pscustomobject]@{Id=$Id;ParentId=$Parent;Created=$Time;ExecutablePath=$Exe;Args=$Arguments}
}
$server=Proc 102 101 $created 'C:\Python\python.exe' @($spec.Python,$spec.Script,'--no-browser')
$wrapper=Proc 101 100 $created.AddSeconds(-1) $spec.Python @($spec.Python,$spec.Script,'--no-browser')
$main=Proc 100 90 $created.AddSeconds(-2) $spec.Electron @($spec.Electron,$spec.AppDirectory)
$health=[pscustomobject]@{app='stopwatch-voice-companion';instance='fixture';pid=102;version=$spec.Version;launch='3adbc13e-5df4-40a1-8dad-3d04ca836947'}
$script:count=0
function Check($Name,$Processes,$Listeners,$Health,$Action,$Reason,$TargetIds=@()) {
    $plan=New-GorkStartupPlan $spec $Processes $Listeners $Health
    if ($plan.Action -ne $Action -or $plan.Reason -ne $Reason -or
        (@($plan.Targets | ForEach-Object {$_.Id}) -join ',') -ne ($TargetIds -join ',')) {
        throw "Case failed: $Name"
    }
    $script:count++
}
Check 'free' @() @() $null 'start' 'free'
Check 'live main without listener' @($main) @() $null 'reuse' 'active-main'
Check 'live current main' @($main,$wrapper,$server) @(102) $health 'reuse' 'active-main'
$oldHealth=$health.PSObject.Copy();$oldHealth.version='0.20.3-dev'
Check 'live old main untouched' @($main,$wrapper,$server) @(102) $oldHealth 'block' 'active-old-main'
Check 'venv orphan' @($wrapper,$server) @(102) $health 'clean' 'owned-orphan' @(102,101)
Check 'direct orphan' @($server) @(102) $health 'clean' 'owned-orphan' @(102)
$reused=Proc 100 90 $created.AddSeconds(5) 'C:\other.exe' @('C:\other.exe')
Check 'former owner PID reused' @($reused,$wrapper,$server) @(102) $health 'clean' 'owned-orphan' @(102,101)
$owner=Proc 100 90 $created.AddSeconds(-2) 'C:\other.exe' @('C:\other.exe')
Check 'external live owner' @($owner,$wrapper,$server) @(102) $health 'block' 'active-owner'
$manual=$health.PSObject.Copy();$manual.launch=''
Check 'independent backend' @($server) @(102) $manual 'reuse' 'external-backend'
$manual.version='0.20.3-dev'
Check 'independent old backend' @($server) @(102) $manual 'block' 'external-old-backend'
$foreign=$server.PSObject.Copy();$foreign.Args=@($spec.Python,($spec.Script+'.backup'),'--no-browser')
Check 'exact path required' @($foreign) @(102) $health 'block' 'foreign-port'
$foreignExe=$server.PSObject.Copy();$foreignExe.ExecutablePath='C:\foreign\python.exe'
Check 'exact executable required' @($foreignExe) @(102) $health 'block' 'foreign-port'
$wrongPid=$health.PSObject.Copy();$wrongPid.pid=999
Check 'health PID required' @($server) @(102) $wrongPid 'block' 'foreign-port'
Check 'unresponsive port preserved' @($server) @(102) $null 'block' 'foreign-port'
Check 'multiple listeners preserved' @($server) @(102,999) $health 'block' 'foreign-port'
Initialize-GorkArgv
$argsParsed=[GorkStartup.NativeArgv]::Parse('"D:\项目 空间\python.exe" "D:\项目 空间\run_companion.py" --no-browser')
if ($argsParsed.Count -ne 3 -or $argsParsed[0] -ne $spec.Python -or $argsParsed[1] -ne $spec.Script) {
    throw 'Windows quoted Unicode argv parsing failed'
}
$script:count++
Write-Output "$script:count startup ownership cases passed"
