param([ValidateSet('Start','Stop','Restart','Status')][string]$Action='Status')
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$stopFlag=Join-Path $project '.local\stop-services'
if($Action -in @('Stop','Restart')){
    & (Join-Path $project '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'check_idle.py')
    if($LASTEXITCODE -ne 0){throw 'Service stop deferred because tasks are active'}
    Set-Content -LiteralPath $stopFlag -Value 'Operator requested stop'
    $deadline=(Get-Date).AddSeconds(50)
    do {
        $task=Get-ScheduledTask -TaskName 'LocalPilot Services'
        if($task.State.ToString() -ne 'Running'){break}
        Start-Sleep -Seconds 2
    } while((Get-Date) -lt $deadline)
    if($task.State.ToString() -eq 'Running'){throw 'Services are still stopping; the stop flag remains set'}
}
if($Action -in @('Start','Restart')){
    Remove-Item -LiteralPath $stopFlag -ErrorAction SilentlyContinue
    Start-ScheduledTask -TaskName 'LocalPilot Services'
}
Get-ScheduledTask -TaskName 'LocalPilot Services' | Select-Object TaskName,State
if(Test-Path -LiteralPath (Join-Path $project '.local\service-status.json')){
    Get-Content -LiteralPath (Join-Path $project '.local\service-status.json')
}
