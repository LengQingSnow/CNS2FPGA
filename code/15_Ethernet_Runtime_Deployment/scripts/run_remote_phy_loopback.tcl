# Temporary KSZ9031 remote (line-side) loopback for a PC capture.
# The saved register value is restored before closing JTAG.
open_hw_manager
connect_hw_server -url localhost:3121
set targets [get_hw_targets -quiet]
if {[llength $targets] != 1} {error "Expected one JTAG target"}
set target [lindex $targets 0]
open_hw_target $target
set device [lindex [get_hw_devices -of_objects $target] 0]
current_hw_device $device
refresh_hw_device $device
set axis [lindex [get_hw_axis -of_objects $device] 0]
if {$axis eq ""} {error "Missing JTAG AXI core"}
reset_hw_axi $axis
proc axi_read {axis addr} {
    set txn [create_hw_axi_txn loop_rd $axis -type READ -address $addr -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    scan $data %x value
    return $value
}
proc axi_write {axis addr value} {
    set txn [create_hw_axi_txn loop_wr $axis -type WRITE -address $addr -data [format %08X $value] -len 1]
    run_hw_axi $txn
    delete_hw_axi_txn $txn
}
proc mdio_read {axis reg} {
    axi_write $axis 00000080 [expr {(1 << 31) | (1 << 25) | ($reg << 20)}]
    after 5
    set status [axi_read $axis 00000078]
    if {($status & 7) != 2} {error "PHY MDIO read failed"}
    return [expr {[axi_read $axis 0000007c] & 0xffff}]
}
proc mdio_write {axis reg value} {
    axi_write $axis 00000080 [expr {(1 << 31) | (1 << 30) | (1 << 25) | ($reg << 20) | $value}]
    after 5
    set status [axi_read $axis 00000078]
    if {($status & 3) != 2} {error "PHY MDIO write failed"}
}
if {[axi_read $axis 00000000] != 0x434e5352 || [mdio_read $axis 2] != 0x0022} {
    error "Board/PHY identification failed"
}
set original [mdio_read $axis 17]
if {$original & 0x0100} {error "Remote loopback already enabled; refusing to overwrite"}
puts "REMOTE_LOOPBACK_SAVED=[format %04X $original]"
flush stdout
set outcome [catch {
    mdio_write $axis 17 [expr {$original | 0x0100}]
    set check [mdio_read $axis 17]
    if {($check & 0x0100) == 0} {error "Remote loopback bit did not set"}
    puts "REMOTE_LOOPBACK_ACTIVE=[format %04X $check]"
    flush stdout
    after 30000
} error_text]
mdio_write $axis 17 $original
set restored [mdio_read $axis 17]
puts "REMOTE_LOOPBACK_RESTORED=[format %04X $restored]"
flush stdout
if {$restored != $original} {error "PHY loopback restoration failed"}
if {$outcome} {error $error_text}
close_hw_target
disconnect_hw_server
close_hw_manager
