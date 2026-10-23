# Run once elevated. Recurring AI services use the ordinary signed-in user.
param([Parameter(Mandatory=$true)][string]$UserSid)
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$local=Join-Path $project '.local'
$windowsPowerShell=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
try {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=New-Object Security.Principal.WindowsPrincipal($identity)
    if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){ throw 'Administrator rights required for VM startup configuration' }
    $user=New-Object Security.Principal.SecurityIdentifier($UserSid)
    $null=$user.Translate([Security.Principal.NTAccount])
    Import-Module Hyper-V
    $created=Get-Content -LiteralPath (Join-Path $local 'vm-created.json') -Raw | ConvertFrom-Json
    if($created.Name -ne 'LocalPilot'){throw 'Unexpected private VM identity record'}
    $expectedId=[guid]$created.Id
    $vm=Get-VM -Id $expectedId
    if($vm.Name -ne 'LocalPilot'){throw 'VM identity mismatch'}
    $backup=Join-Path $local 'startup-before.json'
    if(-not (Test-Path -LiteralPath $backup)){
        @{VMId=$vm.Id.ToString();AutomaticStartAction=$vm.AutomaticStartAction.ToString();AutomaticStopAction=$vm.AutomaticStopAction.ToString();AutomaticStartDelay=$vm.AutomaticStartDelay} | ConvertTo-Json | Set-Content -LiteralPath $backup
    }
    $destination=Join-Path $env:ProgramData 'LocalPilot'
    if(Test-Path -LiteralPath $destination){
        $existing=Get-Acl -LiteralPath $destination
        $owner=(New-Object Security.Principal.NTAccount($existing.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
        if($owner -notin @('S-1-5-18','S-1-5-32-544')){throw 'Existing system folder has an unexpected owner'}
    } else {New-Item -ItemType Directory -Path $destination | Out-Null}
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $administrators=New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
    $acl.SetOwner($administrators)
    $acl.SetAccessRuleProtection($true,$false)
    foreach($entry in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('S-1-5-32-545','ReadAndExecute'))){
        $sid=New-Object Security.Principal.SecurityIdentifier($entry[0])
        $rule=New-Object Security.AccessControl.FileSystemAccessRule($sid,$entry[1],'ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $destination -AclObject $acl
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'discover_vm.ps1') -Destination (Join-Path $destination 'discover_vm.ps1') -Force
    $discoveryAction=New-ScheduledTaskAction -Execute $windowsPowerShell -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $destination 'discover_vm.ps1')+'" -ExpectedId '+$expectedId.ToString())
    $repeat=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
    $discoverySettings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds 45)
    $system=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName 'LocalPilot VM Address' -Action $discoveryAction -Trigger @((New-ScheduledTaskTrigger -AtStartup),$repeat) -Settings $discoverySettings -Principal $system -Description 'Publish only the pinned LocalPilot VM network address. Executes a protected system script.' -Force | Out-Null
    $startAction=New-ScheduledTaskAction -Execute $windowsPowerShell -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $destination 'discover_vm.ps1')+'" -ExpectedId '+$expectedId.ToString()+' -StartIfStopped')
    $startSettings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
    Register-ScheduledTask -TaskName 'LocalPilot VM Start' -Action $startAction -Trigger (New-ScheduledTaskTrigger -AtStartup) -Settings $startSettings -Principal $system -Description 'Start only the pinned LocalPilot VM at Windows startup. Does not change any other VM.' -Force | Out-Null

    $pythonw=Join-Path $project '.venv\Scripts\pythonw.exe'
    $worker=Join-Path $PSScriptRoot 'service_supervisor.py'
    $action=New-ScheduledTaskAction -Execute $pythonw -Argument ('"'+$worker+'"') -WorkingDirectory $project
    $logon=New-ScheduledTaskTrigger -AtLogOn -User $UserSid
    $settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    $ordinaryUser=New-ScheduledTaskPrincipal -UserId $UserSid -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName 'LocalPilot Services' -Action $action -Trigger $logon -Settings $settings -Principal $ordinaryUser -Description 'Run private LocalPilot services after sign-in, without stored passwords or administrator privileges.' -Force | Out-Null
    & (Join-Path $destination 'discover_vm.ps1') -ExpectedId $expectedId
    if($LASTEXITCODE -and $LASTEXITCODE -ne 0){throw 'Initial discovery failed'}
    Remove-Item -LiteralPath (Join-Path $local 'logs\startup-install-error.txt') -ErrorAction SilentlyContinue
    @{Installed=$true;VMId=$expectedId.ToString();UserSid=$UserSid;Time=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $local 'startup-installed.json')
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $local 'logs\startup-install-error.txt')
    exit 1
}
