param([switch]$StartIfStopped,[Parameter(Mandatory=$true)][guid]$ExpectedId)
$ErrorActionPreference='Stop'
$destination=Join-Path $env:ProgramData 'LocalPilot'
try {
    Import-Module Hyper-V
    $vm=Get-VM -Id $expectedId
    if($vm.Name -ne 'LocalPilot'){ throw 'LocalPilot VM identity mismatch' }
    if($StartIfStopped -and $vm.State.ToString() -in @('Off','Saved')){
        Start-VM -VM $vm | Out-Null
        $vm=Get-VM -Id $expectedId
    }
    $adapters=@(Get-VMNetworkAdapter -VM $vm | Where-Object SwitchName -eq 'Default Switch')
    $addresses=@($adapters | ForEach-Object IPAddresses | Where-Object { $_ -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' } | Select-Object -Unique)
    if($addresses.Count -eq 0){
        $macs=@($adapters | ForEach-Object { $_.MacAddress -replace '(..)(?!$)','$1-' })
        $addresses=@(Get-NetNeighbor -AddressFamily IPv4 | Where-Object { $_.LinkLayerAddress -in $macs -and $_.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' } | Select-Object -ExpandProperty IPAddress -Unique)
    }
    $data=@{VMId=$expectedId.ToString();Name=$vm.Name;State=$vm.State.ToString();IPs=$addresses;Time=(Get-Date).ToUniversalTime().ToString('o')}
    $temporary=Join-Path $destination 'network.tmp'
    $data | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination (Join-Path $destination 'network.json') -Force
} catch {
    $_.Exception.Message | Set-Content -LiteralPath (Join-Path $destination 'network-error.txt')
    exit 1
}
