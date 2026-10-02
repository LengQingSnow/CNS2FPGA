param(
    [Parameter(Mandatory = $true)][string]$BitFile,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [string]$SourceIp = '192.168.1.10',
    [switch]$SkipProgramming
)

$ErrorActionPreference = 'Stop'
$step15 = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$code = Split-Path -Parent $step15
$python = 'python'
$bit = (Resolve-Path -LiteralPath $BitFile -ErrorAction Stop).Path
$output = [System.IO.Path]::GetFullPath($OutputRoot)
$report = Join-Path (Split-Path -Parent (Split-Path -Parent $bit)) '..\reports\runtime_eth_long_events_retry_200mhz\run_status.txt'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Bundled Python missing.' }
if (-not (Test-Path -LiteralPath $report -PathType Leaf)) { throw "Build sign-off missing: $report" }
$signoff = Get-Content -LiteralPath $report -Raw
foreach ($required in @('timing_met=1','hold_met=1','unrouted_nets=0','partially_routed_nets=0','drc_error_count=0','drc_critical_count=0')) {
    if (-not $signoff.Contains($required)) { throw "Bitstream sign-off failed: $required" }
}
if (Test-Path -LiteralPath $output) {
    if (@(Get-ChildItem -LiteralPath $output -Force).Count -ne 0) { throw "Refusing to overwrite $output" }
}
$socket = [System.Net.Sockets.UdpClient]::new([System.Net.IPEndPoint]::new([System.Net.IPAddress]::Parse($SourceIp), 0))
$socket.Close()
New-Item -ItemType Directory -Path $output -Force | Out-Null
$statusPath = Join-Path $output 'status.json'
$bitHash = (Get-FileHash -LiteralPath $bit -Algorithm SHA256).Hash
if ($bitHash -ne 'D4C9378D461147062FA5DC590CB3647D241C789B01CC6255F38DA16CB21990DF') {
    throw 'Expanded-event bitstream hash mismatch.'
}
$state = [ordered]@{status='RUNNING'; phase='PROGRAM'; bit_sha256=$bitHash; programming_skipped=$SkipProgramming.IsPresent; completed_ipi_ms=@(); error=$null}
function Save-State { $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding utf8 }
Save-State
try {
    if (-not $SkipProgramming.IsPresent) {
        & (Join-Path $step15 'program_ethernet_bitstream.ps1') -BitFile $bit
        if ($LASTEXITCODE -ne 0) { throw 'Programming failed.' }
    }
    $state.phase = 'UPLOAD_COURTSHIP'; Save-State
    & $python (Join-Path $step15 'host\upload_image_udp.py') `
        (Join-Path $code '6_Connectome Compiler\outputs\courtship_song_hw_ir_v1') `
        --source-ip $SourceIp --board-ip 192.168.1.128 --timeout 2 --retries 10
    if ($LASTEXITCODE -ne 0) { throw 'Courtship Ethernet upload failed.' }
    foreach ($ipi in @(15,35,65)) {
        $state.phase = "CAPTURE_IPI_$ipi"; Save-State
        $trial = Join-Path $code "9_KU115 FPGA Validation\host\trials\ipi_$ipi"
        $capture = Join-Path $output "ipi_${ipi}_capture"
        & (Join-Path $code '14_Runtime Reconfigurable Deployment\host\run_runtime_trial.ps1') `
            -TrialDir $trial -CaptureDir $capture -CaptureEvents -EventCapacity 131072
        if ($LASTEXITCODE -ne 0) { throw "IPI $ipi JTAG capture failed." }
        $state.phase = "VERIFY_IPI_$ipi"; Save-State
        $reference = Join-Path $step15 "build\long_events_20260930\cpu_ipi_$ipi"
        $oldCounts = Join-Path $code "9_KU115 FPGA Validation\host\captures\ipi_${ipi}_summary_parsed\counts.csv"
        $verifyPath = Join-Path $output "ipi_${ipi}_verification.json"
        & $python (Join-Path $step15 'host\verify_long_event_capture.py') `
            --capture-dir $capture --reference-dir $reference --old-counts $oldCounts `
            --expected-epoch 1 --expected-capacity 131072 | Set-Content -LiteralPath $verifyPath -Encoding utf8
        if ($LASTEXITCODE -ne 0) { throw "IPI $ipi event verification failed." }
        $verified = Get-Content -LiteralPath $verifyPath -Raw | ConvertFrom-Json
        if ($verified.status -ne 'PASS') { throw "IPI $ipi verifier did not pass." }
        $state.completed_ipi_ms += $ipi; Save-State
    }
    $state.status = 'PASS'; $state.phase = 'COMPLETE'; Save-State
    Write-Host "LONG_EVENTS_CAMPAIGN_PASS $output"
} catch {
    $state.status = 'FAIL'; $state.error = $_.ToString(); Save-State
    throw
}
