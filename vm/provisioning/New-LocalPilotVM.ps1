param([switch]$InspectOnly)
$ErrorActionPreference = 'Stop'
$project = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$state = Join-Path $project '.local'
$log = Join-Path $state 'logs\hyperv-setup.log'
Start-Transcript -Path $log -Append
try {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this script as Administrator.' }
    Import-Module Hyper-V
    $before = @(Get-VM | Select-Object Name,Id,State,Generation,Path)
    $before | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $state 'hyperv-before.json')
    $before | Format-Table -AutoSize
    Get-VMSwitch | Select-Object Name,SwitchType | Format-Table -AutoSize
    if ($InspectOnly) { exit 0 }
    $name = 'LocalPilot'
    if (Get-VM -Name $name -ErrorAction SilentlyContinue) { throw 'LocalPilot VM already exists. Refusing to overwrite it.' }
    $switch = Get-VMSwitch -Name 'Default Switch' -ErrorAction Stop
    $vmRoot = Join-Path $state 'hyperv'
    $disk = Join-Path $vmRoot 'LocalPilot.vhdx'
    if (Test-Path -LiteralPath $disk) { throw 'Target disk already exists. Refusing to overwrite it.' }
    New-Item -ItemType Directory -Path $vmRoot -Force | Out-Null
    $vm = New-VM -Name $name -Generation 2 -MemoryStartupBytes 6GB -NewVHDPath $disk -NewVHDSizeBytes 60GB -Path $vmRoot -SwitchName $switch.Name
    Set-VMProcessor -VM $vm -Count 4
    Set-VMMemory -VM $vm -DynamicMemoryEnabled $false
    Set-VM -VM $vm -AutomaticStartAction Nothing -AutomaticStopAction ShutDown -CheckpointType Standard
    Set-VMFirmware -VM $vm -EnableSecureBoot On -SecureBootTemplate MicrosoftUEFICertificateAuthority
    Set-VM -VM $vm -Notes 'LocalPilot isolated Linux workstation. Created independently of existing VMs. No host shared folders configured.'
    Get-VM -Name $name | Select-Object Name,Id,State,Generation,ProcessorCount,MemoryStartup,Path | ConvertTo-Json | Set-Content (Join-Path $state 'vm-created.json')
    Get-VM -Name $name | Select-Object Name,State,Generation,ProcessorCount,MemoryStartup,Path | Format-List
    'Created new LocalPilot VM. Existing VMs were not modified.'
} catch {
    $_ | Out-String | Set-Content (Join-Path $state 'logs\hyperv-error.txt')
    Write-Error $_
    exit 1
} finally { Stop-Transcript }
