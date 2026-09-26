$ErrorActionPreference = 'Stop'
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
$script = Join-Path $PSScriptRoot 'scripts\finalize_axku115_bitstream.tcl'
$env:XILINXD_LICENSE_FILE = $license
& $vivado -mode batch -nolog -nojournal -notrace -source $script
if ($LASTEXITCODE -ne 0) {
    throw "AXKU115 bitstream finalization failed with exit code $LASTEXITCODE"
}
