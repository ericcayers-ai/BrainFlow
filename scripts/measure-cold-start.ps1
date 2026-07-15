<#
.SYNOPSIS
  Measure BrainFlow desktop.exe cold-start time-to-visible-window (Windows).

.DESCRIPTION
  Starts the Tauri release binary, polls Process.MainWindowHandle until the
  native window is visible, then kills the process. This is time-to-native-
  window (WebView2 HWND), not "UI fully interactive + sidecar ready".

.PARAMETER Exe
  Path to desktop.exe (default: <repo>/target/release/desktop.exe)

.PARAMETER Samples
  Number of timed launches (default 3). First sample after a long idle may
  be colder than subsequent ones within the same session.

.PARAMETER TimeoutMs
  Per-sample wait for MainWindowHandle (default 60000).

.EXAMPLE
  powershell -NoProfile -File scripts/measure-cold-start.ps1
#>
[CmdletBinding()]
param(
  [string]$Exe = "",
  [int]$Samples = 3,
  [int]$TimeoutMs = 60000
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if (-not $Exe) {
  $Exe = Join-Path $repo "target\release\desktop.exe"
}
if (-not (Test-Path -LiteralPath $Exe)) {
  Write-Error "desktop.exe not found at '$Exe'. Build first: npm run build:desktop"
}

Add-Type -TypeDefinition @"
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
public static class BrainFlowColdStart {
  [DllImport("user32.dll")]
  public static extern bool IsWindowVisible(IntPtr hWnd);

  public static long TimeToMainWindowMs(string path, int timeoutMs) {
    var sw = Stopwatch.StartNew();
    var psi = new ProcessStartInfo(path) { UseShellExecute = true };
    var p = Process.Start(psi);
    if (p == null) throw new Exception("Process.Start returned null");
    try {
      while (sw.ElapsedMilliseconds < timeoutMs) {
        p.Refresh();
        if (p.HasExited) throw new Exception("process exited early code=" + p.ExitCode);
        if (p.MainWindowHandle != IntPtr.Zero && IsWindowVisible(p.MainWindowHandle)) {
          sw.Stop();
          return sw.ElapsedMilliseconds;
        }
        Thread.Sleep(25);
      }
      throw new Exception("timeout waiting for MainWindowHandle");
    } finally {
      try {
        if (!p.HasExited) {
          // .NET Framework Process.Kill() has no entireProcessTree overload.
          p.Kill();
          p.WaitForExit(5000);
        }
      } catch { /* best-effort teardown */ }
    }
  }
}
"@

Write-Host "[cold-start] exe=$Exe"
Write-Host "[cold-start] samples=$Samples timeoutMs=$TimeoutMs"
Write-Host "[cold-start] metric=time-to-visible-MainWindowHandle (not full interactive+sidecar)"

$results = New-Object System.Collections.Generic.List[int]
for ($i = 1; $i -le $Samples; $i++) {
  Write-Host "[cold-start] sample $i ..."
  $ms = [BrainFlowColdStart]::TimeToMainWindowMs($Exe, $TimeoutMs)
  $results.Add([int]$ms)
  Write-Host "[cold-start] sample $i TIME_TO_WINDOW_MS=$ms"
  Start-Sleep -Seconds 2
}

$min = ($results | Measure-Object -Minimum).Minimum
$max = ($results | Measure-Object -Maximum).Maximum
$avg = ($results | Measure-Object -Average).Average
$sorted = $results | Sort-Object
$mid = [int][math]::Floor(($sorted.Count - 1) / 2)
$median = $sorted[$mid]

Write-Host ""
Write-Host "TIME_TO_WINDOW_MS_SAMPLES=$($results -join ',')"
Write-Host "TIME_TO_WINDOW_MS_MIN=$min"
Write-Host "TIME_TO_WINDOW_MS_MEDIAN=$median"
Write-Host "TIME_TO_WINDOW_MS_AVG=$([math]::Round($avg, 1))"
Write-Host "TIME_TO_WINDOW_MS_MAX=$max"

# Machine-readable line for docs/parsers
Write-Output ("RESULT`tmin={0}`tmedian={1}`tavg={2}`tmax={3}`tsamples={4}" -f `
  $min, $median, [math]::Round($avg, 1), $max, ($results -join ','))
