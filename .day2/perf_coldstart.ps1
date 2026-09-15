# Day 2 / Stage 8 — cold-start cost of the backend process.
#
# PDF: "Cold-start cost versus warm cost."
#
# Measures, from a fresh uvicorn process:
#   t_spawn    - process created
#   t_port     - TCP 8000 accepting connections
#   t_health   - GET /api/health returns 200 (embedding model resident by then,
#                because the lifespan handler pre-loads it before serving)
#   rss_after  - working set of the uvicorn process once healthy
#
# The OS file cache is warm (the models were read earlier in this session), so
# this is the realistic *repeated* cold start, not a first-ever-boot number.
# Stated as such in the report rather than presented as a from-disk cold start.

$ErrorActionPreference = 'Stop'
$backend = 'C:\RAGPDFQABOT\pdf-rag-chatbot\backend'
$py = "$backend\.venv\Scripts\python.exe"
$log = 'C:\RAGPDFQABOT\pdf-rag-chatbot\.day2\backend.log'

# Make sure nothing is already holding the port.
Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $py } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

if (Test-Path $log) { Remove-Item $log -Force }

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$proc = Start-Process -FilePath $py `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
    -WorkingDirectory $backend -PassThru -RedirectStandardError $log `
    -RedirectStandardOutput "$log.out" -WindowStyle Hidden
$tSpawn = $sw.Elapsed.TotalSeconds
Write-Output ("t_spawn  : {0:N3} s  (pid {1})" -f $tSpawn, $proc.Id)

# Wait for the port to accept a connection.
$tPort = $null
while ($sw.Elapsed.TotalSeconds -lt 300) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', 8000)
        $c.Close()
        $tPort = $sw.Elapsed.TotalSeconds
        break
    } catch { Start-Sleep -Milliseconds 100 }
}
Write-Output ("t_port   : {0:N3} s" -f $tPort)

# Wait for /api/health to answer 200.
$tHealth = $null
$body = $null
while ($sw.Elapsed.TotalSeconds -lt 300) {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 30
        if ($r.StatusCode -eq 200) { $tHealth = $sw.Elapsed.TotalSeconds; $body = $r.Content; break }
    } catch { Start-Sleep -Milliseconds 200 }
}
Write-Output ("t_health : {0:N3} s" -f $tHealth)
Write-Output ("health   : {0}" -f $body)

$p = Get-Process -Id $proc.Id
Write-Output ("rss_after: {0:N1} MB working set, {1:N1} MB private" -f ($p.WorkingSet64/1MB), ($p.PrivateMemorySize64/1MB))
Write-Output ("cpu_s    : {0:N2} s CPU consumed during startup" -f $p.CPU)
Write-Output ("pid      : {0}" -f $proc.Id)
