param(
    [string]$Python = 'python',
    [string]$ImageDirectory = '',
    [int]$NicIndex = 23,
    [string]$ExistingAddress = '192.168.0.3'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = $Python
$image = if ($ImageDirectory) { $ImageDirectory } else {
    Join-Path $root '..\6_Connectome Compiler\outputs\courtship_song_hw_ir_v1'
}
$uploader = Join-Path $root 'host\upload_image_udp.py'
$probe = Join-Path $root 'host\probe_udp_status.py'
$reportDir = Join-Path $root 'reports\courtship_upload'
$nicIndex = $NicIndex
$tempAddress = '192.168.1.10'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$log = Join-Path $reportDir ('courtship_upload_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
Start-Transcript -Path $log | Out-Null
$addressAdded = $false
try {
    $adapter = Get-NetAdapter -InterfaceIndex $nicIndex
    if ($adapter.InterfaceDescription -ne 'Realtek Gaming GbE Family Controller' -or $adapter.Status -ne 'Up') {
        throw 'Expected Realtek adapter is not connected.'
    }
    if (-not (Get-NetIPAddress -InterfaceIndex $nicIndex -AddressFamily IPv4 | Where-Object IPAddress -eq $ExistingAddress)) {
        throw "Existing host address $ExistingAddress is missing."
    }
    if (Get-NetIPAddress -InterfaceIndex $nicIndex -AddressFamily IPv4 | Where-Object IPAddress -eq $tempAddress) {
        throw 'Temporary test address is already present; refusing to take ownership.'
    }
    $preflight = & $python $uploader $image --dry-run
    if ($LASTEXITCODE -ne 0 -or
        $preflight -ne 'PREFLIGHT neurons=6279 synapses=350185 words=738044 packets=11538 checksum=45AEAAAE') {
        throw "Unexpected courtship image preflight: $preflight"
    }
    Write-Output $preflight
    Write-Output "LINK_SPEED=$($adapter.LinkSpeed)"
    New-NetIPAddress -InterfaceIndex $nicIndex -IPAddress $tempAddress -PrefixLength 24 -PolicyStore ActiveStore -SkipAsSource $false | Out-Null
    $addressAdded = $true
    $preferred = $false
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        $current = Get-NetIPAddress -InterfaceIndex $nicIndex -IPAddress $tempAddress -AddressFamily IPv4
        if ($current.AddressState -eq 'Preferred') { $preferred = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $preferred) { throw 'Temporary test IP did not become Preferred.' }
    & $python $uploader $image --board-ip '192.168.1.128' --source-ip $tempAddress --timeout 2.0 --retries 10
    if ($LASTEXITCODE -ne 0) { throw "Courtship image upload failed with exit $LASTEXITCODE" }
    # BEGIN + 11,535 DATA + COMMIT + uploader STATUS = sequences 1..11,538.
    & $python $probe --source-ip $tempAddress --board-ip '192.168.1.128' --timeout 2.0 --attempts 3 --sequence 11539
    if ($LASTEXITCODE -ne 0) { throw "Independent STATUS failed with exit $LASTEXITCODE" }
    Write-Output 'COURTSHIP_UDP_BOARD_TEST_PASS'
} catch {
    Write-Output "COURTSHIP_UDP_BOARD_TEST_FAIL=$($_.Exception.Message)"
    throw
} finally {
    if ($addressAdded) {
        Remove-NetIPAddress -InterfaceIndex $nicIndex -IPAddress $tempAddress -Confirm:$false
        Write-Output 'TEMPORARY_IP_REMOVED'
    }
    Stop-Transcript | Out-Null
}
