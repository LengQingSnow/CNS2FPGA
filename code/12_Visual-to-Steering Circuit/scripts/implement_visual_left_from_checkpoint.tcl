set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set run_dir [file normalize [file join $root_dir build visual_left_jtag_200mhz]]
set report_dir [file normalize [file join $root_dir reports visual_left_jtag_200mhz]]
set part_name xcku115-flva1517-2-i
set ::env(XILINXD_LICENSE_FILE) {E:/Xilinx/lic/2021.2/VivadoLicense2037.lic}
set ::env(LM_LICENSE_FILE) {E:/Xilinx/lic/2021.2/VivadoLicense2037.lic}
set ip_xci [file join $run_dir ip cns2fpga_jtag_axi cns2fpga_jtag_axi.xci]
set synth_dcp [file join $run_dir post_synth.dcp]
if {![file isfile $ip_xci] || ![file isfile $synth_dcp]} {error "Missing synthesis checkpoint or JTAG IP"}
create_project -in_memory -part $part_name
read_ip [list $ip_xci]
open_checkpoint $synth_dcp

opt_design
place_design
phys_opt_design
route_design
phys_opt_design

write_checkpoint -force [file join $run_dir post_route.dcp]
report_route_status -file [file join $report_dir route_status.rpt]
report_utilization -file [file join $report_dir post_route_utilization.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir post_route_timing_summary.rpt]
report_drc -file [file join $report_dir drc.rpt]

set worst_path [get_timing_paths -delay_type max -max_paths 1]
set wns [get_property SLACK $worst_path]
set timing_ok [expr {$wns >= 0.0}]
set worst_hold_path [get_timing_paths -delay_type min -max_paths 1]
set whs [get_property SLACK $worst_hold_path]
set hold_ok [expr {$whs >= 0.0}]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]

set status [open [file join $report_dir run_status.txt] w]
puts $status "board=ALINX_AXKU115_V1.0"
puts $status "part=$part_name"
puts $status "core_clock_mhz=200.000"
puts $status "wns_ns=$wns"
puts $status "timing_met=$timing_ok"
puts $status "whs_ns=$whs"
puts $status "hold_met=$hold_ok"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $drc_errors]"
close $status

if {!$timing_ok || !$hold_ok || $unrouted != 0 || $partial != 0 || [llength $drc_errors] != 0} {
    puts "ERROR: AXKU115 JTAG implementation did not pass: WNS=$wns WHS=$whs unrouted=$unrouted partial=$partial DRC=[llength $drc_errors]"
    exit 2
}

set bit_file [file join $run_dir cns2fpga_visual_left_jtag_200mhz.bit]
write_bitstream -force $bit_file
puts "VISUAL_LEFT_JTAG_BITSTREAM_PASS file=$bit_file WNS=$wns"
exit 0
