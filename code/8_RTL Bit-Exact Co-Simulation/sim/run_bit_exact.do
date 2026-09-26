transcript file sim/bit_exact_transcript.log
if {[file exists work]} {vdel -lib work -all}
vlib work
vlog -sv rtl/cns2fpga_core_sync.sv sim/tb_bit_exact_full.sv
vsim -c work.tb_bit_exact_full -do "run -all; quit -f"
