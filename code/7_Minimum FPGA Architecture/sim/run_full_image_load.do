transcript file sim/full_image_load.log
if {[file exists work]} {vdel -lib work -all}
vlib work
vlog -sv rtl/cns2fpga_core.sv sim/tb_full_image_load.sv
vsim -c work.tb_full_image_load -do "run -all; quit -f"
