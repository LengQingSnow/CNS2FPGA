`timescale 1ns/1ps

// Standalone protocol test: AXI4-Lite adapter + delayed mock trial-engine bus.
module tb_axi_lite_slave;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1;
    reg write_blocked = 1'b0;

    reg [31:0] awaddr = 0;
    reg awvalid = 0;
    wire awready;
    reg [31:0] wdata = 0;
    reg [3:0] wstrb = 0;
    reg wvalid = 0;
    wire wready;
    wire [1:0] bresp;
    wire bvalid;
    reg bready = 0;
    reg [31:0] araddr = 0;
    reg arvalid = 0;
    wire arready;
    wire [31:0] rdata;
    wire [1:0] rresp;
    wire rvalid;
    reg rready = 0;
    wire bus_wr_en;
    wire [19:0] bus_wr_addr;
    wire [31:0] bus_wr_data;
    wire [3:0] bus_wr_strb;
    wire bus_rd_en;
    wire [19:0] bus_rd_addr;
    reg [31:0] bus_rd_data = 0;
    reg bus_rd_valid = 0;

    integer writes_seen = 0;
    integer reads_seen = 0;
    reg [19:0] last_write_addr = 0;
    reg [31:0] last_write_data = 0;
    reg [3:0] last_write_strb = 0;
    reg [19:0] pending_read_addr = 0;
    reg [2:0] read_delay = 0;

    cns2fpga_axi_lite_slave dut (
        .clk(clk), .rst(rst), .write_blocked(write_blocked),
        .s_axi_awaddr(awaddr), .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(wstrb),
        .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp),
        .s_axi_rvalid(rvalid), .s_axi_rready(rready),
        .bus_wr_en(bus_wr_en), .bus_wr_addr(bus_wr_addr),
        .bus_wr_data(bus_wr_data), .bus_wr_strb(bus_wr_strb),
        .bus_rd_en(bus_rd_en), .bus_rd_addr(bus_rd_addr),
        .bus_rd_data(bus_rd_data), .bus_rd_valid(bus_rd_valid)
    );

    // The mock bus accepts each request in one clock and returns read data
    // later. Keep all checks outside the adapter hierarchy.
    always @(posedge clk) begin
        bus_rd_valid <= 1'b0;
        if (rst) begin
            writes_seen <= 0;
            reads_seen <= 0;
            read_delay <= 0;
            bus_rd_data <= 0;
        end else begin
            if (bus_wr_en) begin
                writes_seen <= writes_seen + 1;
                last_write_addr <= bus_wr_addr;
                last_write_data <= bus_wr_data;
                last_write_strb <= bus_wr_strb;
            end
            if (bus_rd_en) begin
                if (read_delay != 0)
                    $fatal(1, "mock received overlapping read requests");
                reads_seen <= reads_seen + 1;
                pending_read_addr <= bus_rd_addr;
                read_delay <= 3;
            end else if (read_delay != 0) begin
                read_delay <= read_delay - 1'b1;
                if (read_delay == 1) begin
                    bus_rd_data <= 32'ha5000000 ^ {12'd0, pending_read_addr};
                    bus_rd_valid <= 1'b1;
                end
            end
        end
    end

    task automatic send_aw(input [31:0] address);
        begin
            @(negedge clk);
            awaddr = address;
            awvalid = 1'b1;
            do @(posedge clk); while (!awready);
            @(negedge clk);
            awvalid = 1'b0;
        end
    endtask

    task automatic send_w(input [31:0] data, input [3:0] strb);
        begin
            @(negedge clk);
            wdata = data;
            wstrb = strb;
            wvalid = 1'b1;
            do @(posedge clk); while (!wready);
            @(negedge clk);
            wvalid = 1'b0;
        end
    endtask

    task automatic check_b(input [1:0] expected_resp, input integer hold_cycles);
        integer i;
        begin
            bready = 1'b0;
            while (!bvalid) @(negedge clk);
            if (bresp !== expected_resp)
                $fatal(1, "BRESP got=%b expected=%b", bresp, expected_resp);
            for (i = 0; i < hold_cycles; i = i + 1) begin
                @(negedge clk);
                if (!bvalid || bresp !== expected_resp || awready || wready)
                    $fatal(1, "B backpressure changed response or accepted a new write");
            end
            bready = 1'b1;
            @(negedge clk);
            if (bvalid)
                $fatal(1, "BVALID did not clear after B handshake");
            bready = 1'b0;
        end
    endtask

    task automatic send_ar(input [31:0] address);
        begin
            @(negedge clk);
            araddr = address;
            arvalid = 1'b1;
            do @(posedge clk); while (!arready);
            @(negedge clk);
            arvalid = 1'b0;
        end
    endtask

    task automatic check_r(
        input [1:0] expected_resp,
        input [31:0] expected_data,
        input integer hold_cycles
    );
        integer i;
        begin
            rready = 1'b0;
            while (!rvalid) @(negedge clk);
            if (rresp !== expected_resp || rdata !== expected_data)
                $fatal(1, "R got resp=%b data=%h expected resp=%b data=%h",
                       rresp, rdata, expected_resp, expected_data);
            for (i = 0; i < hold_cycles; i = i + 1) begin
                @(negedge clk);
                if (!rvalid || rresp !== expected_resp || rdata !== expected_data || arready)
                    $fatal(1, "R backpressure changed response or accepted a new read");
            end
            rready = 1'b1;
            @(negedge clk);
            if (rvalid)
                $fatal(1, "RVALID did not clear after R handshake");
            rready = 1'b0;
        end
    endtask

    task automatic simultaneous_write(input [31:0] address, input [31:0] data);
        begin
            fork
                send_aw(address);
                send_w(data, 4'hf);
            join
            check_b(2'b00, 0);
        end
    endtask

    integer i;
    initial begin
        repeat (4) @(negedge clk);
        rst = 1'b0;

        // Address arrives first; no write can reach the engine yet.
        send_aw(32'h00010020);
        repeat (3) @(negedge clk);
        if (writes_seen != 0 || bvalid) $fatal(1, "AW-only produced a write");
        send_w(32'hdeadbeef, 4'hf);
        check_b(2'b00, 3);
        if (writes_seen != 1 || last_write_addr != 20'h10020 ||
            last_write_data != 32'hdeadbeef || last_write_strb != 4'hf)
            $fatal(1, "AW-before-W data was wrong or duplicated");

        // Data arrives first. The response must wait for AW.
        send_w(32'h12345678, 4'hf);
        repeat (3) @(negedge clk);
        if (writes_seen != 1 || bvalid) $fatal(1, "W-only produced a write");
        send_aw(32'h00010024);
        check_b(2'b00, 1);
        if (writes_seen != 2 || last_write_addr != 20'h10024 ||
            last_write_data != 32'h12345678)
            $fatal(1, "W-before-AW data was wrong or duplicated");

        // Same-cycle AW/W and a stream of legal sequential transactions.
        for (i = 0; i < 4; i = i + 1)
            simultaneous_write(32'h00020000 + i*4, 32'hf0000000 + i);
        if (writes_seen != 6 || last_write_addr != 20'h2000c ||
            last_write_data != 32'hf0000003)
            $fatal(1, "back-to-back writes were lost or duplicated");

        // The adapter's high-address decode and full-word strobe policy.
        fork
            send_aw(32'h00100000);
            send_w(32'hffffffff, 4'hf);
        join
        check_b(2'b10, 2);
        if (writes_seen != 6) $fatal(1, "out-of-range write reached bus");
        fork
            send_aw(32'h00010028);
            send_w(32'hffffffff, 4'b0101);
        join
        check_b(2'b10, 0);
        if (writes_seen != 6) $fatal(1, "partial-strobe write reached bus");
        fork
            send_aw(32'h0001002c);
            send_w(32'hffffffff, 4'b0000);
        join
        check_b(2'b10, 0);
        if (writes_seen != 6) $fatal(1, "zero-strobe write reached bus");

        // The engine is running: complete the AXI write with an error,
        // without presenting a write pulse to the engine-side bus.
        @(negedge clk);
        write_blocked = 1'b1;
        fork
            send_aw(32'h00010030);
            send_w(32'h55aa55aa, 4'hf);
        join
        check_b(2'b10, 2);
        if (writes_seen != 6) $fatal(1, "blocked write reached bus");
        @(negedge clk);
        write_blocked = 1'b0;

        // Read data is delayed by the mock bus, then held until RREADY.
        send_ar(32'h00001234);
        if (rvalid) $fatal(1, "read response preceded mock bus data");
        check_r(2'b00, 32'ha5001234, 3);
        for (i = 0; i < 3; i = i + 1) begin
            send_ar(32'h00002000 + i*4);
            check_r(2'b00, 32'ha5002000 ^ (i*4), 0);
        end
        if (reads_seen != 4) $fatal(1, "valid read count=%0d", reads_seen);

        send_ar(32'h00101234);
        check_r(2'b10, 32'd0, 2);
        if (reads_seen != 4) $fatal(1, "out-of-range read reached bus");

        // Read and write channels are independent, even while B is stalled.
        fork
            send_ar(32'h00003100);
            send_aw(32'h00010100);
            send_w(32'hcafef00d, 4'hf);
        join
        check_r(2'b00, 32'ha5003100, 1);
        check_b(2'b00, 2);
        if (writes_seen != 7 || reads_seen != 5 ||
            last_write_addr != 20'h10100 || last_write_data != 32'hcafef00d)
            $fatal(1, "concurrent read/write request was lost");

        $display("PASS AXI4-LITE AW/W order, sequential reads/writes, backpressure, SLVERR, WSTRB, blocked writes");
        $finish;
    end

    initial begin
        #100000;
        $fatal(1, "AXI4-Lite test timeout");
    end
endmodule
