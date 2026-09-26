$ErrorActionPreference = "Stop"

$vivado = "E:\Xilinx\Vivado\2021.2\bin\vivado.bat"
$license = "E:\Xilinx\lic\2021.2\VivadoLicense2037.lic"
$script = Join-Path $PSScriptRoot "scripts\run_200mhz_explore.tcl"

if (-not (Test-Path -LiteralPath $vivado)) {
    throw "Vivado was not found at $vivado"
}
if (-not (Test-Path -LiteralPath $license)) {
    throw "Vivado license was not found at $license"
}

$env:XILINXD_LICENSE_FILE = $license
& $vivado -mode batch -notrace -source $script
exit $LASTEXITCODE
