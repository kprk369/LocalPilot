$ErrorActionPreference='Stop'
$project=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$local=Join-Path $project '.local'
Start-Transcript -Path (Join-Path $local 'logs\checkpoint.log') -Append
try {
    Import-Module Hyper-V
    $created=Get-Content (Join-Path $local 'vm-created.json') -Raw | ConvertFrom-Json
    $vm=Get-VM -Name 'LocalPilot'
    if($vm.Id.ToString() -ne $created.Id){ throw 'Unexpected VM identity' }
    Set-VM -VM $vm -AutomaticCheckpointsEnabled $false -CheckpointType ProductionOnly
    $snapshotName='LocalPilot-Desktop-Ready'
    if(@(Get-VMSnapshot -VM $vm | Where-Object Name -eq $snapshotName).Count -eq 0){ Checkpoint-VM -VM $vm -SnapshotName $snapshotName }
    Get-VMSnapshot -VMName 'LocalPilot' -Name $snapshotName | Select-Object Name,Id,CreationTime,SnapshotType | ConvertTo-Json | Set-Content (Join-Path $local 'desktop-checkpoint.json')
    Get-VM -Name 'LocalPilot' | Select-Object Name,Id,State,ProcessorCount,MemoryStartup | ConvertTo-Json | Set-Content (Join-Path $local 'hyperv-after.json')
    'Production checkpoint created for LocalPilot. Other VMs were not changed.'
} catch {
    $_ | Out-String | Set-Content (Join-Path $local 'logs\checkpoint-error.txt')
    Write-Error $_
    exit 1
} finally {Stop-Transcript}
