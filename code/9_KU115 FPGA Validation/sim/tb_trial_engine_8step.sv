`timescale 1ns/1ps

module tb_trial_engine_8step;
    localparam integer N = 6279;
    localparam integer STEPS = 8;
    reg clk = 1'b0;
    always #2 clk = ~clk;
    reg rst = 1'b1;
    reg bus_wr_en = 1'b0;
    reg [19:0] bus_wr_addr = 20'd0;
    reg [31:0] bus_wr_data = 32'd0;
    reg [3:0] bus_wr_strb = 4'hf;
    reg bus_rd_en = 1'b0;
    reg [19:0] bus_rd_addr = 20'd0;
    wire [31:0] bus_rd_data;
    wire bus_rd_valid;
    wire trial_running, trial_done, core_busy, fault_seen, deadline_miss_seen;
    reg [33:0] stimulus [0:STEPS-1];
    reg expected_spike [0:STEPS*N-1];
    integer trial, step, neuron, evt, timeout;
    integer expected_count, observed_count, event_start, expected_neuron;
    integer sample_cycle = 0;
    integer last_start_cycle = 0;
    integer start_count = 0;
    reg [31:0] value;

    always @(posedge clk) begin
        sample_cycle = sample_cycle + 1;
        if (dut.start_timestep) begin
            if ((start_count % STEPS) != 0 &&
                sample_cycle - last_start_cycle != 200000)
                $fatal(1, "start interval=%0d expected=200000",
                    sample_cycle - last_start_cycle);
            last_start_cycle = sample_cycle;
            start_count = start_count + 1;
        end
    end

    cns2fpga_trial_engine #(
        .NEURON_PARAM_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/neuron_param.mem"),
        .SYNAPSE_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/synapse.mem"),
        .OFFSET_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/offset.mem"),
        .TYPE_SIGN_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/type_sign.mem")
    ) dut (
        .clk(clk), .rst(rst), .bus_wr_en(bus_wr_en),
        .bus_wr_addr(bus_wr_addr), .bus_wr_data(bus_wr_data),
        .bus_wr_strb(bus_wr_strb), .bus_rd_en(bus_rd_en),
        .bus_rd_addr(bus_rd_addr), .bus_rd_data(bus_rd_data),
        .bus_rd_valid(bus_rd_valid), .trial_running(trial_running),
        .trial_done(trial_done), .core_busy(core_busy),
        .fault_seen(fault_seen), .deadline_miss_seen(deadline_miss_seen)
    );

    task write32(input [19:0] addr, input [31:0] data);
        begin
            @(negedge clk);
            bus_wr_addr = addr;
            bus_wr_data = data;
            bus_wr_en = 1'b1;
            @(negedge clk);
            bus_wr_en = 1'b0;
        end
    endtask

    task read32(input [19:0] addr, output [31:0] data);
        begin
            @(negedge clk);
            bus_rd_addr = addr;
            bus_rd_en = 1'b1;
            @(negedge clk);
            bus_rd_en = 1'b0;
            while (!bus_rd_valid) @(negedge clk);
            data = bus_rd_data;
        end
    endtask

    task check_trial(input integer trial_number);
        begin
            write32(20'h00004, 32'd1);
            timeout = 0;
            while (!trial_running && timeout < 2000000) begin
                @(posedge clk);
                timeout = timeout + 1;
            end
            if (!trial_running) $fatal(1, "trial did not start");
            while (!trial_done && timeout < 2000000) begin
                @(posedge clk);
                timeout = timeout + 1;
            end
            if (!trial_done) $fatal(1, "trial timeout");
            read32(20'h00014, value);
            if (value != STEPS) $fatal(1, "completed steps=%0d", value);
            read32(20'h0001c, value);
            if (value != 0) $fatal(1, "missed steps=%0d", value);
            for (step = 0; step < STEPS; step = step + 1) begin
                read32(20'h20000 + step*32 + 8, value);
                observed_count = value[15:0];
                read32(20'h20000 + step*32 + 20, value);
                if (value[3:0] != 0) $fatal(1, "step=%0d flags=%h", step, value);
                if (value[31:16] != observed_count)
                    $fatal(1, "step=%0d captured=%0d observed=%0d",
                        step, value[31:16], observed_count);
                read32(20'h20000 + step*32 + 24, value);
                event_start = value;
                expected_count = 0;
                for (neuron = 0; neuron < N; neuron = neuron + 1)
                    if (expected_spike[step*N + neuron]) expected_count = expected_count + 1;
                if (observed_count != expected_count)
                    $fatal(1, "step=%0d observed=%0d expected=%0d",
                        step, observed_count, expected_count);
                expected_neuron = 0;
                for (evt = 0; evt < observed_count; evt = evt + 1) begin
                    while (expected_neuron < N && !expected_spike[step*N + expected_neuron])
                        expected_neuron = expected_neuron + 1;
                    read32(20'h60000 + (event_start + evt)*4, value);
                    if (value[12:0] != expected_neuron)
                        $fatal(1, "step=%0d event=%0d got=%0d expected=%0d",
                            step, evt, value[12:0], expected_neuron);
                    expected_neuron = expected_neuron + 1;
                end
                read32(20'h20000 + step*32, value);
                $display("PASS trial=%0d step=%0d spikes=%0d latency_cycles=%0d",
                    trial_number, step, observed_count, value);
            end
        end
    endtask

    initial begin
        $readmemh("../8_RTL Bit-Exact Co-Simulation/sim/reference/full_network_8step_v1/stimulus.mem", stimulus);
        $readmemh("../8_RTL Bit-Exact Co-Simulation/sim/reference/full_network_8step_v1/expected_spike.mem", expected_spike);
        repeat (10) @(negedge clk);
        rst = 1'b0;
        read32(20'h00000, value);
        if (value != 32'h434e5339) $fatal(1, "wrong ID %h", value);
        write32(20'h0000c, STEPS);
        write32(20'h00010, 32'd200000);
        write32(20'h0002c, 32'd1);
        for (step = 0; step < STEPS; step = step + 1) begin
            write32(20'h10000 + step*8, stimulus[step][31:0]);
            write32(20'h10004 + step*8, {30'd0, stimulus[step][33:32]});
        end
        for (step = 0; step < STEPS; step = step + 1) begin
            read32(20'h10000 + step*8, value);
            if (value != stimulus[step][31:0])
                $fatal(1, "stimulus low readback step=%0d got=%h", step, value);
            read32(20'h10004 + step*8, value);
            if (value[1:0] != stimulus[step][33:32])
                $fatal(1, "stimulus high readback step=%0d got=%h", step, value);
        end
        check_trial(0);
        check_trial(1); // The second run proves that state RAM was cleared.
        $display("PASS TRIAL_ENGINE two independent 8-step trials");
        $finish;
    end
endmodule
