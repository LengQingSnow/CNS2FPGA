set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set run_dir [file normalize [file join $root_dir build axku115_195mhz]]
set report_dir [file normalize [file join $root_dir reports axku115_195mhz]]
set checkpoint [file join $run_dir post_route.dcp]

open_checkpoint $checkpoint
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
report_route_status -file [file join $report_dir route_status.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir post_route_timing_summary.rpt]
report_drc -file [file join $report_dir drc.rpt]

set worst_path [get_timing_paths -delay_type max -max_paths 1]
set wns [get_property SLACK $worst_path]
set timing_ok [expr {$wns >= 0.0}]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]

set status [open [file join $report_dir run_status.txt] w]
puts $status "board=ALINX_AXKU115_V1.0"
puts $status "part=xcku115-flva1517-2-i"
puts $status "reference_clock_mhz=50.000"
puts $status "core_clock_mhz=195.000"
puts $status "wns_ns=$wns"
puts $status "timing_met=$timing_ok"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $drc_errors]"
close $status

if {!$timing_ok} { error "Timing failed: WNS=$wns" }
if {$unrouted != 0 || $partial != 0} {
    error "Routing incomplete: unrouted=$unrouted partial=$partial"
}
if {[llength $drc_errors] != 0} { error "DRC errors: $drc_errors" }

set bit_file [file join $run_dir cns2fpga_axku115_195mhz.bit]
write_bitstream -force $bit_file
puts "AXKU115_BITSTREAM_PASS file=$bit_file WNS=$wns"
exit
