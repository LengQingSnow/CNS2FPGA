param(
    [switch]$SynthesisOnly
)
$ErrorActionPreference = 'Stop'
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
$script = Join-Path $PSScriptRoot 'scripts\run_axku115_jtag_bitstream.tcl'
if (-not (Test-Path -LiteralPath $vivado)) { throw "Vivado not found at $vivado" }
if (-not (Test-Path -LiteralPath $license)) { throw "Vivado license not found at $license" }
$env:XILINXD_LICENSE_FILE = $license
if ($SynthesisOnly) { $env:CNS2FPGA_SYNTH_ONLY = '1' }
else { Remove-Item Env:CNS2FPGA_SYNTH_ONLY -ErrorAction SilentlyContinue }
& $vivado -mode batch -nolog -nojournal -notrace -source $script
if ($LASTEXITCODE -ne 0) { throw "AXKU115 JTAG build failed with exit code $LASTEXITCODE" }
