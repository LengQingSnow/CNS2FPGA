open_checkpoint [file normalize "code/15_Ethernet_Runtime_Deployment/build/runtime_eth_200mhz/post_route.dcp"]
set cells [get_cells -hier -filter {REF_NAME == IDELAYE3}]
puts "IDELAY_COUNT=[llength $cells]"
foreach cell $cells {
    puts "IDELAY=$cell FORMAT=[get_property DELAY_FORMAT $cell] VALUE=[get_property DELAY_VALUE $cell] TYPE=[get_property DELAY_TYPE $cell] REFCLK=[get_property REFCLK_FREQUENCY $cell]"
}
