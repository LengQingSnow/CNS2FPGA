# Vivado Hardware Manager loader for the CNSR firmware. The FPGA must already
# contain the runtime bitstream. Run prepare_image.py before this script.
# Usage: vivado -mode batch -source load_runtime_image.tcl -tclargs
#        <image-dir> <neurons> <synapses> <checksum-8-hex>
#        ?target-pattern? ?device-pattern? ?axi-pattern?

if {[llength $argv] < 4 || [llength $argv] > 7} {
    error "Usage: image-dir neurons synapses checksum ?target? ?device? ?axis?"
}
set image_dir [file normalize [lindex $argv 0]]
set neurons [lindex $argv 1]
set synapses [lindex $argv 2]
set checksum_text [lindex $argv 3]
if {![string is integer -strict $neurons] || $neurons < 1 || $neurons > 6279 ||
    ![string is integer -strict $synapses] || $synapses < 0 || $synapses > 350185 ||
    ![regexp {^[0-9A-Fa-f]{8}$} $checksum_text]} {
    error "Invalid counts or checksum"
}
scan $checksum_text %x expected_checksum
set target_pattern "*"
set device_pattern "*xcku115*"
set axis_pattern "*"
if {[llength $argv] >= 5} {set target_pattern [lindex $argv 4]}
if {[llength $argv] >= 6} {set device_pattern [lindex $argv 5]}
if {[llength $argv] >= 7} {set axis_pattern [lindex $argv 6]}

open_hw_manager
connect_hw_server -url localhost:3121
set targets {}
foreach item [get_hw_targets] {
    if {[string match $target_pattern $item]} {lappend targets $item}
}
if {[llength $targets] != 1} {error "Expected exactly one JTAG target, got $targets"}
set target [lindex $targets 0]
open_hw_target $target
set devices {}
foreach item [get_hw_devices -of_objects $target] {
    if {[string match -nocase $device_pattern $item]} {lappend devices $item}
}
if {[llength $devices] != 1} {error "Expected exactly one KU115, got $devices"}
set device [lindex $devices 0]
current_hw_device $device
refresh_hw_device $device
set axes {}
foreach item [get_hw_axis -of_objects $device] {
    if {[string match $axis_pattern $item]} {lappend axes $item}
}
if {[llength $axes] != 1} {error "Expected exactly one JTAG AXI core, got $axes"}
set axis [lindex $axes 0]
reset_hw_axi $axis

proc check_response {kind address} {
    global axis
    if {$kind eq "READ"} {
        set busy [get_property STATUS.AXI_READ_BUSY $axis]
        set done [get_property STATUS.AXI_READ_DONE $axis]
        set response [get_property STATUS.RRESP $axis]
    } else {
        set busy [get_property STATUS.AXI_WRITE_BUSY $axis]
        set done [get_property STATUS.AXI_WRITE_DONE $axis]
        set response [get_property STATUS.BRESP $axis]
    }
    if {[string is true -strict $busy] || ![string is true -strict $done] ||
        ![string equal -nocase $response "OKAY"]} {
        error "$kind AXI failure at [format %08X $address]: $response"
    }
}
proc read_word {address} {
    global axis
    set txn [create_hw_axi_txn runtime_read $axis -type READ -address [format %08X $address] -len 1]
    run_hw_axi $txn
    check_response READ $address
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {error "Invalid AXI readback: $data"}
    scan $data %x value
    return [expr {$value & 0xFFFFFFFF}]
}
proc write_word {address value} {
    global axis
    set txn [create_hw_axi_txn runtime_write $axis -type WRITE \
        -address [format %08X $address] -data [format %08X $value] -len 1]
    run_hw_axi $txn
    check_response WRITE $address
    delete_hw_axi_txn $txn
}

set ident [read_word 0x00000]
if {$ident != 0x434E5352} {
    error "Wrong bitstream: firmware ID [format %08X $ident], expected CNSR"
}
if {[read_word 0x00068] != 6279 || [read_word 0x0006C] != 350185} {
    error "Unexpected firmware graph capacity"
}
if {[read_word 0x00008] & 1} {error "Trial is running; cannot reload image"}
set previous_epoch [read_word 0x0004C]
write_word 0x00030 1
write_word 0x00034 $neurons
write_word 0x00038 $synapses

set total_words 0
set rolling_checksum 0
set region_names {neuron_param synapse offset type_sign}
set region_widths {32 16 8 4}
set region_lanes {4 2 1 1}
for {set region 0} {$region < 4} {incr region} {
    set name [lindex $region_names $region]
    set width [lindex $region_widths $region]
    set lanes [lindex $region_lanes $region]
    set expected_records [expr {$region == 1 ? $synapses : $neurons}]
    set path [file join $image_dir "$name.mem"]
    if {![file isfile $path]} {error "Missing $path"}
    write_word 0x0003C $region
    set input [open $path r]
    set records 0
    while {[gets $input line] >= 0} {
        set line [string trim $line]
        if {[string length $line] != $width || ![regexp {^[0-9A-Fa-f]+$} $line]} {
            close $input
            error "Malformed $path record [expr {$records + 1}]"
        }
        incr records
        if {$records > $expected_records} {
            close $input
            error "Too many records in $path"
        }
        # Each compiler record is hexadecimal MSB first. Send 32-bit lanes
        # LSB first, exactly as the hardware write port expects.
        for {set lane 0} {$lane < $lanes} {incr lane} {
            if {$region == 3} {
                scan $line %x word
            } else {
                set start [expr {$width - 8 * ($lane + 1)}]
                scan [string range $line $start [expr {$start + 7}]] %x word
            }
            set word [expr {$word & 0xFFFFFFFF}]
            write_word 0x00040 $word
            set rolling_checksum [expr {((($rolling_checksum << 1) |
                (($rolling_checksum >> 31) & 1)) ^ $word ^ $region) & 0xFFFFFFFF}]
            incr total_words
            if {$total_words % 8192 == 0} {
                set status [read_word 0x00030]
                if {$status & 4} {error "Firmware rejected image data: [format %08X $status]"}
                puts "RUNTIME_UPLOAD_PROGRESS words=$total_words region=$name"
            }
        }
    }
    close $input
    if {$records != $expected_records} {
        error "Record count mismatch in $path: $records != $expected_records"
    }
    set counter_address [expr {0x00050 + 4 * $region}]
    if {[read_word $counter_address] != $records * $lanes} {
        error "Firmware word counter mismatch for $name"
    }
}
if {$rolling_checksum != $expected_checksum} {
    error "Image changed after preflight: calculated [format %08X $rolling_checksum], expected [format %08X $expected_checksum]"
}
write_word 0x00044 $expected_checksum
write_word 0x00030 2
set status [read_word 0x00030]
if {$status != 1} {error "Firmware COMMIT failed: status=[format %08X $status]"}
if {[read_word 0x00048] != $expected_checksum ||
    [read_word 0x00060] != $neurons || [read_word 0x00064] != $synapses ||
    [read_word 0x0004C] != (($previous_epoch + 1) & 0xFFFFFFFF)} {
    error "Firmware readback mismatch after COMMIT"
}
puts "RUNTIME_IMAGE_PASS neurons=$neurons synapses=$synapses words=$total_words checksum=[format %08X $expected_checksum] epoch=[read_word 0x0004C]"
close_hw_target
disconnect_hw_server
close_hw_manager
