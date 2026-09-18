<#
.SYNOPSIS
    Polls /api/health and raises an alert when the service is degraded or down.

.DESCRIPTION
    Closes the alerting half of stage 21 in 01_After_Coding_Is_Complete.pdf.
    Before this, the project had logs and a health endpoint but nothing watched
    them: "the service currently logs to stdout and nothing watches it".

    The PDF's alerting rule is to alert on symptoms a user feels, not on every
    raw metric. Three symptoms qualify for this deployment, and nothing else
    raises an alert:

      * the service is unreachable          (the user sees nothing load)
      * status is "degraded"                (a dependency is down, so uploads
                                             or questions will fail)
      * health takes longer than -SlowMs    (the user waits)

    Deliberately NOT a metrics dashboard. This is a single-user service bound to
    127.0.0.1; Prometheus and Grafana would be more infrastructure than the
    thing they watch. That trade-off is recorded in the README's known
    limitations rather than left implicit.

    Every check appends one JSON line to the log, so the history is queryable
    with the same tooling as the application's own production logs:

        Get-Content .day6\health-monitor.log | ForEach-Object { $_ | ConvertFrom-Json } |
            Where-Object { $_.status -ne 'ok' }

.PARAMETER Url
    Health endpoint. Defaults to the loopback address the service binds to.

.PARAMETER IntervalSeconds
    Seconds between checks. Ignored with -Once.

.PARAMETER Once
    Run a single check and exit. This is the mode to use from Task Scheduler,
    which supplies its own schedule. Exit code 0 = healthy, 1 = alert.

.PARAMETER SlowMs
    Latency above which a reachable service is still treated as a symptom.
    The health endpoint makes a real Ollama call, a ChromaDB heartbeat, a SQLite
    query and a Tesseract subprocess spawn, measured at roughly 80-150 ms warm
    on the reference hardware, so 5000 ms is "something is badly wrong", not
    "the machine is busy".

.PARAMETER LogPath
    Where to append the JSONL history. Defaults to .day6\health-monitor.log,
    which is git-ignored.

.EXAMPLE
    # Watch continuously in a terminal
    powershell -ExecutionPolicy Bypass -File scripts\health-monitor.ps1

.EXAMPLE
    # One check, for a scheduler. Register it to run every 5 minutes with:
    #
    #   $action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
    #       -Argument '-ExecutionPolicy Bypass -File "<repo>\scripts\health-monitor.ps1" -Once'
    #   $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    #       -RepetitionInterval (New-TimeSpan -Minutes 5)
    #   Register-ScheduledTask -TaskName 'pdf-rag-chatbot-health' -Action $action -Trigger $trigger
    #
    # Registering a scheduled task changes machine state outside the project, so
    # it is documented here and left for the operator to run deliberately.
    powershell -ExecutionPolicy Bypass -File scripts\health-monitor.ps1 -Once
#>
[CmdletBinding()]
param(
    [string]$Url = 'http://127.0.0.1:8000/api/health',
    [int]$IntervalSeconds = 60,
    [switch]$Once,
    [int]$SlowMs = 5000,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'

# Paths derive from this script's location so the monitor runs from any checkout.
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $LogPath) { $LogPath = Join-Path $repo '.day6\health-monitor.log' }
$logDir = Split-Path -Parent $LogPath
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }

function Write-Alert {
    param([string]$Symptom, [string]$Detail)

    $line = "[ALERT] $(Get-Date -Format 's')  $Symptom  $Detail"
    Write-Host $line -ForegroundColor Red

    # A desktop notification, so an alert reaches the operator without a
    # terminal in front of them. Wrapped because the toast APIs are not present
    # on every Windows edition, and a monitor that dies because it could not
    # draw a notification is worse than one that only writes the log.
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $icon = New-Object System.Windows.Forms.NotifyIcon
        $icon.Icon = [System.Drawing.SystemIcons]::Warning
        $icon.BalloonTipTitle = 'PDF Q&A Chatbot'
        $icon.BalloonTipText = "$Symptom - $Detail"
        $icon.Visible = $true
        $icon.ShowBalloonTip(10000)
        Start-Sleep -Seconds 1
        $icon.Dispose()
    } catch {
        Write-Verbose "Desktop notification unavailable: $($_.Exception.Message)"
    }
}

function Invoke-HealthCheck {
    $started = [System.Diagnostics.Stopwatch]::StartNew()
    $entry = [ordered]@{ timestamp = (Get-Date -Format 's'); url = $Url }

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
        $elapsed = [int]$started.ElapsedMilliseconds
        $body = $response.Content | ConvertFrom-Json

        $entry.reachable = $true
        $entry.latency_ms = $elapsed
        $entry.status = $body.status
        $entry.version = $body.version
        $entry.uptime_seconds = $body.uptime_seconds
        $entry.down = @(
            'ollama', 'chroma', 'embedding_model', 'ocr', 'database' |
                Where-Object {
                    $field = switch ($_) {
                        'embedding_model' { 'embedding_model_loaded' }
                        default { "${_}_available" }
                    }
                    -not $body.$field
                }
        )

        if ($body.status -ne 'ok') {
            $entry.alert = 'degraded'
            Write-Alert 'DEGRADED' ("dependencies down: " + ($entry.down -join ', '))
        } elseif ($elapsed -gt $SlowMs) {
            $entry.alert = 'slow'
            Write-Alert 'SLOW' "health took ${elapsed}ms (threshold ${SlowMs}ms)"
        } else {
            $entry.alert = $null
            # OCR is a fallback, not part of the ok/degraded gate, so its absence
            # is reported without being escalated to an alert.
            $note = if ($entry.down -contains 'ocr') { ' (OCR unavailable)' } else { '' }
            Write-Host "[ok]    $($entry.timestamp)  ${elapsed}ms  v$($body.version)$note"
        }
    } catch {
        $entry.reachable = $false
        $entry.latency_ms = [int]$started.ElapsedMilliseconds
        $entry.status = 'unreachable'
        $entry.alert = 'unreachable'
        $entry.error = $_.Exception.Message
        Write-Alert 'UNREACHABLE' $_.Exception.Message
    }

    ($entry | ConvertTo-Json -Compress -Depth 4) | Add-Content -Path $LogPath -Encoding utf8
    return ($null -eq $entry.alert)
}

if ($Once) {
    $healthy = Invoke-HealthCheck
    exit ([int](-not $healthy))
}

Write-Host "Watching $Url every ${IntervalSeconds}s. Log: $LogPath"
Write-Host "Alerts on: unreachable, degraded, slower than ${SlowMs}ms. Ctrl-C to stop.`n"
while ($true) {
    Invoke-HealthCheck | Out-Null
    Start-Sleep -Seconds $IntervalSeconds
}
