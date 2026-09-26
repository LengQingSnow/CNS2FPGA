# AXKU115 JTAG and JTAG-to-AXI probe (2026-09-25)

## Connected hardware

Read-only Vivado Hardware Manager enumeration succeeded with Vivado **2021.2** (SW build 3367213, IP build 3369179) and its local `hw_server`.

| Item | Observed value |
|---|---|
| Hardware server | `localhost:3121` |
| JTAG target | `localhost:3121/xilinx_tcf/Digilent/210512180081` |
| Device | `xcku115_0` |
| Device `PART` | `xcku115` |
| Device `IR_LENGTH` | `12` |
| `get_hw_axis` at time of probe | 0 objects |

The probe called only `open_hw_manager`, `connect_hw_server`, `open_hw_target`, `get_hw_devices`, and property queries. It did **not** call `program_hw_devices` or issue AXI transactions. `PROGRAM.FILE` was blank; that property alone does not establish whether the FPGA is configured. `get_hw_axis` returning zero does not establish the configuration either, because discovery of debug cores can depend on refreshing the device and the currently loaded design. The existing board bitstream has no JTAG-to-AXI block in its source.

Reproduce with `scripts/probe_jtag_readonly.tcl` in Vivado batch mode. It discovers available targets rather than hard-coding the cable serial.

## Installed JTAG-to-AXI IP

Vivado `get_ipdefs -all xilinx.com:ip:jtag_axi:*` returned `xilinx.com:ip:jtag_axi:1.2`. A temporary IP was created under `build/jtag_ip_probe` for part `xcku115-flva1517-2-i`; Vivado accepted:

```tcl
create_ip -name jtag_axi -vendor xilinx.com -library ip -version 1.2 \
  -module_name jtag_axi_probe -dir $probe_dir
set_property CONFIG.PROTOCOL 2 [get_ips jtag_axi_probe]
set_property CONFIG.M_AXI_DATA_WIDTH 32 [get_ips jtag_axi_probe]
set_property CONFIG.M_AXI_ADDR_WIDTH 32 [get_ips jtag_axi_probe]
```

Here `CONFIG.PROTOCOL=2` means AXI4-Lite. The generated Verilog instantiation template confirms `aclk`, active-low `aresetn`, and an **AXI4-Lite master** with 32-bit address/data and 4-bit `WSTRB`; the normal AW, W, B, AR, and R ready/valid channels are present. It has no AXI4 burst/ID ports in this configuration. The IP component XML also offers AXI4 mode (`CONFIG.PROTOCOL=0`) and 32- or 64-bit data/address widths. The IP clock `aclk` can be the core's 195 MHz clock, with reset released only after MMCM lock and reset synchronization.

The IP may be instantiated from HDL without a block design. Include its `.xci` and generated synthesis products in the Vivado project; a plain RTL reference to the module name without the IP files is insufficient.

### Verified non-project synthesis sequence

`create_ip` itself requires an open project in Vivado 2021.2. Calling it in pure non-project mode returns `No open project`. The probe created the XCI with an **in-memory project**, using `scripts/probe_jtag_ip.tcl`:

```tcl
create_project -in_memory -part xcku115-flva1517-2-i
create_ip -name jtag_axi -vendor xilinx.com -library ip -version 1.2 \
  -module_name jtag_axi_probe -dir $probe_dir
set_property CONFIG.PROTOCOL 2 [get_ips jtag_axi_probe]
set_property CONFIG.M_AXI_DATA_WIDTH 32 [get_ips jtag_axi_probe]
set_property CONFIG.M_AXI_ADDR_WIDTH 32 [get_ips jtag_axi_probe]
```

The resulting XCI is `build/jtag_ip_probe/jtag_axi_probe/jtag_axi_probe.xci`. The generated `jtag_axi_probe.veo` is in the same directory; after output generation, `synth/jtag_axi_probe.v` is also there.

A fresh **non-project** Vivado process then successfully synthesized a minimal top that instantiates the IP with this sequence (`scripts/probe_jtag_read_ip_synth.tcl`):

```tcl
set_part xcku115-flva1517-2-i
read_ip [list $xci_file]
generate_target all [get_ips jtag_axi_probe]
synth_ip [get_ips jtag_axi_probe]
read_verilog [list $rtl_file]
synth_design -top jtag_axi_smoke_top -part xcku115-flva1517-2-i \
  -flatten_hierarchy rebuilt
```

The OOC IP synthesis and top synthesis completed, producing `build/jtag_nonproject_probe/post_synth.dcp`. Omitting `synth_ip` after `read_ip` and `generate_target all` caused `module 'jtag_axi_probe' not found` at top elaboration. The `synth_ip` step is therefore required by the current non-project build arrangement.

The license environment must match the existing board build wrapper before running Vivado: `XILINXD_LICENSE_FILE=E:\Xilinx\lic\2021.2\VivadoLicense2037.lic`. Without it, `synth_design` failed to acquire the xcku115 Synthesis license. This was a probe invocation issue, not an IP licensing restriction.

## Vivado Hardware Manager transaction flow

Vivado's installed Tcl help confirms this sequence after loading a bitstream that contains the JTAG-to-AXI IP:

```tcl
open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target [lindex [get_hw_targets] 0]
set dev [lindex [get_hw_devices xcku115*] 0]
current_hw_device $dev
refresh_hw_device $dev
set axi [lindex [get_hw_axis -of_objects $dev] 0]
reset_hw_axi $axi

create_hw_axi_txn wr0 $axi -type WRITE -address 00000000 -data 00000001
run_hw_axi [get_hw_axi_txns wr0]
create_hw_axi_txn rd0 $axi -type READ -address 00000000
run_hw_axi [get_hw_axi_txns rd0]
puts [report_hw_axi_txn [get_hw_axi_txns rd0] -w 4 -t x4]
```

Actual transaction addresses must come from the new board-level register map. `reset_hw_axi` is required before first transaction per Vivado help, but was **not** run during this probe. `create_hw_axi_txn -len N` specifies a count of data words. AXI4-Lite mode should use one-word transactions; AXI4 mode is available if large stimulus or trace transfers require bursts. `run_hw_axi -queue` can queue up to 16 read and 16 write transactions, according to the installed help. PC/JTAG transaction latency is not the model's timestep latency; FPGA counters should measure that internally.

For a first board experiment, AXI4-Lite is enough for control and a short bit-exact trial. For thousands of stimulus/result words, choose an AXI4 memory-mapped window with burst transfers or accept a slower load/readback phase. In either case, stimulus transfer and FPGA model execution should be separate phases so JTAG throughput does not affect the 1 ms timestep deadline.

### Host transaction audit (2026-09-25)

The installed Vivado 2021.2 help and [AMD UG908 read transaction example](https://docs.amd.com/r/2021.2-%E6%97%A5%E6%9C%AC%E8%AA%9E/ug908-vivado-programming-debugging/%E8%AA%AD%E3%81%BF%E5%87%BA%E3%81%97%E3%83%88%E3%83%A9%E3%83%B3%E3%82%B6%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E3%81%AE%E4%BD%9C%E6%88%90%E3%81%A8%E5%AE%9F%E8%A1%8C) show that the `DATA` property for a four-word, 32-bit read appears as 32 contiguous hex digits. A one-word read therefore uses eight digits, as expected by `host/run_jtag_trial.tcl`. The `create_hw_axi_txn` command returns a transaction object that `run_hw_axi` and `delete_hw_axi_txn` accept.

The original host script does not inspect the AXI response. Vivado's [2021.2 `reset_hw_axi` reference](https://docs.amd.com/r/2021.2-English/ug835-vivado-tcl-commands/reset_hw_axi) lists `STATUS.RRESP`, `STATUS.BRESP`, `STATUS.AXI_READ_DONE`, and `STATUS.AXI_WRITE_DONE` on the **hw_axi** object. `run_hw_axi` updates these status properties; callers should check `RRESP/BRESP == OKAY` and the corresponding done flag after each transaction. A prior `reset_hw_axi $axis` is also recommended by the guide. Tcl command success alone should not be used to claim that an AXI slave returned OKAY.

This audit is based on the 2021.2 manuals and installed Tcl help. The exact value for a live single-word transaction has not yet been measured because no JTAG-to-AXI bitstream has been downloaded to the connected board during this read-only probe.

## Reproduction artifacts

- `scripts/probe_jtag_readonly.tcl`: live cable/device enumeration, no programming.
- `scripts/probe_jtag_ip.tcl`: isolated IP availability and configuration check.
- `scripts/probe_jtag_read_ip_synth.tcl`: verified non-project `read_ip` / `synth_ip` / `synth_design` flow.
- `scripts/probe_hw_axi_help.tcl`: local command syntax query.
- `build/jtag_ip_probe/jtag_axi_probe/jtag_axi_probe.veo`: generated AXI4-Lite instantiation template (temporary build product).
