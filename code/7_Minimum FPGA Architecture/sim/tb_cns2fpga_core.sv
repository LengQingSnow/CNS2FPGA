`timescale 1ns/1ps

module tb_cns2fpga_core;
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg start_timestep = 1'b0;
    reg signed [33:0] input_current = 34'sd0;
    wire busy, timestep_done, spike_valid, spike_is_pC1;
    wire [12:0] spike_neuron;
    wire state_saturation_seen, accumulator_saturation_seen;
    integer observed_spikes = 0;
    integer expected_neuron = -1;

    always #5 clk = ~clk;

    cns2fpga_core #(
        .NEURON_COUNT(2), .SYNAPSE_COUNT(1), .INPUT_COUNT(1), .NEURON_INDEX_BITS(13),
        .STATE_BITS(34), .STATE_FRAC(24), .WEIGHT_BITS(30), .WEIGHT_FRAC(24),
        .DECAY_BITS(32), .DECAY_FRAC(30), .ACC_BITS(35),
        .NEURON_PARAM_FILE("sim/fixtures/two_neuron/neuron_param.mem"),
        .SYNAPSE_FILE("sim/fixtures/two_neuron/synapse.mem"),
        .OFFSET_FILE("sim/fixtures/two_neuron/offset.mem"),
        .TYPE_SIGN_FILE("sim/fixtures/two_neuron/type_sign.mem")
    ) dut (
        .clk(clk), .rst(rst), .start_timestep(start_timestep), .input_current(input_current),
        .busy(busy), .timestep_done(timestep_done), .spike_valid(spike_valid),
        .spike_neuron(spike_neuron), .spike_is_pC1(spike_is_pC1),
        .state_saturation_seen(state_saturation_seen),
        .accumulator_saturation_seen(accumulator_saturation_seen)
    );

    always @(posedge clk) begin
        if (spike_valid) begin
            observed_spikes = observed_spikes + 1;
            if (spike_neuron !== expected_neuron[12:0]) begin
                $display("FAIL unexpected spike neuron=%0d expected=%0d", spike_neuron, expected_neuron);
                $finish;
            end
        end
    end

    task run_step;
        input signed [33:0] current;
        input integer expected;
        integer before_count;
        begin
            before_count = observed_spikes;
            expected_neuron = expected;
            @(negedge clk);
            input_current = current;
            start_timestep = 1'b1;
            @(negedge clk);
            start_timestep = 1'b0;
            wait (timestep_done === 1'b1);
            @(negedge clk);
            if (observed_spikes != before_count + 1) begin
                $display("FAIL spike count delta=%0d", observed_spikes-before_count);
                $finish;
            end
            if (state_saturation_seen || accumulator_saturation_seen) begin
                $display("FAIL unexpected saturation");
                $finish;
            end
        end
    endtask

    initial begin
        repeat (3) @(negedge clk);
        rst = 1'b0;
        // t=0: external S34.24 current of 1.0 makes input neuron 0 spike.
        run_step(34'sd16777216, 0);
        // t=1: the propagated S30.24 weight of 1.0 makes neuron 1 spike.
        run_step(34'sd0, 1);
        $display("PASS two-neuron one-cycle propagation, spikes=%0d", observed_spikes);
        $finish;
    end

    initial begin
        #10000;
        $display("FAIL timeout");
        $finish;
    end
endmodule
