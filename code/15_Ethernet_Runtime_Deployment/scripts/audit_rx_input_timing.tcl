# Read-only post-route timing audit for the RGMII receive input paths.
# Usage: vivado -mode batch -source audit_rx_input_timing.tcl -tclargs DCP REPORT_PREFIX
if {$argc != 2} {
    error "usage: audit_rx_input_timing.tcl DCP REPORT_PREFIX"
}
set dcp [file normalize [lindex $argv 0]]
set prefix [file normalize [lindex $argv 1]]
open_checkpoint $dcp
set rxports [get_ports {phy_rxd[*] phy_rx_ctl}]
puts "AUDIT_DCP=$dcp"
puts "AUDIT_RX_PORTS=[join $rxports ,]"
foreach delay_type {max min} {
    set paths [get_timing_paths -from $rxports -delay_type $delay_type -max_paths 10]
    puts "AUDIT_${delay_type}_PATH_COUNT=[llength $paths]"
    if {[llength $paths] > 0} {
        set worst [lindex $paths 0]
        puts "AUDIT_${delay_type}_WORST_SLACK=[get_property SLACK $worst]"
        puts "AUDIT_${delay_type}_WORST_START=[get_property STARTPOINT_PIN $worst]"
        puts "AUDIT_${delay_type}_WORST_END=[get_property ENDPOINT_PIN $worst]"
    }
    report_timing -from $rxports -delay_type $delay_type -max_paths 10 -path_type full_clock_expanded -file "${prefix}_${delay_type}.rpt"
}
puts "AUDIT_DONE=$prefix"
