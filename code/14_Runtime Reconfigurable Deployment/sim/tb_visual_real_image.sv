`timescale 1ns/1ps

// End-to-end regression using the checked-in visual-left compiler image and
// its independently generated 250-step expected spike-count trace.
module tb_visual_real_image;
    localparam integer N = 226;
    localparam integer S = 1730;
    localparam integer STEPS = 250;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1;
    reg wr = 1'b0;
    reg [19:0] wa = 0;
    reg [31:0] wd = 0;
    reg rd = 1'b0;
    reg [19:0] ra = 0;
    wire [31:0] data;
    wire valid, running, done, busy, fault, deadline;
    reg [127:0] params [0:N-1];
    reg [63:0] synapses [0:S-1];
    reg [31:0] offsets [0:N-1];
    reg [15:0] types [0:N-1];
    reg [33:0] stimulus [0:STEPS-1];
    reg [31:0] sum = 0;
    reg [31:0] value;
    integer i, j, f, parsed, index, expected_total, left_count, right_count;
    integer cycles, mismatches;
    reg [1023:0] csv_line;

    cns2fpga_trial_engine #(
        .MAX_NEURONS(N), .MAX_SYNAPSES(S), .MAX_STEPS(STEPS),
        .MAX_EVENTS(2048)
    ) dut (
        .clk(clk), .rst(rst), .bus_wr_en(wr), .bus_wr_addr(wa),
        .bus_wr_data(wd), .bus_wr_strb(4'hf),
        .bus_rd_en(rd), .bus_rd_addr(ra), .bus_rd_data(data),
        .bus_rd_valid(valid), .trial_running(running), .trial_done(done),
        .core_busy(busy), .fault_seen(fault), .deadline_miss_seen(deadline)
    );

    task automatic write_reg(input [19:0] address, input [31:0] word);
        begin
            @(negedge clk);
            wa = address; wd = word; wr = 1'b1;
            @(negedge clk);
            wr = 1'b0;
        end
    endtask
    task automatic read_reg(input [19:0] address, output [31:0] word);
        integer timeout;
        begin
            @(negedge clk);
            ra = address; rd = 1'b1;
            @(negedge clk);
            rd = 1'b0;
            timeout = 0;
            while (!valid && timeout < 8) begin
                @(negedge clk);
                timeout = timeout + 1;
            end
            if (!valid) $fatal(1, "Bus read timeout: %h", address);
            word = data;
        end
    endtask
    task automatic stream(input [1:0] region, input [31:0] word);
        begin
            write_reg(20'h00040, word);
            sum = {sum[30:0],sum[31]} ^ word ^ region;
        end
    endtask

    initial begin
        $readmemh("../12_Visual-to-Steering Circuit/outputs/visual_left_hw_ir_v0/neuron_param.mem", params);
        $readmemh("../12_Visual-to-Steering Circuit/outputs/visual_left_hw_ir_v0/synapse.mem", synapses);
        $readmemh("../12_Visual-to-Steering Circuit/outputs/visual_left_hw_ir_v0/offset.mem", offsets);
        $readmemh("../12_Visual-to-Steering Circuit/outputs/visual_left_hw_ir_v0/type_sign.mem", types);
        $readmemh("../12_Visual-to-Steering Circuit/outputs/visual_left_board_v0/trial/stimulus.mem", stimulus);
        repeat (5) @(negedge clk);
        rst = 1'b0;
        write_reg(20'h00030, 1);
        write_reg(20'h00034, N);
        write_reg(20'h00038, S);
        for (j = 0; j < 4; j = j + 1) begin
            write_reg(20'h0003c, j);
            if (j == 0)
                for (i = 0; i < N; i = i + 1)
                    for (integer lane = 0; lane < 4; lane = lane + 1)
                        stream(2'd0, params[i][lane*32 +: 32]);
            if (j == 1)
                for (i = 0; i < S; i = i + 1) begin
                    stream(2'd1, synapses[i][31:0]);
                    stream(2'd1, synapses[i][63:32]);
                end
            if (j == 2)
                for (i = 0; i < N; i = i + 1)
                    stream(2'd2, offsets[i]);
            if (j == 3)
                for (i = 0; i < N; i = i + 1)
                    stream(2'd3, {16'd0, types[i]});
        end
        if (sum != 32'h6c233d31) $fatal(1, "Fixture checksum mismatch: %h", sum);
        write_reg(20'h00044, sum);
        write_reg(20'h00030, 2);
        read_reg(20'h00030, value);
        if (value != 1) $fatal(1, "Visual image COMMIT failed: %h", value);
        read_reg(20'h00050, value);
        if (value != 904) $fatal(1, "Visual parameter count mismatch");
        read_reg(20'h00054, value);
        if (value != 3460) $fatal(1, "Visual synapse count mismatch");

        write_reg(20'h0000c, STEPS);
        write_reg(20'h00010, 2); // no idle wait; only deadline flags differ
        for (i = 0; i < STEPS; i = i + 1) begin
            write_reg(20'h10000 + i*8, stimulus[i][31:0]);
            write_reg(20'h10004 + i*8, {30'd0,stimulus[i][33:32]});
        end
        write_reg(20'h00004, 1);
        cycles = 0;
        while (!done && cycles < 1000000) begin
            @(negedge clk);
            cycles = cycles + 1;
        end
        if (!done) $fatal(1, "Visual trial timeout");
        if (fault) $fatal(1, "Visual trial fault");

        f = $fopen("../12_Visual-to-Steering Circuit/outputs/visual_left_board_v0/trial/expected_counts.csv", "r");
        if (!f) $fatal(1, "Missing visual expected_counts.csv");
        parsed = $fgets(csv_line, f); // header
        mismatches = 0;
        for (i = 0; i < STEPS; i = i + 1) begin
            parsed = $fgets(csv_line, f);
            if (parsed == 0 || $sscanf(csv_line, "%d,%d,%d,%d", index,
                expected_total, left_count, right_count) != 4 || index != i)
                $fatal(1, "Malformed expected count at timestep %0d", i);
            read_reg(20'h20000 + i*32 + 8, value);
            if (value[15:0] !== expected_total) begin
                mismatches = mismatches + 1;
                if (mismatches < 8)
                    $display("Mismatch step %0d: hardware=%0d expected=%0d", i,
                        value[15:0], expected_total);
            end
        end
        $fclose(f);
        if (mismatches) $fatal(1, "%0d visual count mismatches", mismatches);
        $display("VISUAL_REAL_IMAGE_PASS: %0d neurons, %0d synapses, %0d exact timestep counts", N, S, STEPS);
        $finish;
    end
endmodule
