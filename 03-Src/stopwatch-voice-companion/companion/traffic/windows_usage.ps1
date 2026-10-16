param([int]$Days = 2)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $usageType = [System.Collections.Generic.IReadOnlyList[Windows.Networking.Connectivity.AttributedNetworkUsage]]
    $states = New-Object Windows.Networking.Connectivity.NetworkUsageStates
    $now = [DateTimeOffset]::Now.ToOffset([TimeSpan]::FromHours(8))
    $today = New-Object DateTimeOffset($now.Year,$now.Month,$now.Day,0,0,0,$now.Offset)
    $rows = New-Object 'System.Collections.Generic.List[object]'
    $errors = New-Object 'System.Collections.Generic.List[object]'
    $profiles = @([Windows.Networking.Connectivity.NetworkInformation]::GetConnectionProfiles())
    foreach ($profile in $profiles) {
        $profileId = [string]$profile.NetworkAdapter.NetworkAdapterId
        $label = [string]$profile.ProfileName
        for ($i=0; $i -lt $Days; $i++) {
            $begin = $today.AddDays(-$i)
            $end = $begin.AddDays(1)
            if ($end -gt $now) { $end = $now }
            try {
                $operation = $profile.GetAttributedNetworkUsageAsync($begin,$end,$states)
                $task = $asTask.MakeGenericMethod($usageType).Invoke($null,@($operation))
                foreach ($usage in $task.GetAwaiter().GetResult()) {
                    $identity = [string]$usage.AttributionId
                    $app = [IO.Path]::GetFileName($identity)
                    if (-not $app) { $app = 'Unattributed' }
                    $sha = [Security.Cryptography.SHA256]::Create()
                    try { $key = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($identity))).Replace('-','').ToLowerInvariant() }
                    finally { $sha.Dispose() }
                    $rows.Add([pscustomobject]@{day=$begin.ToString('yyyy-MM-dd');profile=$profileId;network=$label;
                        app=$app;identity=$key;upload=[long]$usage.BytesSent;download=[long]$usage.BytesReceived})
                }
            } catch {
                $errors.Add([pscustomobject]@{day=$begin.ToString('yyyy-MM-dd');profile=$profileId;error=$_.Exception.GetType().Name})
            }
        }
    }
    [pscustomobject]@{available=$true;captured_at=$now.ToString('o');profiles=$profiles.Count;rows=@($rows.ToArray());errors=@($errors.ToArray())} | ConvertTo-Json -Depth 5 -Compress
} catch {
    [pscustomobject]@{available=$false;error=$_.Exception.GetType().Name;rows=@();errors=@()} | ConvertTo-Json -Compress
}
