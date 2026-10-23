# Run elevated to remove only LocalPilot's three startup tasks. VM and data remain.
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot 'manage_services.ps1') -Action Stop
foreach($taskName in @('LocalPilot Services','LocalPilot VM Start','LocalPilot VM Address')){
    if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
}
Remove-Item -LiteralPath (Join-Path $project '.local\startup-installed.json') -ErrorAction SilentlyContinue
'LocalPilot startup tasks removed. VM, task history, credentials, Ollama, and protected address files retained.'
