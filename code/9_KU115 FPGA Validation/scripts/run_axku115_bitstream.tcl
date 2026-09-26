set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set rtl_core [file normalize [file join $root_dir rtl cns2fpga_core_sync_250mhz.sv]]
set rtl_top [file normalize [file join $root_dir rtl cns2fpga_axku115_top.sv]]
set xdc_file [file normalize [file join $root_dir constraints axku115_board_195mhz.xdc]]
set run_dir [file normalize [file join $root_dir build axku115_195mhz]]
set report_dir [file normalize [file join $root_dir reports axku115_195mhz]]
file mkdir $run_dir
file mkdir $report_dir

set part_name "xcku115-flva1517-2-i"
set top_name "cns2fpga_axku115_top"

read_verilog -sv [list $rtl_core $rtl_top]
read_xdc [list $xdc_file]

synth_design -top $top_name -part $part_name -flatten_hierarchy rebuilt
write_checkpoint -force [file join $run_dir post_synth.dcp]
report_utilization -file [file join $report_dir post_synth_utilization.rpt]
report_timing_summary -delay_type max -max_paths 20 \
    -file [file join $report_dir post_synth_timing_summary.rpt]

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
report_clock_utilization -file [file join $report_dir clock_utilization.rpt]
report_methodology -file [file join $report_dir methodology.rpt]
report_drc -file [file join $report_dir drc.rpt]

set worst_path [get_timing_paths -delay_type max -max_paths 1]
set wns [get_property SLACK $worst_path]
set timing_ok [expr {$wns >= 0.0}]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]

set status [open [file join $report_dir run_status.txt] w]
puts $status "board=ALINX_AXKU115_V1.0"
puts $status "part=$part_name"
puts $status "reference_clock_mhz=50.000"
puts $status "core_clock_mhz=195.000"
puts $status "wns_ns=$wns"
puts $status "timing_met=$timing_ok"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $drc_errors]"
close $status

if {!$timing_ok} {
    puts "ERROR: AXKU115 195 MHz timing did not close; WNS=$wns"
    exit 2
}
if {$unrouted != 0 || $partial != 0} {
    puts "ERROR: AXKU115 design has $unrouted unrouted and $partial partially routed nets"
    exit 3
}
if {[llength $drc_errors] != 0} {
    puts "ERROR: AXKU115 design has DRC errors: $drc_errors"
    exit 4
}

set bit_file [file join $run_dir cns2fpga_axku115_195mhz.bit]
write_bitstream -force $bit_file
puts "AXKU115_BITSTREAM_PASS file=$bit_file WNS=$wns"
exit
