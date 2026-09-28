# Read-only independent check after the UDP uploader has closed its socket.
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
proc read_word {axis address} {
    set txn [create_hw_axi_txn image_verify $axis -type READ -address [format %08X $address] -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {error "Invalid readback at $address: $data"}
    scan $data %x value
    return $value
}
if {[read_word $axis 0x00] != 0x434e5352} {error "Unexpected runtime identity"}
set status [read_word $axis 0x30]
set neurons [read_word $axis 0x60]
set synapses [read_word $axis 0x64]
set expected [read_word $axis 0x44]
set actual [read_word $axis 0x48]
set epoch [read_word $axis 0x4c]
set errors [read_word $axis 0xa4]
set flow_counts [read_word $axis 0xac]
set overflow [expr {($flow_counts >> 16) & 0xffff}]
puts "UDP_IMAGE_JTAG_READBACK status=[format %08X $status] neurons=$neurons synapses=$synapses expected=[format %08X $expected] actual=[format %08X $actual] epoch=$epoch errors=[format %08X $errors] rx_overflow=$overflow"
if {$status != 1 || $neurons != 6279 || $synapses != 350185 ||
    $expected != 0x45AEAAAE || $actual != 0x45AEAAAE || $epoch != 2 ||
    $errors != 0 || $overflow != 0} {
    error "Courtship UDP image JTAG readback mismatch"
}
puts "COURTSHIP_UDP_JTAG_VERIFY_PASS"
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
