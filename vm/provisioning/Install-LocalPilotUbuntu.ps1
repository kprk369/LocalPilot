$ErrorActionPreference='Stop'
$project=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$local=Join-Path $project '.local'
Start-Transcript -Path (Join-Path $local 'logs\ubuntu-install.log') -Append
try {
    Import-Module Hyper-V
    $vm=Get-VM -Name 'LocalPilot'
    $created=Get-Content (Join-Path $local 'vm-created.json') -Raw | ConvertFrom-Json
    if ($vm.Id.ToString() -ne $created.Id) { throw 'VM identity does not match the newly created LocalPilot VM.' }
    if ($vm.State -ne 'Off') { throw 'VM must be powered off before initial installation.' }
    $disk=@(Get-VMHardDiskDrive -VM $vm)
    if ($disk.Count -ne 1 -or $disk[0].Path -ne (Join-Path $local 'hyperv\LocalPilot.vhdx')) { throw 'Unexpected disk attached; installation stopped.' }
    if ((Get-VHD -Path $disk[0].Path).FileSize -gt 10MB) { throw 'Disk is no longer empty; refusing automated installation.' }
    $media=Join-Path $local 'downloads\localpilot-ubuntu-serial-autoinstall.iso'
    if (-not (Test-Path -LiteralPath $media)) { throw 'Installer media missing.' }
    $dvd=Add-VMDvdDrive -VM $vm -Path $media -Passthru
    Set-VMComPort -VMName 'LocalPilot' -Number 1 -Path '\\.\pipe\LocalPilotConsole'
    Set-VMFirmware -VM $vm -BootOrder @($dvd, $disk[0])
    Start-VM -VM $vm
    $deadline=(Get-Date).AddMinutes(50)
    while ((Get-Date) -lt $deadline) {
        $vm=Get-VM -Name 'LocalPilot'
        @{Time=(Get-Date).ToString('o'); State=$vm.State.ToString(); Status=$vm.Status; IPs=@(Get-VMNetworkAdapter -VM $vm | ForEach-Object IPAddresses); Uptime=$vm.Uptime.ToString()} | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $local 'install-status.json')
        if($vm.State -eq 'Off') {
            Set-VMDvdDrive -VMName 'LocalPilot' -Path $null
            Set-VMFirmware -VM $vm -FirstBootDevice (Get-VMHardDiskDrive -VM $vm)
            Start-VM -VM $vm
            'Installer powered off. Installation media detached; starting installed disk.'
            break
        }
        Start-Sleep -Seconds 10
    }
    if ((Get-Date) -ge $deadline) { throw 'Installation monitoring timed out. VM left running for inspection.' }
} catch {
    $_ | Out-String | Set-Content (Join-Path $local 'logs\ubuntu-install-error.txt')
    Write-Error $_
    exit 1
} finally { Stop-Transcript }
