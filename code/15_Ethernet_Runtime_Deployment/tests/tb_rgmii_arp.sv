`timescale 1ns/1ps

module tb_rgmii_arp;
    reg clk = 0;
    reg clk90 = 0;
    reg phy_rx_clk = 0;
    always #4 clk = ~clk;
    initial begin #2; forever #4 clk90 = ~clk90; end
    initial begin #1; forever #4 phy_rx_clk = ~phy_rx_clk; end

    reg rst = 1;
    reg [3:0] phy_rxd = 0;
    reg phy_rx_ctl = 0;
    wire phy_tx_clk;
    wire [3:0] phy_txd;
    wire phy_tx_ctl;
    wire phy_reset_n;
    wire phy_link_activity;
    wire cmd_toggle;
    wire cmd_read;
    wire [19:0] cmd_addr;
    wire [31:0] cmd_data;

    cns2fpga_eth_stack #(
        .TARGET("GENERIC"), .PHY_RESET_CYCLES(16),
        .PHY_MAC_SETTLE_CYCLES(16)
    ) dut (
        .clk(clk), .clk90(clk90), .rst(rst),
        .phy_rx_clk(phy_rx_clk), .phy_rxd(phy_rxd),
        .phy_rx_ctl(phy_rx_ctl), .phy_tx_clk(phy_tx_clk),
        .phy_txd(phy_txd), .phy_tx_ctl(phy_tx_ctl),
        .phy_reset_n(phy_reset_n), .phy_link_activity(phy_link_activity),
        .test_frame_toggle(1'b0),
        .cmd_toggle(cmd_toggle), .cmd_read(cmd_read),
        .cmd_addr(cmd_addr), .cmd_data(cmd_data),
        .cmd_ack_toggle(cmd_toggle), .cmd_read_data(32'd0)
    );

    reg [7:0] frame [0:63];
    reg [31:0] crc;
    reg [31:0] fcs;
    integer i;
    integer j;
    integer arp_replies = 0;
    integer rx_headers = 0;
    integer tx_active_edges = 0;
    reg [3:0] tx_low_nibble = 0;
    reg [7:0] tx_capture [0:127];
    integer tx_byte_count = 0;

    task automatic send_rgmii_byte(input reg [7:0] octet);
        begin
            @(negedge phy_rx_clk);
            #1 phy_rxd = octet[3:0];
               phy_rx_ctl = 1;
            @(posedge phy_rx_clk);
            #1 phy_rxd = octet[7:4];
        end
    endtask

    always @(posedge clk) begin
        if (dut.rx_eth_hdr_valid && dut.rx_eth_hdr_ready) begin
            rx_headers <= rx_headers + 1;
            $display("RX_ETH_HEADER type=%h dest=%h src=%h", dut.rx_eth_type,
                     dut.rx_eth_dest_mac, dut.rx_eth_src_mac);
        end
        if (dut.tx_eth_hdr_valid && dut.tx_eth_hdr_ready) begin
            $display("TX_ETH_HEADER type=%h dest=%h src=%h", dut.tx_eth_type,
                     dut.tx_eth_dest_mac, dut.tx_eth_src_mac);
            if (dut.tx_eth_type == 16'h0806 &&
                dut.tx_eth_dest_mac == 48'h28c5c8d5e228 &&
                dut.tx_eth_src_mac == 48'h020000000015)
                arp_replies <= arp_replies + 1;
        end
    end

    always @(posedge phy_tx_clk or negedge phy_tx_clk) begin
        if (phy_tx_ctl) tx_active_edges <= tx_active_edges + 1;
    end
    always @(posedge phy_tx_clk) begin
        #0.1;
        if (phy_tx_ctl) tx_low_nibble = phy_txd;
    end
    always @(negedge phy_tx_clk) begin
        #0.1;
        if (phy_tx_ctl && tx_byte_count < 128) begin
            tx_capture[tx_byte_count] = {phy_txd, tx_low_nibble};
            tx_byte_count = tx_byte_count + 1;
        end
    end

    initial begin
        // Ethernet header: broadcast, host MAC, ARP.
        frame[0]=8'hff; frame[1]=8'hff; frame[2]=8'hff;
        frame[3]=8'hff; frame[4]=8'hff; frame[5]=8'hff;
        frame[6]=8'h28; frame[7]=8'hc5; frame[8]=8'hc8;
        frame[9]=8'hd5; frame[10]=8'he2; frame[11]=8'h28;
        frame[12]=8'h08; frame[13]=8'h06;
        // ARP request: Ethernet/IPv4, sender 192.168.1.10,
        // target 192.168.1.128.
        frame[14]=8'h00; frame[15]=8'h01;
        frame[16]=8'h08; frame[17]=8'h00;
        frame[18]=8'h06; frame[19]=8'h04;
        frame[20]=8'h00; frame[21]=8'h01;
        frame[22]=8'h28; frame[23]=8'hc5; frame[24]=8'hc8;
        frame[25]=8'hd5; frame[26]=8'he2; frame[27]=8'h28;
        frame[28]=8'hc0; frame[29]=8'ha8; frame[30]=8'h01; frame[31]=8'h0a;
        for (i=32; i<38; i=i+1) frame[i]=0;
        frame[38]=8'hc0; frame[39]=8'ha8; frame[40]=8'h01; frame[41]=8'h80;
        for (i=42; i<60; i=i+1) frame[i]=0;
        crc = 32'hffffffff;
        for (i=0; i<60; i=i+1) begin
            for (j=0; j<8; j=j+1) begin
                if (crc[0] ^ frame[i][j])
                    crc = (crc >> 1) ^ 32'hedb88320;
                else
                    crc = crc >> 1;
            end
        end
        fcs = ~crc;
        frame[60]=fcs[7:0]; frame[61]=fcs[15:8];
        frame[62]=fcs[23:16]; frame[63]=fcs[31:24];

        repeat (30) @(posedge clk);
        rst = 0;
        // The vendor ARP cache clears all 512 entries after reset.
        repeat (800) @(posedge clk);
        for (i=0; i<7; i=i+1) send_rgmii_byte(8'h55);
        send_rgmii_byte(8'hd5);
        for (i=0; i<64; i=i+1) send_rgmii_byte(frame[i]);
        @(negedge phy_rx_clk);
        #1 phy_rx_ctl = 0;
           phy_rxd = 0;
        repeat (4000) @(posedge clk);
        if (rx_headers != 1 || arp_replies != 1 || tx_active_edges < 80)
            $fatal(1, "RGMII_ARP_FAIL rx_headers=%0d arp_replies=%0d tx_edges=%0d",
                   rx_headers, arp_replies, tx_active_edges);
        if (tx_byte_count < 72 || tx_capture[7] != 8'hd5 ||
            {tx_capture[8],tx_capture[9],tx_capture[10],
             tx_capture[11],tx_capture[12],tx_capture[13]} != 48'h28c5c8d5e228 ||
            {tx_capture[14],tx_capture[15],tx_capture[16],
             tx_capture[17],tx_capture[18],tx_capture[19]} != 48'h020000000015 ||
            {tx_capture[20],tx_capture[21]} != 16'h0806)
            $fatal(1, "RGMII_ARP_TX_BYTES_FAIL count=%0d sfd=%h dmac=%h%h%h%h%h%h",
                   tx_byte_count, tx_capture[7], tx_capture[8], tx_capture[9],
                   tx_capture[10], tx_capture[11], tx_capture[12], tx_capture[13]);
        crc = 32'hffffffff;
        for (i=8; i<tx_byte_count-4; i=i+1) begin
            for (j=0; j<8; j=j+1) begin
                if (crc[0] ^ tx_capture[i][j]) crc = (crc >> 1) ^ 32'hedb88320;
                else crc = crc >> 1;
            end
        end
        fcs = ~crc;
        if ({tx_capture[tx_byte_count-1], tx_capture[tx_byte_count-2],
             tx_capture[tx_byte_count-3], tx_capture[tx_byte_count-4]} !== fcs)
            $fatal(1, "RGMII_ARP_TX_FCS_FAIL count=%0d calc=%h got=%h%h%h%h",
                   tx_byte_count, fcs, tx_capture[tx_byte_count-1],
                   tx_capture[tx_byte_count-2], tx_capture[tx_byte_count-3],
                   tx_capture[tx_byte_count-4]);
        $display("RGMII_ARP_PASS rx_headers=%0d arp_replies=%0d tx_edges=%0d",
                 rx_headers, arp_replies, tx_active_edges);
        // Replay a real Windows CNSE STATUS packet after the ARP request has
        // populated the FPGA cache with the host's IP and MAC address.
        tx_byte_count = 0;
        frame[0]=8'h02; frame[1]=8'h00; frame[2]=8'h00;
        frame[3]=8'h00; frame[4]=8'h00; frame[5]=8'h15;
        frame[6]=8'h28; frame[7]=8'hc5; frame[8]=8'hc8;
        frame[9]=8'hd5; frame[10]=8'he2; frame[11]=8'h28;
        frame[12]=8'h08; frame[13]=8'h00;
        frame[14]=8'h45; frame[15]=8'h00; frame[16]=8'h00; frame[17]=8'h2c;
        frame[18]=8'hd0; frame[19]=8'h89; frame[20]=8'h00; frame[21]=8'h00;
        frame[22]=8'h80; frame[23]=8'h11; frame[24]=8'he6; frame[25]=8'h5c;
        frame[26]=8'hc0; frame[27]=8'ha8; frame[28]=8'h01; frame[29]=8'h0a;
        frame[30]=8'hc0; frame[31]=8'ha8; frame[32]=8'h01; frame[33]=8'h80;
        frame[34]=8'hcf; frame[35]=8'hf5; frame[36]=8'h10; frame[37]=8'he1;
        frame[38]=8'h00; frame[39]=8'h18; frame[40]=8'hff; frame[41]=8'h78;
        frame[42]=8'h43; frame[43]=8'h4e; frame[44]=8'h53; frame[45]=8'h45;
        frame[46]=8'h04; frame[47]=8'h00; frame[48]=8'h00; frame[49]=8'h00;
        frame[50]=8'h01; frame[51]=8'h00; frame[52]=8'h00; frame[53]=8'h00;
        for (i=54; i<60; i=i+1) frame[i]=0;
        crc = 32'hffffffff;
        for (i=0; i<60; i=i+1) begin
            for (j=0; j<8; j=j+1) begin
                if (crc[0] ^ frame[i][j]) crc = (crc >> 1) ^ 32'hedb88320;
                else crc = crc >> 1;
            end
        end
        fcs = ~crc;
        frame[60]=fcs[7:0]; frame[61]=fcs[15:8];
        frame[62]=fcs[23:16]; frame[63]=fcs[31:24];
        for (i=0; i<7; i=i+1) send_rgmii_byte(8'h55);
        send_rgmii_byte(8'hd5);
        for (i=0; i<64; i=i+1) send_rgmii_byte(frame[i]);
        @(negedge phy_rx_clk);
        #1 phy_rx_ctl = 0;
           phy_rxd = 0;
        repeat (6000) @(posedge clk);
        $display("RGMII_STATUS_TRACE rx_udp=%d tx_udp=%d tx_eth=%d bytes=%d type=%h dest=%h",
                 dut.rx_udp_count, dut.tx_udp_count, dut.tx_good_count,
                 tx_byte_count, {tx_capture[20],tx_capture[21]},
                 {tx_capture[8],tx_capture[9],tx_capture[10],tx_capture[11],tx_capture[12],tx_capture[13]});
        if (dut.rx_udp_count != 1 || dut.tx_udp_count != 1 ||
            tx_byte_count != 72 ||
            {tx_capture[8],tx_capture[9],tx_capture[10],tx_capture[11],tx_capture[12],tx_capture[13]} != 48'h28c5c8d5e228 ||
            {tx_capture[20],tx_capture[21]} != 16'h0800 ||
            {tx_capture[50],tx_capture[51],tx_capture[52],tx_capture[53]} != 32'h434e5341)
            $fatal(1, "RGMII_STATUS_FAIL bytes=%0d", tx_byte_count);
        crc = 32'hffffffff;
        for (i=8; i<68; i=i+1) begin
            for (j=0; j<8; j=j+1) begin
                if (crc[0] ^ tx_capture[i][j]) crc = (crc >> 1) ^ 32'hedb88320;
                else crc = crc >> 1;
            end
        end
        fcs = ~crc;
        if ({tx_capture[71],tx_capture[70],tx_capture[69],tx_capture[68]} !== fcs)
            $fatal(1, "RGMII_STATUS_FCS_FAIL expected=%h got=%h%h%h%h",
                   fcs,tx_capture[71],tx_capture[70],tx_capture[69],tx_capture[68]);
        $display("RGMII_STATUS_PASS bytes=%0d fcs=%h", tx_byte_count, fcs);
        $finish;
    end
endmodule
