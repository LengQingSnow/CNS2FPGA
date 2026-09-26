$ErrorActionPreference = 'Stop'
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
if (-not (Test-Path -LiteralPath $vivado)) {
    throw "Vivado 2021.2 not found at $vivado"
}
if (Test-Path -LiteralPath $license) {
    $env:XILINXD_LICENSE_FILE = $license
}
& $vivado -mode batch -nolog -nojournal -notrace -source '.\scripts\run_200mhz_high_effort.tcl'
if ($LASTEXITCODE -ne 0) {
    throw "Vivado high-effort implementation failed with exit code $LASTEXITCODE"
}
