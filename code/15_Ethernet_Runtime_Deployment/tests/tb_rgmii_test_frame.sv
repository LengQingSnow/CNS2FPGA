`timescale 1ns/1ps

module tb_rgmii_test_frame;
    reg clk = 0;
    reg clk90 = 0;
    reg phy_rx_clk = 0;
    always #4 clk = ~clk;
    initial begin #2; forever #4 clk90 = ~clk90; end
    initial begin #1; forever #4 phy_rx_clk = ~phy_rx_clk; end
    reg rst = 1;
    reg test_frame_toggle = 0;
    wire phy_tx_clk;
    wire [3:0] phy_txd;
    wire phy_tx_ctl;
    wire [31:0] diag_test_count;
    cns2fpga_eth_stack #(
        .TARGET("GENERIC"), .PHY_RESET_CYCLES(16),
        .PHY_MAC_SETTLE_CYCLES(16), .TX_RAM_PIPELINE(1)
    ) dut (
        .clk(clk), .clk90(clk90), .rst(rst),
        .phy_rx_clk(phy_rx_clk), .phy_rxd(4'b0), .phy_rx_ctl(1'b0),
        .phy_tx_clk(phy_tx_clk), .phy_txd(phy_txd), .phy_tx_ctl(phy_tx_ctl),
        .test_frame_toggle(test_frame_toggle), .diag_test_count(diag_test_count),
        .cmd_ack_toggle(1'b0), .cmd_read_data(32'b0)
    );
    reg [3:0] low_nibble;
    reg [7:0] bytes [0:127];
    integer count = 0;
    integer i;
    integer j;
    reg [31:0] crc;
    reg crc_x_logged = 0;
    always @(posedge clk) begin
        if ($time >= 2400 && $time < 2480)
            $display("CRC_TRACE time=%0t state=%h crc=%h data=%h fifo=%h valid=%b ready=%b",
                $time, dut.eth_mac_inst.eth_mac_1g_rgmii_inst.eth_mac_1g_inst.axis_gmii_tx_inst.state_reg,
                dut.eth_mac_inst.eth_mac_1g_rgmii_inst.eth_mac_1g_inst.axis_gmii_tx_inst.crc_state,
                dut.eth_mac_inst.eth_mac_1g_rgmii_inst.eth_mac_1g_inst.axis_gmii_tx_inst.s_tdata_reg,
                dut.eth_mac_inst.tx_fifo_axis_tdata, dut.eth_mac_inst.tx_fifo_axis_tvalid,
                dut.eth_mac_inst.tx_fifo_axis_tready);
        if (!crc_x_logged &&
            (^dut.eth_mac_inst.eth_mac_1g_rgmii_inst.eth_mac_1g_inst.axis_gmii_tx_inst.crc_state === 1'bx)) begin
            crc_x_logged <= 1;
            $display("CRC_FIRST_X time=%0t state=%h s_data=%h fifo_data=%h valid=%b last=%b",
                $time, dut.eth_mac_inst.eth_mac_1g_rgmii_inst.eth_mac_1g_inst.axis_gmii_tx_inst.state_reg,
                dut.eth_mac_inst.eth_mac_1g_rgmii_inst.eth_mac_1g_inst.axis_gmii_tx_inst.s_tdata_reg,
                dut.eth_mac_inst.tx_fifo_axis_tdata, dut.eth_mac_inst.tx_fifo_axis_tvalid,
                dut.eth_mac_inst.tx_fifo_axis_tlast);
        end
        if (dut.eth_mac_inst.eth_mac_1g_rgmii_inst.eth_mac_1g_inst.axis_gmii_tx_inst.state_reg == 5)
            $display("TX_FCS_STATE crc=%h data=%h last=%b user=%b",
                dut.eth_mac_inst.eth_mac_1g_rgmii_inst.eth_mac_1g_inst.axis_gmii_tx_inst.crc_state,
                dut.eth_mac_inst.tx_fifo_axis_tdata,
                dut.eth_mac_inst.tx_fifo_axis_tlast,
                dut.eth_mac_inst.tx_fifo_axis_tuser);
    end
    always @(posedge phy_tx_clk) begin
        #0.1;
        if (phy_tx_ctl) low_nibble = phy_txd;
    end
    always @(negedge phy_tx_clk) begin
        #0.1;
        if (phy_tx_ctl && count < 128) begin
            bytes[count] = {phy_txd, low_nibble};
            count = count + 1;
        end
    end
    initial begin
        repeat (30) @(posedge clk);
        rst = 0;
        repeat (200) @(posedge clk);
        test_frame_toggle = 1;
        repeat (4000) @(posedge clk);
        $display("FIRST_TEST_FRAME count=%0d fcs=%h%h%h%h",
            count, bytes[71], bytes[70], bytes[69], bytes[68]);
        count = 0;
        test_frame_toggle = 0;
        repeat (4000) @(posedge clk);
        if (diag_test_count != 2 || count != 72 || bytes[7] != 8'hd5 ||
            {bytes[8],bytes[9],bytes[10],bytes[11],bytes[12],bytes[13]} != 48'hffffffffffff ||
            {bytes[14],bytes[15],bytes[16],bytes[17],bytes[18],bytes[19]} != 48'h020000000015 ||
            {bytes[20],bytes[21]} != 16'h88b5)
            $fatal(1, "RGMII_TEST_FRAME_FAIL count=%0d sent=%0d", count, diag_test_count);
        crc = 32'hffffffff;
        for (i=8; i<68; i=i+1) begin
            for (j=0; j<8; j=j+1) begin
                if (crc[0] ^ bytes[i][j]) crc = (crc >> 1) ^ 32'hedb88320;
                else crc = crc >> 1;
            end
        end
        crc = ~crc;
        $display("RGMII_TEST_TAIL b64..71=%h %h %h %h %h %h %h %h",
            bytes[64],bytes[65],bytes[66],bytes[67],bytes[68],bytes[69],bytes[70],bytes[71]);
        if ({bytes[71],bytes[70],bytes[69],bytes[68]} !== crc)
            $fatal(1, "RGMII_TEST_FCS_FAIL expected=%h got=%h%h%h%h",
                   crc, bytes[71],bytes[70],bytes[69],bytes[68]);
        $display("RGMII_TEST_FRAME_PASS bytes=%0d fcs=%h", count, crc);
        $finish;
    end
endmodule
