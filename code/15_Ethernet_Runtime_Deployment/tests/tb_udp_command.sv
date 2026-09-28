`timescale 1ns/1ps

module tb_udp_command;
    reg clk125 = 0, clk200 = 0, rst = 1;
    always #4 clk125 = ~clk125;
    always #2.5 clk200 = ~clk200;

    reg rx_hdr_valid = 0, rx_valid = 0, rx_last = 0, rx_user = 0;
    reg [7:0] rx_data = 0;
    reg [31:0] rx_dest_ip = 32'hc0a80180;
    reg [15:0] rx_dest_port = 16'd4321;
    reg [15:0] rx_length = 16'd24;
    wire rx_hdr_ready, rx_ready;
    wire tx_hdr_valid, tx_valid, tx_last;
    wire [7:0] tx_data;
    wire [15:0] tx_length;
    wire [31:0] tx_dest_ip;
    wire [15:0] tx_dest_port;
    wire cmd_toggle, cmd_read, ack_toggle;
    wire [19:0] cmd_addr;
    wire [31:0] cmd_data, read_data;
    wire bus_wr_en, bus_rd_en;
    wire [19:0] bus_wr_addr, bus_rd_addr;
    wire [31:0] bus_wr_data;
    reg [31:0] bus_rd_data = 0;
    reg bus_rd_valid = 0;
    reg [31:0] image_status = 0;
    reg [19:0] writes_addr [0:15];
    reg [31:0] writes_data [0:15];
    integer write_count = 0;
    integer reply_headers = 0;
    always @(posedge clk125) if (tx_hdr_valid) reply_headers <= reply_headers + 1;

    cns2fpga_udp_command dut (
        .clk(clk125), .rst(rst),
        .rx_hdr_valid(rx_hdr_valid), .rx_hdr_ready(rx_hdr_ready),
        .rx_source_ip(32'hc0a8010a), .rx_dest_ip(rx_dest_ip),
        .rx_source_port(16'd49152), .rx_dest_port(rx_dest_port),
        .rx_length(rx_length), .rx_data(rx_data), .rx_valid(rx_valid),
        .rx_ready(rx_ready), .rx_last(rx_last), .rx_user(rx_user),
        .tx_hdr_valid(tx_hdr_valid), .tx_hdr_ready(1'b1),
        .tx_dest_ip(tx_dest_ip), .tx_dest_port(tx_dest_port),
        .tx_length(tx_length), .tx_data(tx_data), .tx_valid(tx_valid),
        .tx_ready(1'b1), .tx_last(tx_last),
        .cmd_toggle(cmd_toggle), .cmd_read(cmd_read),
        .cmd_addr(cmd_addr), .cmd_data(cmd_data),
        .cmd_ack_toggle(ack_toggle), .cmd_read_data(read_data)
    );

    cns2fpga_eth_bus_bridge bridge (
        .clk(clk200), .rst(rst),
        .req_toggle(cmd_toggle), .req_read(cmd_read),
        .req_addr(cmd_addr), .req_data(cmd_data),
        .ack_toggle(ack_toggle), .read_data(read_data),
        .jtag_activity(1'b0),
        .bus_wr_en(bus_wr_en), .bus_wr_addr(bus_wr_addr),
        .bus_wr_data(bus_wr_data), .bus_rd_en(bus_rd_en),
        .bus_rd_addr(bus_rd_addr), .bus_rd_data(bus_rd_data),
        .bus_rd_valid(bus_rd_valid)
    );

    always @(posedge clk200) begin
        bus_rd_valid <= bus_rd_en;
        if (bus_rd_en) begin
            if (bus_rd_addr !== 20'h30) $fatal(1, "wrong read address");
            bus_rd_data <= image_status;
        end
        if (bus_wr_en) begin
            writes_addr[write_count] <= bus_wr_addr;
            writes_data[write_count] <= bus_wr_data;
            write_count <= write_count + 1;
            if (bus_wr_addr == 20'h30 && bus_wr_data == 1)
                image_status <= 2;
            if (bus_wr_addr == 20'h30 && bus_wr_data == 2)
                image_status <= 1;
        end
    end

    task send_byte(input [7:0] b, input bit last);
        begin
            @(negedge clk125);
            rx_data = b;
            rx_valid = 1;
            rx_last = last;
            if (!rx_ready) $fatal(1, "receiver not ready");
            @(negedge clk125);
            rx_valid = 0;
            rx_last = 0;
        end
    endtask

    task send_word(input [31:0] w, input bit last_word);
        integer i;
        begin
            for (i = 0; i < 4; i = i + 1)
                send_byte(w[8*i +: 8], last_word && i == 3);
        end
    endtask

    task send_packet(input [7:0] op, input [7:0] region,
                     input [15:0] count, input [31:0] seq,
                     input [31:0] val, input bit payload);
        begin
            rx_length = payload ? 16'd32 : 16'd24;
            wait (rx_hdr_ready);
            @(negedge clk125);
            rx_hdr_valid = 1;
            @(negedge clk125);
            rx_hdr_valid = 0;
            send_byte(8'h43, 0);
            send_byte(8'h4e, 0);
            send_byte(8'h53, 0);
            send_byte(8'h45, 0);
            send_byte(op, 0);
            send_byte(region, 0);
            send_byte(count[7:0], 0);
            send_byte(count[15:8], 0);
            send_word(seq, 0);
            send_word(val, !payload);
            if (payload) begin
                send_word(32'h12345678, 0);
                send_word(32'habcdef01, 1);
            end
        end
    endtask

    task expect_ack(input [7:0] want_status, input [31:0] want_seq,
                    input [31:0] want_image);
        reg [7:0] got [0:15];
        integer i;
        begin
            wait (tx_hdr_valid);
            @(posedge clk125);
            if (tx_length !== 24 || tx_dest_ip !== 32'hc0a8010a ||
                tx_dest_port !== 16'd49152)
                $fatal(1, "bad UDP reply header");
            for (i = 0; i < 16; i = i + 1) begin
                @(posedge clk125);
                if (!tx_valid) $fatal(1, "short ACK");
                got[i] = tx_data;
                if (tx_last !== (i == 15)) $fatal(1, "wrong ACK last");
            end
            if ({got[3],got[2],got[1],got[0]} !== 32'h41534e43 ||
                got[4] !== want_status ||
                {got[11],got[10],got[9],got[8]} !== want_seq ||
                {got[15],got[14],got[13],got[12]} !== want_image)
                $fatal(1, "bad ACK status=%d seq=%d image=%h",
                       got[4], {got[11],got[10],got[9],got[8]},
                       {got[15],got[14],got[13],got[12]});
            @(posedge clk125);
        end
    endtask

    initial begin
        repeat (8) @(negedge clk125);
        rst = 0;
        // Unrelated host broadcasts must be drained without an ACK or an
        // engine write; otherwise ARP retries can block graph deployment.
        rx_dest_ip = 32'he00000fb;
        rx_dest_port = 16'd5353;
        repeat (20) begin
            send_packet(4, 0, 0, 1, 0, 0);
            repeat (2) @(negedge clk125);
            if (!rx_hdr_ready || reply_headers != 0 || write_count != 0)
                $fatal(1, "foreign UDP was not silently drained");
        end
        rx_dest_ip = 32'hc0a80180;
        send_packet(4, 0, 0, 1, 0, 0);
        repeat (2) @(negedge clk125);
        if (!rx_hdr_ready || reply_headers != 0 || write_count != 0)
            $fatal(1, "foreign UDP port generated an ACK");
        rx_dest_port = 16'd4321;
        send_packet(1, 0, 2, 1, 2, 0);
        expect_ack(0, 1, 2);
        if (write_count != 3 || writes_addr[0] != 20'h30 ||
            writes_data[0] != 1 || writes_addr[1] != 20'h34 ||
            writes_data[1] != 2 || writes_addr[2] != 20'h38 ||
            writes_data[2] != 2) $fatal(1, "BEGIN writes wrong");

        send_packet(2, 1, 2, 2, 0, 1);
        expect_ack(0, 2, 2);
        if (write_count != 6 || writes_addr[3] != 20'h3c ||
            writes_data[3] != 1 || writes_addr[4] != 20'h40 ||
            writes_data[4] != 32'h12345678 || writes_addr[5] != 20'h40 ||
            writes_data[5] != 32'habcdef01) $fatal(1, "DATA writes wrong");

        send_packet(2, 1, 2, 2, 0, 1);
        expect_ack(4, 2, 0);
        if (write_count != 6) $fatal(1, "duplicate wrote data");

        send_packet(3, 0, 0, 4, 32'hdeadbeef, 0);
        expect_ack(2, 4, 0);
        if (write_count != 6) $fatal(1, "out-of-order wrote data");

        send_packet(3, 0, 0, 3, 32'hdeadbeef, 0);
        expect_ack(0, 3, 1);
        if (write_count != 8 || writes_addr[6] != 20'h44 ||
            writes_data[6] != 32'hdeadbeef || writes_addr[7] != 20'h30 ||
            writes_data[7] != 2) $fatal(1, "COMMIT writes wrong");

        $display("ETHERNET_UDP_COMMAND_SIM_PASS writes=%0d", write_count);
        $finish;
    end

    initial begin
        #1000000;
        $fatal(1, "simulation timeout");
    end
endmodule
