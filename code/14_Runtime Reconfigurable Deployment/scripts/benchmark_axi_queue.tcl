# Read-only JTAG AXI throughput probe. Does not change FPGA state.
open_hw_manager
connect_hw_server -url localhost:3121
set targets [get_hw_targets]
if {[llength $targets] != 1} {error "Expected one JTAG target, got $targets"}
set target [lindex $targets 0]
open_hw_target $target
set devices [get_hw_devices -of_objects $target]
if {[llength $devices] != 1 || ![string match -nocase *xcku115* [lindex $devices 0]]} {
    error "Expected one xcku115, got $devices"
}
set device [lindex $devices 0]
current_hw_device $device
refresh_hw_device $device
set axes [get_hw_axis -of_objects $device]
if {[llength $axes] != 1} {error "Expected one JTAG AXI core, got $axes"}
set axis [lindex $axes 0]
reset_hw_axi $axis

set txn [create_hw_axi_txn probe_fixed_burst $axis -type READ \
    -address 00000000 -len 4 -burst FIXED]
set start [clock milliseconds]
set result [catch {run_hw_axi $txn} error_text]
set elapsed [expr {[clock milliseconds] - $start}]
puts "AXI_BURST_RESULT caught=$result message=$error_text elapsed_ms=$elapsed"
puts "AXI_BURST_DATA [string trim [get_property DATA $txn]]"
delete_hw_axi_txn $txn
close_hw_target
disconnect_hw_server
close_hw_manager
