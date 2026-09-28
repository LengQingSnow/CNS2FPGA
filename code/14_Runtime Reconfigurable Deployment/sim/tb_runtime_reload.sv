`timescale 1ns/1ps

module tb_runtime_reload;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1;
    reg wr = 1'b0;
    reg [19:0] wa = 20'd0;
    reg [31:0] wd = 32'd0;
    reg rd = 1'b0;
    reg [19:0] ra = 20'd0;
    wire [31:0] data;
    wire valid, running, done, busy, fault, deadline;
    reg [31:0] sum = 32'd0;
    reg [31:0] value;
    integer cycles;

    cns2fpga_trial_engine #(
        .MAX_NEURONS(2), .MAX_SYNAPSES(1), .MAX_STEPS(4), .MAX_EVENTS(8)
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
            wa = address;
            wd = word;
            wr = 1'b1;
            @(negedge clk);
            wr = 1'b0;
        end
    endtask

    task automatic read_reg(input [19:0] address, output [31:0] word);
        begin
            @(negedge clk);
            ra = address;
            rd = 1'b1;
            @(negedge clk);
            rd = 1'b0;
            cycles = 0;
            while (!valid && cycles < 8) begin
                @(negedge clk);
                cycles = cycles + 1;
            end
            if (!valid) $fatal(1, "Read timeout at %h", address);
            word = data;
        end
    endtask

    task automatic stream(input [1:0] region, input [31:0] word);
        begin
            write_reg(20'h00040, word);
            sum = {sum[30:0],sum[31]} ^ word ^ region;
        end
    endtask

    task automatic load_two_neurons(input [31:0] threshold);
        begin
            write_reg(20'h00030, 32'd1);
            write_reg(20'h00034, 32'd2);
            write_reg(20'h00038, 32'd0);
            sum = 32'd0;
            write_reg(20'h0003c, 32'd0);
            stream(2'd0, threshold);
            stream(2'd0, 32'd0);
            stream(2'd0, 32'd0);
            stream(2'd0, 32'd0);
            stream(2'd0, 32'h04000000);
            stream(2'd0, 32'd0);
            stream(2'd0, 32'd0);
            stream(2'd0, 32'd0);
            write_reg(20'h0003c, 32'd2);
            stream(2'd2, 32'd0);
            stream(2'd2, 32'd0);
            write_reg(20'h0003c, 32'd3);
            stream(2'd3, 32'd4);
            stream(2'd3, 32'd0);
            write_reg(20'h00044, sum);
            write_reg(20'h00030, 32'd2);
            read_reg(20'h00030, value);
            if (value != 32'd1) $fatal(1, "COMMIT failed: status=%h", value);
        end
    endtask

    task automatic trial(input integer expected_spikes);
        begin
            write_reg(20'h0000c, 32'd1);
            write_reg(20'h00010, 32'd2000);
            write_reg(20'h0002c, 32'd1);
            write_reg(20'h10000, 32'h02000000);
            write_reg(20'h10004, 32'd0);
            write_reg(20'h00004, 32'd1);
            cycles = 0;
            while (!running && cycles < 20) begin
                @(negedge clk);
                cycles = cycles + 1;
            end
            if (!running) $fatal(1, "Trial did not start");
            cycles = 0;
            while (!done && cycles < 200) begin
                @(negedge clk);
                cycles = cycles + 1;
            end
            if (!done) $fatal(1, "Trial timeout");
            if (fault) $fatal(1, "Trial fault");
            read_reg(20'h20008, value);
            if (value[15:0] !== expected_spikes)
                $fatal(1, "Spike mismatch: expected %0d, got %0d", expected_spikes, value[15:0]);
            read_reg(20'h00018, value);
            if (value !== expected_spikes)
                $fatal(1, "Event count mismatch: expected %0d, got %0d", expected_spikes, value);
            if (expected_spikes != 0) begin
                read_reg(20'h60000, value);
                if (value !== 32'd0)
                    $fatal(1, "Event readback mismatch: %h", value);
            end
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        rst = 1'b0;
        read_reg(20'h00000, value);
        if (value != 32'h434e5352) $fatal(1, "Wrong firmware ID");
        write_reg(20'h00004, 32'd1);
        repeat (3) @(negedge clk);
        if (running || done) $fatal(1, "Started without an image");

        write_reg(20'h00030, 32'd1);
        write_reg(20'h00034, 32'd2);
        write_reg(20'h00038, 32'd0);
        write_reg(20'h00044, 32'd0);
        write_reg(20'h00030, 32'd2);
        read_reg(20'h00030, value);
        if ((value & 32'h00000005) != 32'h00000004)
            $fatal(1, "Incomplete image was not rejected: %h", value);

        write_reg(20'h00030, 32'd1);
        write_reg(20'h00034, 32'd2);
        write_reg(20'h00038, 32'd1);
        write_reg(20'h0003c, 32'd1);
        stream(2'd1, 32'd2); // post_index 2 is outside 0..1
        read_reg(20'h00030, value);
        if ((value & 32'h00000004) == 0)
            $fatal(1, "Out-of-range synapse post was accepted");

        write_reg(20'h00030, 32'd1);
        write_reg(20'h00034, 32'd2);
        write_reg(20'h00038, 32'd0);
        write_reg(20'h0003c, 32'd2);
        stream(2'd2, 32'd1); // CSR start 1 exceeds zero synapses
        read_reg(20'h00030, value);
        if ((value & 32'h00000004) == 0)
            $fatal(1, "Out-of-range CSR offset was accepted");

        load_two_neurons(32'h01000000);
        read_reg(20'h0004c, value);
        if (value != 1) $fatal(1, "First image epoch missing");
        trial(1);

        load_two_neurons(32'h03000000);
        read_reg(20'h0004c, value);
        if (value != 2) $fatal(1, "Second image epoch missing");
        trial(0);
        $display("RUNTIME_RELOAD_PASS: one design, two distinct images, epochs=2, spikes=1 then 0");
        $finish;
    end
endmodule
