set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set run_dir [file join $root_dir build axku115_jtag_200mhz]
set report_dir [file join $root_dir reports axku115_jtag_200mhz]
open_checkpoint [file join $run_dir post_route.dcp]

phys_opt_design -insert_negative_edge_ffs -aggressive_hold_fix
route_design
write_checkpoint -force [file join $run_dir post_hold_negedge.dcp]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir post_hold_negedge_timing_summary.rpt]
report_route_status -file [file join $report_dir post_hold_negedge_route_status.rpt]
report_drc -file [file join $report_dir post_hold_negedge_drc.rpt]

set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set whs [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]
set status [open [file join $report_dir hold_negedge_status.txt] w]
puts $status "wns_ns=$wns"
puts $status "whs_ns=$whs"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $drc_errors]"
close $status
if {$wns < 0.0 || $whs < 0.0 || $unrouted != 0 || $partial != 0 || [llength $drc_errors] != 0} {
    puts "ERROR: Negedge hold repair did not sign off: WNS=$wns WHS=$whs unrouted=$unrouted partial=$partial DRC=[llength $drc_errors]"
    exit 2
}
set bit_file [file join $run_dir cns2fpga_axku115_jtag_200mhz.bit]
write_bitstream -force $bit_file
puts "AXKU115_JTAG_BITSTREAM_PASS file=$bit_file WNS=$wns WHS=$whs"
exit 0
