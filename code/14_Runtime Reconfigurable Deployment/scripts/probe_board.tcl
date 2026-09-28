# Read-only JTAG inventory before programming the runtime image.
open_hw_manager
connect_hw_server -url localhost:3121
refresh_hw_server [get_hw_servers]
set targets [get_hw_targets -quiet]
puts "JTAG_TARGETS=$targets"
foreach target $targets {
    open_hw_target $target
    set devices [get_hw_devices -of_objects $target]
    puts "JTAG_TARGET=$target DEVICES=$devices"
    foreach device $devices {
        puts "JTAG_DEVICE=$device PART=[get_property PART $device]"
    }
    close_hw_target
}
disconnect_hw_server
close_hw_manager
exit 0
