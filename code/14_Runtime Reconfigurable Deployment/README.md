# Runtime-reconfigurable graph deployment / 运行时网络部署

This step changes the deployment contract: one AXKU115 bitstream reserves the
maximum graph storage and compute datapath; a host can replace the graph image
through JTAG AXI-Lite **without rerunning Vivado or reprogramming the FPGA**.
Only images using the existing `safe_wf24` hardware IR are compatible. The
architecture, numerical format, and physical capacities are fixed in the bitstream.

本步骤将网络图从综合时初始化数据改为运行时写入片上存储器。一个 bit 文件可顺序装载不同的
`safe_wf24` 网络，但不能改变神经元动力学、数值格式或硬件容量。

## Contents

- `rtl/`: parameterized graph RAMs, runtime image protocol, trial engine, AXI-Lite top.
- `host/prepare_image.py`: validate compiler `.mem` records, CSR, post indices,
  format and capacities; calculate SHA-256 hashes and a transport checksum.
- `host/load_runtime_image.ps1` + `.tcl`: validate then stream an image over JTAG;
  reject bad firmware ID, incomplete transfer, wrong counters or checksum.
- `host/run_two_image_demo.ps1`: program once, load visual then courtship graph,
  capture and compare each trial with the CPU reference. Use `-ValidateOnly`
  to preflight all inputs without touching the board.
- `sim/tb_runtime_reload.sv`: two distinct images, one unchanged RTL instance;
  also verifies refusal to start without an image and rejection of an incomplete image.
- `sim/tb_visual_real_image.sv`: streams the real 226-neuron visual-left image,
  runs 250 steps, and compares every spike count with the independent reference.
- `sim/tb_courtship_real_image.sv`: streams the full 6,279-neuron/350,185-synapse
  courtship image and matches all eight smoke-trial spike counts.
- `scripts/build_runtime_bitstream.tcl`: Vivado 2021.2 build, 200 MHz target.
- `constraints/`: original AXKU115 JTAG pin/timing constraints.

## Image protocol

The controller holds up to 6,279 neurons and 350,185 synapses. Its graph RAMs
are *not* initialized from `.mem` by synthesis. Write `BEGIN=1` to `0x30`,
then neuron/synapse counts to `0x34/0x38`. Select each region at `0x3C` and
stream little-endian 32-bit lanes to `0x40`, in order:

| Region | Records | Words per record |
| --- | ---: | ---: |
| 0 neuron parameters | neuron count | 4 |
| 1 synapses | synapse count | 2 |
| 2 CSR offsets | neuron count | 1 |
| 3 type/sign flags | neuron count | 1 |

For each accepted word `w` in region `r`, update
`checksum = rotl32(checksum, 1) XOR w XOR r`, starting from zero. Write the
result to `0x44`, then `COMMIT=2` to `0x30`. Status `0x30` bit 0 is
`image_ready`, bit 1 `load_active`, bit 2 `image_error`, bit 3 reserved zero,
bits 7:4 error code. `0x48` is the observed checksum, `0x4C` the successful
image epoch, `0x50..0x5C` word counts, `0x60/0x64` active counts, and
`0x68/0x6C` physical capacities. `ABORT=3` invalidates the image. An image
error requires a fresh `BEGIN` and complete reload.

The loader rejects out-of-range synapse posts and CSR ranges in hardware;
the host preflight additionally verifies contiguous CSR ranges and all layout
fields. `BEGIN` invalidates the previous image immediately. The graph cannot run
until the complete new image passes `COMMIT`. The trial engine clears all
neuron state at the start of each trial, so state never leaks across images.
Writes during trials are rejected by the AXI-Lite bridge. This is a
*single-image* design: it is not a background/double-buffered swap.

## Offline verification

From this directory:

```powershell
vlib sim_work
vlog -sv -work sim_work rtl/cns2fpga_core_sync_runtime.sv rtl/cns2fpga_trial_engine_runtime.sv rtl/cns2fpga_axi_lite_slave.sv sim/tb_runtime_reload.sv
vsim -c -lib sim_work tb_runtime_reload -do 'run -all; quit -f'
vlog -sv -work sim_work sim/tb_visual_real_image.sv
vsim -c -lib sim_work tb_visual_real_image -do 'run -all; quit -f'
vlog -sv -work sim_work sim/tb_courtship_real_image.sv
vsim -c -lib sim_work tb_courtship_real_image -do 'run -all; quit -f'
python host/prepare_image.py '../../12_Visual-to-Steering Circuit/outputs/visual_left_hw_ir_v0'
python host/prepare_image.py '../../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1'
```

Run Vivado `-mode batch -source scripts/build_runtime_bitstream.tcl`. Set
`CNS2FPGA_SYNTH_ONLY=1` to stop after synthesis. Do not deploy a bitstream
unless timing, hold, routing and DRC pass. The board sequence is: program the
**new runtime bitstream once**, load image A with `host/load_runtime_image.ps1`,
run a trial, load image B with the same script **without reprogramming**, and
run a second trial. This physical sequence passed on 30 September 2026;
simulation alone was not used as proof. On 2026-09-27, Vivado 2021.2 completed the
200 MHz build with setup WNS +0.043 ns, hold WHS +0.030 ns, zero unrouted
nets, and zero DRC errors. See `docs/implementation_status.md` for the
bitstream hash and original implementation signoff.

Example board commands from this directory (only after the full build passes):

```powershell
.\host\run_two_image_demo.ps1 -ValidateOnly
.\host\run_two_image_demo.ps1
```

For manual control, another valid sequence is:

```powershell
.\program_runtime_bitstream.ps1
.\host\load_runtime_image.ps1 -ImageDirectory '..\6_Connectome Compiler\outputs\courtship_song_hw_ir_v1'
.\host\run_runtime_trial.ps1 -TrialDir '..\9_KU115 FPGA Validation\host\trials\smoke8' -CaptureDir 'build\courtship_smoke8_capture'
.\host\load_runtime_image.ps1 -ImageDirectory '..\12_Visual-to-Steering Circuit\outputs\visual_left_hw_ir_v0'
.\host\run_runtime_trial.ps1 -TrialDir '..\12_Visual-to-Steering Circuit\outputs\visual_left_board_v0\trial' -CaptureDir 'build\visual_left_capture'
```

The trial wrapper checks that the loaded image's neuron count matches the
stimulus metadata and captures image epoch/checksum/counts with the results.
Changing images **does not** call `program_hw_devices` or write a new bit file.

## P0 physical result (30 September 2026)

The runtime JTAG bitstream SHA-256 is
`95F9B50EE03804DDC211828A9FBD3B3171B45BC3FFB79F9F3B2407F0D3190E52`.
With one programming operation, the visual image reached epoch 1 and matched
560 ordered fixed-CPU events over 250 steps; the courtship image reached epoch 2
and matched 2,475 ordered events over eight steps. An interrupted partial
upload was not committed. Incomplete COMMIT and an invalid postsynaptic index
were rejected; a valid visual reload reached epoch 4 and again matched the
full 250-step trial. Raw captures are under `build/p0_jtag_20260930/` and
`build/p0_jtag_recovery_logged_20260930/`; the curated public copy is under
`reports/p0_board_20260930/`. The offline cross-transport audit is
`../15_Ethernet_Runtime_Deployment/reports/p0_board_audit_v1.json`.

JTAG 运行时 bit 文件只烧录一次，视觉与求偶镜像随后顺序装载且事件分别匹配
560 和 2,475 个；中断、不完整提交及非法索引被拒绝，重新装载有效视觉镜像后
250 步试验再次通过。该测试验证已注入的异常，不等于穷举所有故障。

The courtship image requires 738,044 single-word graph writes. AXI-Lite/JTAG
upload may be slow; this is a functional first version, not a high-throughput
transport. DDR is not used. The maximum graph's current synthesis uses 585
RAMB36, 3 RAMB18, 4 DSP48E2 and 20,167 LUTs as memory. This is within both
the old 625-BRAM36 planning allowance and the KU115's 2,160 RAMB36 capacity;
the implemented resource and timing reports remain the final authority.
Vivado 2021.2 maps graph synapses/offsets/type flags to BRAM but neuron
parameters to distributed LUT RAM.
