param([switch]$Restart)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
if(Test-Path -LiteralPath (Join-Path $root '.local\startup-installed.json')) {
    $action=if($Restart){'Restart'}else{'Start'}
    & (Join-Path $PSScriptRoot 'manage_services.ps1') -Action $action
    exit
}
$log=Join-Path $root '.local\logs\backend-error.log'
if($Restart -and (Test-Path -LiteralPath $log)) {
    $matchesInLog=Select-String -LiteralPath $log -Pattern 'Started server process \[(\d+)\]'
    if($matchesInLog){
        $serverId=[int]$matchesInLog[-1].Matches[0].Groups[1].Value
        $process=Get-CimInstance Win32_Process -Filter "ProcessId=$serverId" -ErrorAction SilentlyContinue
        if($process -and $process.CommandLine -match 'uvicorn.+backend\.main:app'){
            Stop-Process -Id $serverId
        }
    }
}
$process=Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') -WindowStyle Hidden -WorkingDirectory $root -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8765','--no-access-log') -RedirectStandardOutput (Join-Path $root '.local\logs\backend-out.log') -RedirectStandardError $log -PassThru
$process.Id | Set-Content (Join-Path $root '.local\backend.pid')
Write-Output "LocalPilot backend launched: $($process.Id)"
