# Read-only Hardware Manager inventory.  No program_hw_devices or register writes.
set exit_code 0
if {[catch {open_hw_manager} err]} {
    puts "PROBE_ERROR open_hw_manager: $err"
    exit 2
}
if {[catch {connect_hw_server -url localhost:3121} err]} {
    puts "PROBE_ERROR connect_hw_server: $err"
    close_hw_manager
    exit 3
}
puts "PROBE_HW_SERVERS [get_hw_servers]"
set targets [get_hw_targets]
puts "PROBE_TARGET_COUNT [llength $targets]"
foreach target $targets {
    puts "PROBE_TARGET $target"
    if {[catch {open_hw_target $target} err]} {
        puts "PROBE_TARGET_ERROR $target: $err"
        set exit_code 4
        continue
    }
    set devices [get_hw_devices]
    puts "PROBE_DEVICE_COUNT $target [llength $devices]"
    foreach device $devices {
        puts "PROBE_DEVICE $device"
        current_hw_device $device
        foreach prop {PART DEVICE_ID IR_LENGTH IS_PROGRAMMED PROGRAM.FILE PROBES.FILE} {
            if {![catch {get_property $prop $device} value]} {
                puts "PROBE_PROPERTY $device $prop $value"
            }
        }
        if {![catch {get_hw_axis -of_objects $device} axis]} {
            puts "PROBE_HW_AXI_COUNT $device [llength $axis]"
        }
    }
    close_hw_target $target
}
disconnect_hw_server
close_hw_manager
exit $exit_code
