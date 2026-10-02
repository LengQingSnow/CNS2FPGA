# Physical negative test for the already programmed CNSR runtime bitstream.
# Run phase "interrupt" in one Vivado process, then phase "reject" in a
# separate process. This deliberately invalidates the active image; reload a
# fully preflighted image afterwards. No FPGA programming is performed here.
if {[llength $argv] != 2} {error "Usage: interrupt|reject expected_epoch"}
set phase [lindex $argv 0]
set expected_epoch [lindex $argv 1]
if {$phase ne "interrupt" && $phase ne "reject"} {error "Invalid phase: $phase"}
if {![string is integer -strict $expected_epoch] || $expected_epoch < 1} {
    error "Invalid expected epoch: $expected_epoch"
}

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

proc axi_read {address} {
    global axis
    set txn [create_hw_axi_txn p0_fault_read $axis -type READ -address [format %08X $address] -len 1]
    run_hw_axi $txn
    set response [get_property STATUS.RRESP $axis]
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![string equal -nocase $response OKAY] || ![regexp {^[0-9A-Fa-f]{8}$} $data]} {
        error "AXI READ failed at [format %08X $address]: $response $data"
    }
    scan $data %x value
    return [expr {$value & 0xFFFFFFFF}]
}
proc axi_write {address value} {
    global axis
    set txn [create_hw_axi_txn p0_fault_write $axis -type WRITE \
        -address [format %08X $address] -data [format %08X $value] -len 1]
    run_hw_axi $txn
    set response [get_property STATUS.BRESP $axis]
    delete_hw_axi_txn $txn
    if {![string equal -nocase $response OKAY]} {
        error "AXI WRITE failed at [format %08X $address]: $response"
    }
}

if {[axi_read 0x00] != 0x434E5352} {error "Wrong firmware ID"}
if {[axi_read 0x4C] != $expected_epoch} {error "Unexpected image epoch"}
if {$phase eq "interrupt"} {
    if {[axi_read 0x30] != 1} {error "Expected a committed image before interruption"}
    axi_write 0x30 1
    axi_write 0x34 226
    axi_write 0x38 1730
    axi_write 0x3C 0
    axi_write 0x40 0
    set status [axi_read 0x30]
    if {$status != 2 || [axi_read 0x50] != 1 || [axi_read 0x4C] != $expected_epoch} {
        error "Partial image state mismatch: status=[format %08X $status]"
    }
    puts "P0_JTAG_INTERRUPTED_PASS status=[format %08X $status] epoch=$expected_epoch words=1"
} else {
    if {[axi_read 0x30] != 2 || [axi_read 0x50] != 1} {
        error "Interrupted image did not persist across host reconnect"
    }
    axi_write 0x30 2
    set incomplete_status [axi_read 0x30]
    if {$incomplete_status != 0x16 || [axi_read 0x4C] != $expected_epoch} {
        error "Incomplete image was not rejected: [format %08X $incomplete_status]"
    }
    puts "P0_JTAG_INCOMPLETE_REJECT_PASS status=[format %08X $incomplete_status] epoch=$expected_epoch"

    # A fresh BEGIN clears the prior error. A target index equal to the
    # neuron count is out of range and must be rejected before graph RAM write.
    axi_write 0x30 1
    axi_write 0x34 226
    axi_write 0x38 1730
    axi_write 0x3C 1
    axi_write 0x40 226
    set bad_post_status [axi_read 0x30]
    if {$bad_post_status != 0x66 || [axi_read 0x54] != 0 ||
        [axi_read 0x4C] != $expected_epoch} {
        error "Invalid post index was not rejected: [format %08X $bad_post_status]"
    }
    puts "P0_JTAG_BAD_POST_REJECT_PASS status=[format %08X $bad_post_status] epoch=$expected_epoch"
}
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
