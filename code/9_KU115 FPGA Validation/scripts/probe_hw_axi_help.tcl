load_features labtools
foreach cmd {get_hw_axis create_hw_axi_txn run_hw_axi report_hw_axi_txn delete_hw_axi_txn} {
    puts "HELP_BEGIN $cmd"
    if {[catch {help $cmd} value]} {
        puts "HELP_ERROR $cmd $value"
    } else {
        puts $value
    }
    puts "HELP_END $cmd"
}
exit 0
