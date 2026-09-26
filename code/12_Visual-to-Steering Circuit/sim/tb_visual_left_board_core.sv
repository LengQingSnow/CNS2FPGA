`timescale 1ns/1ps

module tb_visual_left_board_core;
    localparam integer N = 226;
    localparam integer STEPS = 8;
    localparam integer FLAT = N * STEPS;
    reg clk = 0, rst = 1, start_timestep = 0;
    reg signed [33:0] input_current = 0;
    wire busy, timestep_done, spike_valid, spike_is_pC1;
    wire [12:0] spike_neuron;
    wire state_saturation_seen, accumulator_saturation_seen;
    wire clear_done, synapse_op_valid;
    wire [4:0] spike_group_flags;
    reg signed [33:0] stimulus [0:STEPS-1];
    reg signed [33:0] expected_voltage [0:FLAT-1];
    reg signed [34:0] expected_syn_current [0:FLAT-1];
    reg [7:0] expected_refractory [0:FLAT-1];
    reg expected_spike [0:FLAT-1];
    reg actual_spike [0:N-1];
    integer step, i, errors, checks, spikes;
    always #5 clk = ~clk;
    always @(posedge clk) if (spike_valid) actual_spike[spike_neuron] = 1'b1;

    cns2fpga_core_sync #(
        .NEURON_COUNT(N), .SYNAPSE_COUNT(1730), .NEURON_INDEX_BITS(13),
        .NEURON_PARAM_FILE("outputs/visual_left_hw_ir_v0/neuron_param.mem"),
        .SYNAPSE_FILE("outputs/visual_left_hw_ir_v0/synapse.mem"),
        .OFFSET_FILE("outputs/visual_left_hw_ir_v0/offset.mem"),
        .TYPE_SIGN_FILE("outputs/visual_left_hw_ir_v0/type_sign.mem")
    ) dut (
        .clk(clk), .rst(rst), .clear_state(1'b0), .start_timestep(start_timestep), .input_current(input_current),
        .busy(busy), .timestep_done(timestep_done), .spike_valid(spike_valid),
        .spike_neuron(spike_neuron), .spike_is_pC1(spike_is_pC1),
        .spike_group_flags(spike_group_flags), .clear_done(clear_done), .synapse_op_valid(synapse_op_valid),
        .state_saturation_seen(state_saturation_seen),
        .accumulator_saturation_seen(accumulator_saturation_seen)
    );

    initial begin
        $readmemh("outputs/visual_left_rtl_reference_v0/stimulus.mem", stimulus);
        $readmemh("outputs/visual_left_rtl_reference_v0/expected_voltage.mem", expected_voltage);
        $readmemh("outputs/visual_left_rtl_reference_v0/expected_syn_current.mem", expected_syn_current);
        $readmemh("outputs/visual_left_rtl_reference_v0/expected_refractory.mem", expected_refractory);
        $readmemh("outputs/visual_left_rtl_reference_v0/expected_spike.mem", expected_spike);
        errors = 0;
        checks = 0;
        repeat (3) @(negedge clk);
        rst = 0;
        for (step = 0; step < STEPS; step = step + 1) begin
            for (i = 0; i < N; i = i + 1) actual_spike[i] = 0;
            @(negedge clk);
            input_current = stimulus[step];
            start_timestep = 1;
            @(negedge clk);
            start_timestep = 0;
            wait (timestep_done === 1'b1);
            @(negedge clk);
            spikes = 0;
            for (i = 0; i < N; i = i + 1) begin
                if (dut.voltage_mem[i] !== expected_voltage[step*N+i]) errors = errors + 1;
                if (dut.syn_current_mem[i] !== expected_syn_current[step*N+i]) errors = errors + 1;
                if (dut.refractory_mem[i] !== expected_refractory[step*N+i]) errors = errors + 1;
                if (actual_spike[i] !== expected_spike[step*N+i]) errors = errors + 1;
                checks = checks + 4;
                if (actual_spike[i]) spikes = spikes + 1;
            end
            if (state_saturation_seen || accumulator_saturation_seen) errors = errors + 1;
            $display("VISUAL_STEP=%0d SPIKES=%0d ERRORS=%0d", step, spikes, errors);
            if (errors != 0) $fatal(1, "Visual circuit RTL mismatch");
        end
        $display("PASS VISUAL_LEFT_BOARD_CORE_BIT_EXACT neurons=%0d timesteps=%0d state_checks=%0d errors=%0d", N, STEPS, checks, errors);
        $finish;
    end
    initial begin
        #100000000;
        $fatal(1, "Visual circuit RTL timeout");
    end
endmodule


