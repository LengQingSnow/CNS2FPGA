set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set checkpoint [file join $root_dir build runtime_eth_200mhz post_route_ethernet_eco.dcp]
set report [file join $root_dir reports runtime_eth_200mhz eco_bus_skew.rpt]
if {![file isfile $checkpoint]} {error "Missing finalized checkpoint: $checkpoint"}
open_checkpoint $checkpoint
report_bus_skew -file $report
puts "RUNTIME_ETH_BUS_SKEW_REPORT=$report"
exit 0
