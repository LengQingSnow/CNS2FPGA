`timescale 1ns/1ps

// AXKU115 experiment top: one bitstream, runtime-loaded network images.
module cns2fpga_axku115_jtag_top (
    input  wire clk_50m,
    input  wire key1_n,
    output wire led1,
    output wire led2
);
    wire clk_50m_ibuf;
    wire clkfb_mmcm;
    wire clkfb_buf;
    wire clk_200m_mmcm;
    wire clk_200m;
    wire mmcm_locked;

    IBUF clock_input_buffer (.I(clk_50m), .O(clk_50m_ibuf));
    MMCME3_BASE #(
        .BANDWIDTH("OPTIMIZED"),
        .CLKIN1_PERIOD(20.000),
        .DIVCLK_DIVIDE(1),
        .CLKFBOUT_MULT_F(20.000),
        .CLKOUT0_DIVIDE_F(5.000),
        .CLKOUT0_DUTY_CYCLE(0.500),
        .STARTUP_WAIT("FALSE")
    ) clock_manager (
        .CLKIN1(clk_50m_ibuf), .CLKFBIN(clkfb_buf),
        .RST(~key1_n), .PWRDWN(1'b0),
        .CLKFBOUT(clkfb_mmcm), .CLKFBOUTB(),
        .CLKOUT0(clk_200m_mmcm), .CLKOUT0B(),
        .CLKOUT1(), .CLKOUT1B(), .CLKOUT2(), .CLKOUT2B(),
        .CLKOUT3(), .CLKOUT3B(), .CLKOUT4(), .CLKOUT5(),
        .CLKOUT6(), .LOCKED(mmcm_locked)
    );
    BUFG feedback_clock_buffer (.I(clkfb_mmcm), .O(clkfb_buf));
    BUFG system_clock_buffer (.I(clk_200m_mmcm), .O(clk_200m));

    (* ASYNC_REG = "TRUE" *) reg [3:0] reset_sync = 4'hf;
    always @(posedge clk_200m or negedge mmcm_locked) begin
        if (!mmcm_locked)
            reset_sync <= 4'hf;
        else
            reset_sync <= {reset_sync[2:0], 1'b0};
    end
    wire system_reset = reset_sync[3];

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
    wire bus_rd_valid;
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
        .s_axi_rready(axi_rready), .bus_wr_en(bus_wr_en),
        .bus_wr_addr(bus_wr_addr), .bus_wr_data(bus_wr_data),
        .bus_wr_strb(bus_wr_strb), .bus_rd_en(bus_rd_en),
        .bus_rd_addr(bus_rd_addr), .bus_rd_data(bus_rd_data),
        .bus_rd_valid(bus_rd_valid)
    );

    cns2fpga_trial_engine #(
        .MAX_NEURONS(6279),
        .MAX_SYNAPSES(350185)
    ) experiment (
        .clk(clk_200m), .rst(system_reset),
        .bus_wr_en(bus_wr_en), .bus_wr_addr(bus_wr_addr),
        .bus_wr_data(bus_wr_data), .bus_wr_strb(bus_wr_strb),
        .bus_rd_en(bus_rd_en), .bus_rd_addr(bus_rd_addr),
        .bus_rd_data(bus_rd_data), .bus_rd_valid(bus_rd_valid),
        .trial_running(trial_running), .trial_done(trial_done),
        .core_busy(core_busy), .fault_seen(fault_seen),
        .deadline_miss_seen(deadline_miss_seen)
    );

    assign led1 = trial_running | fault_seen;
    assign led2 = trial_done & ~deadline_miss_seen;
endmodule
