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
    Join-Path $root '..\12_Visual-to-Steering Circuit\outputs\visual_left_hw_ir_v0'
}
$uploader = Join-Path $root 'host\upload_image_udp.py'
$probe = Join-Path $root 'host\probe_udp_status.py'
$reportDir = Join-Path $root 'reports\visual_upload'
$nicIndex = $NicIndex
$tempAddress = '192.168.1.10'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$log = Join-Path $reportDir ('visual_upload_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
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
    if ($LASTEXITCODE -ne 0) { throw "Visual image upload failed with exit $LASTEXITCODE" }
    # The uploader used BEGIN=1, 78 DATA packets=2..79, COMMIT=80,
    # and its own independent STATUS=81; the next valid request is 82.
    & $python $probe --source-ip $tempAddress --board-ip '192.168.1.128' --timeout 2.0 --attempts 3 --sequence 82
    if ($LASTEXITCODE -ne 0) { throw "Independent STATUS failed with exit $LASTEXITCODE" }
    Write-Output 'VISUAL_UDP_BOARD_TEST_PASS'
} catch {
    Write-Output "VISUAL_UDP_BOARD_TEST_FAIL=$($_.Exception.Message)"
    throw
} finally {
    if ($addressAdded) {
        Remove-NetIPAddress -InterfaceIndex $nicIndex -IPAddress $tempAddress -Confirm:$false
        Write-Output 'TEMPORARY_IP_REMOVED'
    }
    Stop-Transcript | Out-Null
}
