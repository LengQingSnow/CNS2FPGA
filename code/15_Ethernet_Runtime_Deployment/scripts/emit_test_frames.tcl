# Emit four Ethernet broadcast test frames from the FPGA and verify MAC counts.
# Register 0xA0 toggles the on-board generator; 0x8C counts accepted frames.
open_hw_manager
connect_hw_server -url localhost:3121
set targets [get_hw_targets -quiet]
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
proc rd {axis address} {
    set txn [create_hw_axi_txn probe_read $axis -type READ -address $address -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {error "Invalid AXI readback: $data"}
    scan $data %x value
    return $value
}
proc wr {axis address value} {
    set txn [create_hw_axi_txn probe_write $axis -type WRITE -address $address -data [format %08X $value] -len 1]
    run_hw_axi $txn
    delete_hw_axi_txn $txn
}
if {[rd $axis 00000000] != 0x434e5352} {error "Unexpected runtime ID"}
set before [rd $axis 0000008c]
puts "TEST_FRAME_COUNT_BEFORE=$before"
for {set i 0} {$i < 4} {incr i} {
    wr $axis 000000a0 1
    after 200
}
set after_count [rd $axis 0000008c]
set tx_counts [rd $axis 00000088]
set status [rd $axis 00000070]
puts "TEST_FRAME_COUNT_AFTER=$after_count"
puts "TEST_FRAME_TX_COUNTS=[format %08X $tx_counts]"
puts "TEST_FRAME_STATUS=[format %08X $status]"
if {$after_count != $before + 4} {error "Test frame generator did not accept four frames"}
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
