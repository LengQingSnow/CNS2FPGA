transcript file sim/transcript.log
if {[file exists work]} {vdel -lib work -all}
vlib work
vlog -sv rtl/cns2fpga_core.sv sim/tb_cns2fpga_core.sv
vsim -c work.tb_cns2fpga_core -do "run -all; quit -f"
