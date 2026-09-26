`timescale 1ns/1ps

module tb_bit_exact_250mhz;
    localparam integer N = 6279;
    localparam integer STEPS = 8;
    localparam integer FLAT = N * STEPS;

    reg clk = 1'b0;
    reg rst = 1'b1;
    reg start_timestep = 1'b0;
    reg signed [33:0] input_current = 0;
    wire busy, timestep_done, spike_valid, spike_is_pC1;
    wire [12:0] spike_neuron;
    wire state_saturation_seen, accumulator_saturation_seen;
    reg signed [33:0] stimulus [0:STEPS-1];
    reg signed [33:0] expected_voltage [0:FLAT-1];
    reg signed [34:0] expected_syn_current [0:FLAT-1];
    reg [7:0] expected_refractory [0:FLAT-1];
    reg expected_spike [0:FLAT-1];
    reg actual_spike [0:N-1];
    integer timestep, index, errors, actual_spike_count, expected_spike_count;
    integer cycle_counter, step_start_cycle, summary_file;

    always #2 clk = ~clk;
    always @(posedge clk) begin
        cycle_counter = cycle_counter + 1;
        if (spike_valid) begin
            actual_spike[spike_neuron] = 1'b1;
            actual_spike_count = actual_spike_count + 1;
        end
    end

    cns2fpga_core_sync #(
        .NEURON_COUNT(N), .SYNAPSE_COUNT(350185), .NEURON_INDEX_BITS(13),
        .STATE_BITS(34), .STATE_FRAC(24), .WEIGHT_BITS(30), .WEIGHT_FRAC(24),
        .DECAY_BITS(32), .DECAY_FRAC(30), .ACC_BITS(35),
        .NEURON_PARAM_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/neuron_param.mem"),
        .SYNAPSE_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/synapse.mem"),
        .OFFSET_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/offset.mem"),
        .TYPE_SIGN_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/type_sign.mem")
    ) dut (
        .clk(clk), .rst(rst), .clear_state(1'b0), .start_timestep(start_timestep), .input_current(input_current),
        .busy(busy), .timestep_done(timestep_done), .spike_valid(spike_valid),
        .spike_neuron(spike_neuron), .spike_is_pC1(spike_is_pC1),
        .spike_group_flags(), .clear_done(), .synapse_op_valid(),
        .state_saturation_seen(state_saturation_seen),
        .accumulator_saturation_seen(accumulator_saturation_seen)
    );

    task compare_step;
        input integer step_number;
        integer flat_index;
        begin
            errors = 0;
            expected_spike_count = 0;
            for (index = 0; index < N; index = index + 1) begin
                flat_index = step_number * N + index;
                if (dut.voltage_mem[index] !== expected_voltage[flat_index]) errors = errors + 1;
                if (dut.syn_current_mem[index] !== expected_syn_current[flat_index]) errors = errors + 1;
                if (dut.refractory_mem[index] !== expected_refractory[flat_index]) errors = errors + 1;
                if (actual_spike[index] !== expected_spike[flat_index]) errors = errors + 1;
                if (expected_spike[flat_index]) expected_spike_count = expected_spike_count + 1;
            end
            $fdisplay(summary_file, "%0d,%0d,%0d,%0d,%0d", step_number,
                      cycle_counter-step_start_cycle, actual_spike_count,
                      expected_spike_count, errors);
            if (errors != 0 || actual_spike_count != expected_spike_count) begin
                $display("FAIL timestep=%0d errors=%0d rtl_spikes=%0d cpu_spikes=%0d",
                         step_number, errors, actual_spike_count, expected_spike_count);
                $finish;
            end
            if (state_saturation_seen || accumulator_saturation_seen) begin
                $display("FAIL saturation at timestep=%0d", step_number);
                $finish;
            end
            $display("PASS timestep=%0d cycles=%0d spikes=%0d exact_state_neurons=%0d",
                     step_number, cycle_counter-step_start_cycle, actual_spike_count, N);
        end
    endtask

    initial begin
        $readmemh("../8_RTL Bit-Exact Co-Simulation/sim/reference/full_network_8step_v1/stimulus.mem", stimulus);
        $readmemh("../8_RTL Bit-Exact Co-Simulation/sim/reference/full_network_8step_v1/expected_voltage.mem", expected_voltage);
        $readmemh("../8_RTL Bit-Exact Co-Simulation/sim/reference/full_network_8step_v1/expected_syn_current.mem", expected_syn_current);
        $readmemh("../8_RTL Bit-Exact Co-Simulation/sim/reference/full_network_8step_v1/expected_refractory.mem", expected_refractory);
        $readmemh("../8_RTL Bit-Exact Co-Simulation/sim/reference/full_network_8step_v1/expected_spike.mem", expected_spike);
        summary_file = $fopen("sim/rtl_step_summary_250mhz.csv", "w");
        $fdisplay(summary_file, "timestep,cycles,rtl_spikes,cpu_spikes,mismatches");
        cycle_counter = 0;
        repeat (3) @(negedge clk);
        rst = 1'b0;
        for (timestep = 0; timestep < STEPS; timestep = timestep + 1) begin
            actual_spike_count = 0;
            for (index = 0; index < N; index = index + 1) actual_spike[index] = 1'b0;
            @(negedge clk);
            input_current = stimulus[timestep];
            start_timestep = 1'b1;
            step_start_cycle = cycle_counter;
            @(negedge clk);
            start_timestep = 1'b0;
            wait (timestep_done === 1'b1);
            @(negedge clk);
            compare_step(timestep);
        end
        $fclose(summary_file);
        $display("PASS BIT-EXACT 250MHz-pipelined full-network timesteps=%0d neurons=%0d", STEPS, N);
        $finish;
    end

    initial begin
        #100000000;
        $display("FAIL timeout");
        $finish;
    end
endmodule
