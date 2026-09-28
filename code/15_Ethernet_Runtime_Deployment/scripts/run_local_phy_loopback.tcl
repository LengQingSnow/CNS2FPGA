# Temporary KSZ9031RNX MAC-side digital loopback.  Restores PHY registers.
# This interrupts the external link briefly and tests FPGA TX -> PHY -> FPGA RX.
open_hw_manager
connect_hw_server -url localhost:3121
set targets [get_hw_targets -quiet]
if {[llength $targets] != 1} {error "Expected one JTAG target"}
set target [lindex $targets 0]
open_hw_target $target
set devices [get_hw_devices -of_objects $target]
if {[llength $devices] != 1 || ![string match -nocase *xcku115* [lindex $devices 0]]} {
    error "Expected one xcku115"
}
set device [lindex $devices 0]
current_hw_device $device
refresh_hw_device $device
set axes [get_hw_axis -of_objects $device]
if {[llength $axes] != 1} {error "Expected one JTAG AXI core"}
set axis [lindex $axes 0]
reset_hw_axi $axis
proc rd {axis address} {
    set txn [create_hw_axi_txn loop_read $axis -type READ -address $address -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {error "Invalid AXI readback: $data"}
    scan $data %x value
    return $value
}
proc wr {axis address value} {
    set txn [create_hw_axi_txn loop_write $axis -type WRITE -address $address -data [format %08X $value] -len 1]
    run_hw_axi $txn
    delete_hw_axi_txn $txn
}
proc phy_read {axis reg} {
    wr $axis 00000080 [expr {(1 << 31) | (1 << 25) | ($reg << 20)}]
    after 5
    if {([rd $axis 00000078] & 7) != 2} {error "PHY read failed for $reg"}
    return [expr {[rd $axis 0000007c] & 0xffff}]
}
proc phy_write {axis reg value} {
    wr $axis 00000080 [expr {(1 << 31) | (1 << 30) | (1 << 25) | ($reg << 20) | $value}]
    after 5
    if {([rd $axis 00000078] & 3) != 2} {error "PHY write failed for $reg"}
}
if {[rd $axis 00000000] != 0x434e5352 || [phy_read $axis 2] != 0x0022} {
    error "Board/PHY identification failed"
}
set bmcr [phy_read $axis 0]
set ctrl1000 [phy_read $axis 9]
if {$bmcr & 0x4000} {error "PHY already in local loopback; refusing to overwrite"}
puts "LOCAL_LOOPBACK_SAVED_BMCR=[format %04X $bmcr] CTRL1000=[format %04X $ctrl1000]"
flush stdout
set result [catch {
    # Datasheet 3.13.1: 1 Gbps full-duplex, autoneg off, manual slave.
    phy_write $axis 0 0x4140
    phy_write $axis 9 [expr {($ctrl1000 | 0x1000) & ~0x0800}]
    after 500
    puts "LOCAL_LOOPBACK_ACTIVE_BMCR=[format %04X [phy_read $axis 0]] CTRL1000=[format %04X [phy_read $axis 9]]"
    set rx_before [rd $axis 00000084]
    set tx_before [rd $axis 00000088]
    set test_before [rd $axis 0000008c]
    puts "LOCAL_LOOPBACK_COUNTS_BEFORE rx=[format %08X $rx_before] tx=[format %08X $tx_before] test=$test_before"
    for {set i 0} {$i < 4} {incr i} {
        wr $axis 000000a0 1
        after 100
    }
    set rx_after [rd $axis 00000084]
    set tx_after [rd $axis 00000088]
    set test_after [rd $axis 0000008c]
    set status [rd $axis 00000070]
    puts "LOCAL_LOOPBACK_COUNTS_AFTER rx=[format %08X $rx_after] tx=[format %08X $tx_after] test=$test_after status=[format %08X $status]"
    if {$test_after != $test_before + 4} {error "Generator did not send four frames"}
    if {($rx_after >> 16) - ($rx_before >> 16) < 3} {
        error "PHY did not loop back three valid frames to FPGA MAC"
    }
} failure]
set restore_error [catch {
    phy_write $axis 9 $ctrl1000
    # Re-enable and explicitly restart autonegotiation after forced loopback.
    phy_write $axis 0 [expr {$bmcr | 0x0200}]
    after 3000
    set bmcr_restored [phy_read $axis 0]
    set ctrl1000_restored [phy_read $axis 9]
    puts "LOCAL_LOOPBACK_RESTORED_BMCR=[format %04X $bmcr_restored] CTRL1000=[format %04X $ctrl1000_restored]"
    if {($bmcr_restored & ~0x0200) != $bmcr || $ctrl1000_restored != $ctrl1000} {
        error "PHY configuration did not restore"
    }
} restore_failure]
flush stdout
if {$restore_error} {error $restore_failure}
if {$result} {error $failure}
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
