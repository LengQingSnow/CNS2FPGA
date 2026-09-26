# Vivado Hardware Manager: load one locked stimulus, run, and dump raw AXI data.
# Usage:
#   vivado -mode batch -source run_jtag_trial.tcl -tclargs \
#     <trial-directory> <capture-directory> <capture-events:0|1> \
#     ?hw-target-pattern? ?hw-device-pattern? ?hw-axi-pattern?
# The FPGA must already contain the Step 9 JTAG control bitstream.

if {[llength $argv] < 3 || [llength $argv] > 6} {
    error "Usage: <trial-dir> <capture-dir> <capture-events:0|1> ?target-pattern? ?device-pattern? ?axis-pattern?"
}
set trial_dir [file normalize [lindex $argv 0]]
set capture_dir [file normalize [lindex $argv 1]]
set capture_events [lindex $argv 2]
set target_pattern "*"
set device_pattern "*xcku115*"
set axis_pattern "*"
if {[llength $argv] >= 4} {set target_pattern [lindex $argv 3]}
if {[llength $argv] >= 5} {set device_pattern [lindex $argv 4]}
if {[llength $argv] >= 6} {set axis_pattern [lindex $argv 5]}
if {$capture_events ne "0" && $capture_events ne "1"} {
    error "capture-events must be 0 or 1"
}
set stimulus_path [file join $trial_dir stimulus.mem]
if {![file isfile $stimulus_path]} {
    error "Missing stimulus file: $stimulus_path"
}
if {[file exists $capture_dir] && [llength [glob -nocomplain -directory $capture_dir *]] > 0} {
    error "Refusing to overwrite nonempty capture directory: $capture_dir"
}

set input [open $stimulus_path r]
set stimulus [split [string trim [read $input]] "\n"]
close $input
set length [llength $stimulus]
if {$length < 1 || $length > 8192} {
    error "Stimulus length must be in 1..8192, got $length"
}
foreach hex $stimulus {
    set hex [string trim $hex]
    if {![regexp {^[0-9A-Fa-f]{9}$} $hex]} {
        error "Stimulus must contain exactly one 9-digit hex current per line"
    }
}

open_hw_manager
connect_hw_server -url localhost:3121
set targets {}
foreach item [get_hw_targets] {
    if {[string match $target_pattern $item]} {lappend targets $item}
}
if {[llength $targets] != 1} {
    error "Expected exactly one JTAG target matching '$target_pattern'; got $targets"
}
set target [lindex $targets 0]
open_hw_target $target
set devices {}
foreach item [get_hw_devices -of_objects $target] {
    if {[string match -nocase $device_pattern $item]} {lappend devices $item}
}
if {[llength $devices] != 1} {
    error "Expected exactly one KU115 matching '$device_pattern'; got $devices"
}
set device [lindex $devices 0]
current_hw_device $device
refresh_hw_device $device
set axes {}
foreach item [get_hw_axis -of_objects $device] {
    if {[string match $axis_pattern $item]} {lappend axes $item}
}
if {[llength $axes] != 1} {
    error "Expected exactly one JTAG AXI core matching '$axis_pattern'; got $axes"
}
set axis [lindex $axes 0]
puts "STEP9_TARGET $target"
puts "STEP9_DEVICE $device"
puts "STEP9_AXI $axis"
reset_hw_axi $axis

# Single-word transactions are valid for AXI4 and AXI4-Lite. Verify each
# AXI response explicitly; Tcl command success alone does not imply OKAY.
proc check_axi_response {kind address} {
    global axis
    if {$kind eq "READ"} {
        set busy [get_property STATUS.AXI_READ_BUSY $axis]
        set done [get_property STATUS.AXI_READ_DONE $axis]
        set resp [get_property STATUS.RRESP $axis]
    } else {
        set busy [get_property STATUS.AXI_WRITE_BUSY $axis]
        set done [get_property STATUS.AXI_WRITE_DONE $axis]
        set resp [get_property STATUS.BRESP $axis]
    }
    if {[string is true -strict $busy] || ![string is true -strict $done] ||
        ![string equal -nocase $resp "OKAY"]} {
        error "$kind AXI error at [format %08X $address]: busy='$busy' done='$done' response='$resp'"
    }
}
proc read_word {address} {
    global axis
    set txn [create_hw_axi_txn step9_read $axis -type READ -address [format %08X $address] -len 1]
    run_hw_axi $txn
    check_axi_response READ $address
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {
        error "Unexpected JTAG AXI DATA at [format %08X $address]: '$data'"
    }
    scan $data %x value
    return [expr {$value & 0xFFFFFFFF}]
}

proc write_word {address value} {
    global axis
    set txn [create_hw_axi_txn step9_write $axis -type WRITE \
        -address [format %08X $address] -data [format %08X $value] -len 1]
    run_hw_axi $txn
    check_axi_response WRITE $address
    delete_hw_axi_txn $txn
}

set id [read_word 0x0000]
if {$id != 0x434E5339} {
    error "Firmware ID mismatch: got [format %08X $id], expected CNS9 (434E5339)"
}
set status [read_word 0x0008]
if {$status & 0x1} {
    error "The board is already running a trial (STATUS=[format %08X $status])"
}

write_word 0x000C $length
write_word 0x0010 200000
write_word 0x002C $capture_events
puts "STEP9_LOADING timesteps=$length capture_events=$capture_events"
set step 0
foreach hex $stimulus {
    set raw [expr 0x$hex]
    set low [expr {$raw & 0xFFFFFFFF}]
    set high [expr {($raw >> 32) & 0x3}]
    write_word [expr {0x10000 + $step * 8}] $low
    write_word [expr {0x10000 + $step * 8 + 4}] $high
    incr step
    if {$step % 512 == 0} {puts "STEP9_LOADED $step/$length"}
}
puts "STEP9_LOADED $length/$length"

# Check first/last words and one nonzero pulse before starting the core.
set check_steps [list 0 [expr {$length - 1}]]
set step 0
foreach hex $stimulus {
    if {$hex ne "000000000"} {
        lappend check_steps $step
        break
    }
    incr step
}
foreach step [lsort -integer -unique $check_steps] {
    set expected [expr 0x[lindex $stimulus $step]]
    set low [read_word [expr {0x10000 + $step * 8}]]
    set high [read_word [expr {0x10000 + $step * 8 + 4}]]
    set actual [expr {($high & 3) << 32 | ($low & 0xFFFFFFFF)}]
    if {$expected != $actual} {
        error "Stimulus readback mismatch at step $step: [format %09X $actual] != [format %09X $expected]"
    }
}

write_word 0x0004 1
set complete 0
for {set attempt 0} {$attempt < 1000} {incr attempt} {
    set status [read_word 0x0008]
    if {$status & 0x2} {
        set complete 1
        break
    }
    after 20
}
if {!$complete} {
    error "Trial did not complete within polling timeout; STATUS=[format %08X $status]"
}
set completed [read_word 0x0014]
if {$completed != $length} {
    error "Completed step count $completed differs from requested $length"
}
set global_events [read_word 0x0018]
if {$capture_events && $global_events > 65536} {
    error "Global event count $global_events exceeds 65536-event BRAM"
}

file mkdir $capture_dir
set registers [open [file join $capture_dir registers.csv] w]
puts $registers "name,hex32"
foreach {name address} {
    ID 0x0000 STATUS 0x0008 LENGTH 0x000C PERIOD_CYCLES 0x0010
    COMPLETED_STEPS 0x0014 GLOBAL_EVENT_COUNT 0x0018 MISSED_STEPS 0x001C
    MAX_LATENCY 0x0020 TOTAL_SYNOPS_LOW 0x0024 TOTAL_SYNOPS_HIGH 0x0028 CONFIG 0x002C
} {
    puts $registers "$name,[format %08X [read_word $address]]"
}
close $registers

set summary_file [open [file join $capture_dir summary_words.hex] w]
for {set word 0} {$word < $length * 8} {incr word} {
    puts $summary_file [format %08X [read_word [expr {0x20000 + $word * 4}]]]
    if {$word % 4096 == 4095} {puts "STEP9_SUMMARY_READ [expr {$word + 1}]/[expr {$length * 8}]"}
}
close $summary_file

if {$capture_events} {
    set event_file [open [file join $capture_dir event_words.hex] w]
    for {set event 0} {$event < $global_events} {incr event} {
        puts $event_file [format %08X [read_word [expr {0x60000 + $event * 4}]]]
        if {$event % 4096 == 4095} {puts "STEP9_EVENTS_READ [expr {$event + 1}]/$global_events"}
    }
    close $event_file
}
puts "STEP9_COMPLETE timesteps=$completed events=$global_events status=[format %08X $status] capture=$capture_dir"
close_hw_target
disconnect_hw_server
close_hw_manager
