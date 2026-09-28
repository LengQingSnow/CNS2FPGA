`timescale 1ns/1ps

// AXKU115 runtime engine: JTAG control plus UDP/RGMII graph upload.
module cns2fpga_axku115_eth_top (
    input  wire clk_50m,
    input  wire key1_n,
    input  wire phy_rx_clk,
    input  wire [3:0] phy_rxd,
    input  wire phy_rx_ctl,
    output wire phy_tx_clk,
    output wire [3:0] phy_txd,
    output wire phy_tx_ctl,
    output wire phy_reset_n,
    output wire phy_mdc,
    inout  wire phy_mdio,
    output wire led1,
    output wire led2
);
    wire clk_50m_ibuf;
    wire clkfb_mmcm;
    wire clkfb_buf;
    wire clk_200m_mmcm;
    wire clk_200m;
    wire clk_125m_mmcm;
    wire clk_125m90_mmcm;
    wire clk_125m;
    wire clk_125m90;
    wire mmcm_locked;

    IBUF clock_input_buffer (.I(clk_50m), .O(clk_50m_ibuf));
    MMCME3_BASE #(
        .BANDWIDTH("OPTIMIZED"),
        .CLKIN1_PERIOD(20.000),
        .DIVCLK_DIVIDE(1),
        .CLKFBOUT_MULT_F(20.000),
        .CLKOUT0_DIVIDE_F(5.000),
        .CLKOUT0_DUTY_CYCLE(0.500),
        .CLKOUT1_DIVIDE(8),
        .CLKOUT2_DIVIDE(8),
        .CLKOUT2_PHASE(95.625),
        .STARTUP_WAIT("FALSE")
    ) clock_manager (
        .CLKIN1(clk_50m_ibuf), .CLKFBIN(clkfb_buf),
        .RST(~key1_n), .PWRDWN(1'b0),
        .CLKFBOUT(clkfb_mmcm), .CLKFBOUTB(),
        .CLKOUT0(clk_200m_mmcm), .CLKOUT0B(),
        .CLKOUT1(clk_125m_mmcm), .CLKOUT1B(),
        .CLKOUT2(clk_125m90_mmcm), .CLKOUT2B(),
        .CLKOUT3(), .CLKOUT3B(), .CLKOUT4(), .CLKOUT5(),
        .CLKOUT6(), .LOCKED(mmcm_locked)
    );
    BUFG feedback_clock_buffer (.I(clkfb_mmcm), .O(clkfb_buf));
    BUFG system_clock_buffer (.I(clk_200m_mmcm), .O(clk_200m));
    BUFG ethernet_clock_buffer (.I(clk_125m_mmcm), .O(clk_125m));
    BUFG ethernet_clock90_buffer (.I(clk_125m90_mmcm), .O(clk_125m90));

    (* ASYNC_REG = "TRUE" *) reg [3:0] reset_sync = 4'hf;
    always @(posedge clk_200m or negedge mmcm_locked) begin
        if (!mmcm_locked)
            reset_sync <= 4'hf;
        else
            reset_sync <= {reset_sync[2:0], 1'b0};
    end
    wire system_reset = reset_sync[3];
    (* ASYNC_REG = "TRUE" *) reg [3:0] ethernet_reset_sync = 4'hf;
    always @(posedge clk_125m or negedge mmcm_locked) begin
        if (!mmcm_locked)
            ethernet_reset_sync <= 4'hf;
        else
            ethernet_reset_sync <= {ethernet_reset_sync[2:0], 1'b0};
    end
    wire ethernet_reset = ethernet_reset_sync[3];

    wire [31:0] axi_awaddr;
    wire [2:0] axi_awprot;
    wire axi_awvalid, axi_awready;
    wire [31:0] axi_wdata;
    wire [3:0] axi_wstrb;
    wire axi_wvalid, axi_wready;
    wire [1:0] axi_bresp;
    wire axi_bvalid, axi_bready;
    wire [31:0] axi_araddr;
    wire [2:0] axi_arprot;
    wire axi_arvalid, axi_arready;
    wire [31:0] axi_rdata;
    wire [1:0] axi_rresp;
    wire axi_rvalid, axi_rready;

    cns2fpga_jtag_axi jtag_master (
        .aclk(clk_200m), .aresetn(~system_reset),
        .m_axi_awaddr(axi_awaddr), .m_axi_awprot(axi_awprot),
        .m_axi_awvalid(axi_awvalid), .m_axi_awready(axi_awready),
        .m_axi_wdata(axi_wdata), .m_axi_wstrb(axi_wstrb),
        .m_axi_wvalid(axi_wvalid), .m_axi_wready(axi_wready),
        .m_axi_bresp(axi_bresp), .m_axi_bvalid(axi_bvalid),
        .m_axi_bready(axi_bready),
        .m_axi_araddr(axi_araddr), .m_axi_arprot(axi_arprot),
        .m_axi_arvalid(axi_arvalid), .m_axi_arready(axi_arready),
        .m_axi_rdata(axi_rdata), .m_axi_rresp(axi_rresp),
        .m_axi_rvalid(axi_rvalid), .m_axi_rready(axi_rready)
    );

    wire bus_wr_en;
    wire [19:0] bus_wr_addr;
    wire [31:0] bus_wr_data;
    wire [3:0] bus_wr_strb;
    wire bus_rd_en;
    wire [19:0] bus_rd_addr;
    wire [31:0] bus_rd_data;
    wire [31:0] core_bus_rd_data;
    wire bus_rd_valid;
    wire [31:0] ethernet_diag_status;
    wire [15:0] ethernet_diag_rx_clock_gray;
    wire [31:0] ethernet_diag_rx_counts;
    wire [31:0] ethernet_diag_tx_counts;
    wire [31:0] ethernet_diag_test_count;
    wire [47:0] ethernet_last_tx_dest_mac;
    wire [15:0] ethernet_last_tx_eth_type;
    wire [47:0] ethernet_last_rx_src_mac;
    wire [15:0] ethernet_last_rx_eth_type;
    wire [31:0] ethernet_error_counts;
    wire [31:0] ethernet_flow_live;
    wire [31:0] ethernet_flow_counts;
    reg test_frame_toggle = 0;
    wire [31:0] mdio_status;
    wire [31:0] mdio_result;
    reg [3:0] diag_read_select = 0;
    wire jtag_bus_wr_en;
    wire [19:0] jtag_bus_wr_addr;
    wire [31:0] jtag_bus_wr_data;
    wire [3:0] jtag_bus_wr_strb;
    wire jtag_bus_rd_en;
    wire [19:0] jtag_bus_rd_addr;
    wire eth_bus_wr_en;
    wire [19:0] eth_bus_wr_addr;
    wire [31:0] eth_bus_wr_data;
    wire eth_bus_rd_en;
    wire [19:0] eth_bus_rd_addr;
    wire eth_cmd_toggle;
    wire eth_cmd_read;
    wire [19:0] eth_cmd_addr;
    wire [31:0] eth_cmd_data;
    wire eth_ack_toggle;
    wire [31:0] eth_read_data;
    wire phy_link_activity;
    wire trial_running;
    wire trial_done;
    wire core_busy;
    wire fault_seen;
    wire deadline_miss_seen;

    cns2fpga_axi_lite_slave axi_slave (
        .clk(clk_200m), .rst(system_reset), .write_blocked(trial_running),
        .s_axi_awaddr(axi_awaddr), .s_axi_awvalid(axi_awvalid),
        .s_axi_awready(axi_awready), .s_axi_wdata(axi_wdata),
        .s_axi_wstrb(axi_wstrb), .s_axi_wvalid(axi_wvalid),
        .s_axi_wready(axi_wready), .s_axi_bresp(axi_bresp),
        .s_axi_bvalid(axi_bvalid), .s_axi_bready(axi_bready),
        .s_axi_araddr(axi_araddr), .s_axi_arvalid(axi_arvalid),
        .s_axi_arready(axi_arready), .s_axi_rdata(axi_rdata),
        .s_axi_rresp(axi_rresp), .s_axi_rvalid(axi_rvalid),
        .s_axi_rready(axi_rready), .bus_wr_en(jtag_bus_wr_en),
        .bus_wr_addr(jtag_bus_wr_addr), .bus_wr_data(jtag_bus_wr_data),
        .bus_wr_strb(jtag_bus_wr_strb), .bus_rd_en(jtag_bus_rd_en),
        .bus_rd_addr(jtag_bus_rd_addr), .bus_rd_data(bus_rd_data),
        .bus_rd_valid(bus_rd_valid)
    );

    cns2fpga_eth_stack #(.TARGET("XILINX")) ethernet (
        .clk(clk_125m), .clk90(clk_125m90), .rst(ethernet_reset),
        .phy_rx_clk(phy_rx_clk), .phy_rxd(phy_rxd), .phy_rx_ctl(phy_rx_ctl),
        .phy_tx_clk(phy_tx_clk), .phy_txd(phy_txd),
        .phy_tx_ctl(phy_tx_ctl), .phy_reset_n(phy_reset_n),
        .phy_link_activity(phy_link_activity),
        .diag_status(ethernet_diag_status),
        .diag_rx_clock_gray(ethernet_diag_rx_clock_gray),
        .diag_rx_counts(ethernet_diag_rx_counts),
        .diag_tx_counts(ethernet_diag_tx_counts),
        .diag_test_count(ethernet_diag_test_count),
        .diag_last_tx_dest_mac(ethernet_last_tx_dest_mac),
        .diag_last_tx_eth_type(ethernet_last_tx_eth_type),
        .diag_last_rx_src_mac(ethernet_last_rx_src_mac),
        .diag_last_rx_eth_type(ethernet_last_rx_eth_type),
        .diag_error_counts(ethernet_error_counts),
        .diag_flow_live(ethernet_flow_live),
        .diag_flow_counts(ethernet_flow_counts),
        .test_frame_toggle(test_frame_toggle),
        .cmd_toggle(eth_cmd_toggle), .cmd_read(eth_cmd_read),
        .cmd_addr(eth_cmd_addr), .cmd_data(eth_cmd_data),
        .cmd_ack_toggle(eth_ack_toggle), .cmd_read_data(eth_read_data)
    );

    cns2fpga_eth_bus_bridge ethernet_bus_bridge (
        .clk(clk_200m), .rst(system_reset),
        .req_toggle(eth_cmd_toggle), .req_read(eth_cmd_read),
        .req_addr(eth_cmd_addr), .req_data(eth_cmd_data),
        .ack_toggle(eth_ack_toggle), .read_data(eth_read_data),
        .jtag_activity(jtag_bus_wr_en | jtag_bus_rd_en),
        .bus_wr_en(eth_bus_wr_en), .bus_wr_addr(eth_bus_wr_addr),
        .bus_wr_data(eth_bus_wr_data), .bus_rd_en(eth_bus_rd_en),
        .bus_rd_addr(eth_bus_rd_addr),
        .bus_rd_data(bus_rd_data), .bus_rd_valid(bus_rd_valid)
    );

    cns2fpga_mdio_diag mdio_diagnostics (
        .clk(clk_200m), .rst(system_reset),
        .start(jtag_bus_wr_en && jtag_bus_wr_addr == 20'h00080 && jtag_bus_wr_data[31]),
        .write_mode(jtag_bus_wr_data[30]),
        .phy_addr(jtag_bus_wr_data[29:25]),
        .reg_addr(jtag_bus_wr_data[24:20]),
        .write_data(jtag_bus_wr_data[15:0]),
        .mdc(phy_mdc), .mdio(phy_mdio),
        .status(mdio_status), .result(mdio_result)
    );

    // Host software serializes JTAG and Ethernet access.
    assign bus_wr_en = jtag_bus_wr_en | eth_bus_wr_en;
    assign bus_wr_addr = jtag_bus_wr_en ? jtag_bus_wr_addr : eth_bus_wr_addr;
    assign bus_wr_data = jtag_bus_wr_en ? jtag_bus_wr_data : eth_bus_wr_data;
    assign bus_wr_strb = jtag_bus_wr_en ? jtag_bus_wr_strb : 4'hf;
    assign bus_rd_en = jtag_bus_rd_en | eth_bus_rd_en;
    assign bus_rd_addr = jtag_bus_rd_en ? jtag_bus_rd_addr : eth_bus_rd_addr;
    always @(posedge clk_200m) begin
        if (system_reset)
            test_frame_toggle <= 0;
        else if (jtag_bus_wr_en && jtag_bus_wr_addr == 20'h000a0 && jtag_bus_wr_data[0])
            test_frame_toggle <= ~test_frame_toggle;
    end
    always @(posedge clk_200m) begin
        if (system_reset)
            diag_read_select <= 0;
        else if (bus_rd_en) begin
            case (bus_rd_addr)
                20'h00070: diag_read_select <= 2'd1;
                20'h00074: diag_read_select <= 2'd2;
                20'h00078: diag_read_select <= 3'd3;
                20'h0007c: diag_read_select <= 3'd4;
                20'h00084: diag_read_select <= 3'd5;
                20'h00088: diag_read_select <= 3'd6;
                20'h0008c: diag_read_select <= 3'd7;
                20'h00090: diag_read_select <= 4'd8;
                20'h00094: diag_read_select <= 4'd9;
                20'h00098: diag_read_select <= 4'd10;
                20'h0009c: diag_read_select <= 4'd11;
                20'h000a4: diag_read_select <= 4'd12;
                20'h000a8: diag_read_select <= 4'd13;
                20'h000ac: diag_read_select <= 4'd14;
                default: diag_read_select <= 0;
            endcase
        end
    end
    assign bus_rd_data = diag_read_select == 2'd1 ? ethernet_diag_status :
                         diag_read_select == 2'd2 ? {16'd0, ethernet_diag_rx_clock_gray} :
                         diag_read_select == 3'd3 ? mdio_status :
                         diag_read_select == 3'd4 ? mdio_result :
                         diag_read_select == 3'd5 ? ethernet_diag_rx_counts :
                         diag_read_select == 3'd6 ? ethernet_diag_tx_counts :
                         diag_read_select == 3'd7 ? ethernet_diag_test_count :
                         diag_read_select == 4'd8 ? ethernet_last_tx_dest_mac[31:0] :
                         diag_read_select == 4'd9 ? {ethernet_last_tx_eth_type, ethernet_last_tx_dest_mac[47:32]} :
                         diag_read_select == 4'd10 ? ethernet_last_rx_src_mac[31:0] :
                         diag_read_select == 4'd11 ? {ethernet_last_rx_eth_type, ethernet_last_rx_src_mac[47:32]} :
                         diag_read_select == 4'd12 ? ethernet_error_counts :
                         diag_read_select == 4'd13 ? ethernet_flow_live :
                         diag_read_select == 4'd14 ? ethernet_flow_counts :
                         core_bus_rd_data;

    cns2fpga_trial_engine #(
        .MAX_NEURONS(6279),
        .MAX_SYNAPSES(350185)
    ) experiment (
        .clk(clk_200m), .rst(system_reset),
        .bus_wr_en(bus_wr_en), .bus_wr_addr(bus_wr_addr),
        .bus_wr_data(bus_wr_data), .bus_wr_strb(bus_wr_strb),
        .bus_rd_en(bus_rd_en), .bus_rd_addr(bus_rd_addr),
        .bus_rd_data(core_bus_rd_data), .bus_rd_valid(bus_rd_valid),
        .trial_running(trial_running), .trial_done(trial_done),
        .core_busy(core_busy), .fault_seen(fault_seen),
        .deadline_miss_seen(deadline_miss_seen)
    );

    assign led1 = trial_running | fault_seen;
    assign led2 = trial_done & ~deadline_miss_seen;
endmodule
