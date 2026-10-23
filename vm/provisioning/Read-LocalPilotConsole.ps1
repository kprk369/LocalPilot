$ErrorActionPreference='Stop'
$root=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$log=Join-Path $root '.local\logs\serial-console.log'
$pipe=New-Object System.IO.Pipes.NamedPipeClientStream('.', 'LocalPilotConsole', [System.IO.Pipes.PipeDirection]::In)
try {
    $pipe.Connect(20000)
    $file=[IO.File]::Open($log,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::ReadWrite)
    $buffer=New-Object byte[] 8192
    $deadline=(Get-Date).AddMinutes(45)
    while ((Get-Date) -lt $deadline) {
        $read=$pipe.ReadAsync($buffer,0,$buffer.Length)
        while (-not $read.Wait(1000)) { if((Get-Date) -gt $deadline){exit} }
        $count=$read.Result
        if($count -eq 0){ break }
        $file.Write($buffer,0,$count)
        $file.Flush()
    }
} catch { $_ | Out-String | Set-Content (Join-Path $root '.local\logs\serial-error.txt') }
finally { if($file){$file.Dispose()}; $pipe.Dispose() }
