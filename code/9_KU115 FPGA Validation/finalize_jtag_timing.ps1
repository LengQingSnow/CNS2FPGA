$ErrorActionPreference = 'Stop'
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
$script = Join-Path $PSScriptRoot 'scripts\finalize_jtag_timing.tcl'
if (-not (Test-Path -LiteralPath $vivado)) { throw "Vivado not found at $vivado" }
if (-not (Test-Path -LiteralPath $license)) { throw "Vivado license not found at $license" }
$oldLicense = $env:XILINXD_LICENSE_FILE
try {
    $env:XILINXD_LICENSE_FILE = $license
    & $vivado -mode batch -nolog -nojournal -notrace -source $script
    if ($LASTEXITCODE -ne 0) { throw "AXKU115 final timing signoff failed with exit code $LASTEXITCODE" }
} finally {
    $env:XILINXD_LICENSE_FILE = $oldLicense
}
