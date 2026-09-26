$ErrorActionPreference = 'Stop'
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
$script = Join-Path $PSScriptRoot 'scripts\implement_visual_left_from_checkpoint.tcl'
$checkpoint = Join-Path $PSScriptRoot 'build\visual_left_jtag_200mhz\post_synth.dcp'
if (-not (Test-Path -LiteralPath $checkpoint -PathType Leaf)) { throw "Missing post-synthesis checkpoint: $checkpoint" }
if (-not (Test-Path -LiteralPath $vivado)) { throw "Vivado not found at $vivado" }
if (-not (Test-Path -LiteralPath $license)) { throw "Vivado license not found at $license" }
$env:XILINXD_LICENSE_FILE = $license
& $vivado -mode batch -nolog -nojournal -notrace -source $script
if ($LASTEXITCODE -ne 0) { throw "Visual-left implementation failed with exit code $LASTEXITCODE" }
