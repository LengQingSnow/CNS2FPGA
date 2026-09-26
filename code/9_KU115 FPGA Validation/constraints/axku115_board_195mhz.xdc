# AXKU115 V1.0 pinout from AXKU115_UG.pdf.
# The single-ended 50 MHz oscillator is used to avoid assuming the SI5332
# differential output electrical standard.
set_property PACKAGE_PIN AL14 [get_ports clk_50m]
set_property IOSTANDARD LVCMOS33 [get_ports clk_50m]
create_clock -name clk_50m -period 20.000 -waveform {0.000 10.000} [get_ports clk_50m]

# User keys are active low and connect to BANK24.
set_property PACKAGE_PIN AL33 [get_ports key1_n]
set_property PACKAGE_PIN AG30 [get_ports key2_n]
set_property IOSTANDARD LVCMOS18 [get_ports {key1_n key2_n}]
set_property PULLUP true [get_ports {key1_n key2_n}]

# User LEDs are active high through board-level transistor drivers on BANK44.
set_property PACKAGE_PIN AH21 [get_ports led1]
set_property PACKAGE_PIN AJ23 [get_ports led2]
set_property IOSTANDARD LVCMOS18 [get_ports {led1 led2}]
set_property DRIVE 8 [get_ports {led1 led2}]
set_property SLEW SLOW [get_ports {led1 led2}]

# KEY inputs are synchronized internally; LEDs are human-visible status only.
set_false_path -from [get_ports {key1_n key2_n}]
set_false_path -to [get_ports {led1 led2}]

# Keep the same conservative internal margin used for OOC closure.
set_clock_uncertainty 0.200 [get_clocks -of_objects [get_pins system_clock_buffer/O]]

set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
