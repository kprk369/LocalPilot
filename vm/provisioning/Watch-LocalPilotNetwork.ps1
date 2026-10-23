$ErrorActionPreference='Stop'
$project=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$local=Join-Path $project '.local'
Import-Module Hyper-V
$created=Get-Content (Join-Path $local 'vm-created.json') -Raw | ConvertFrom-Json
$deadline=(Get-Date).AddMinutes(30)
while((Get-Date) -lt $deadline) {
    $vm=Get-VM -Name 'LocalPilot'
    if($vm.Id.ToString() -ne $created.Id){ throw 'Unexpected VM identity' }
    $adapter=Get-VMNetworkAdapter -VM $vm
    $mac=$adapter.MacAddress -replace '(..)(?!$)','$1-'
    $ips=@($adapter.IPAddresses | Where-Object {$_ -match '^\d+\.'})
    if($ips.Count -eq 0){$ips=@(Get-NetNeighbor -AddressFamily IPv4 | Where-Object { $_.LinkLayerAddress -eq $mac } | Select-Object -ExpandProperty IPAddress)}
    @{Time=(Get-Date).ToString('o');Name=$vm.Name;VMId=$vm.Id.ToString();State=$vm.State.ToString();MAC=$mac;IPs=$ips} | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $local 'network-status.json')
    Start-Sleep -Seconds 10
}
