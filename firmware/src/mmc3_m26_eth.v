/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */

`timescale 1ps / 1ps
`default_nettype none

module mmc3_m26_eth(
    input wire RESET_N,
    input wire clkin,


    output wire [3:0] rgmii_txd,
    output wire rgmii_tx_ctl,
    output wire rgmii_txc,
    input wire [3:0] rgmii_rxd,
    input wire rgmii_rx_ctl,
    input wire rgmii_rxc,
    output wire mdio_phy_mdc,
    inout wire mdio_phy_mdio,
    output wire phy_rst_n,

    output wire [7:0] LED,

    input wire [5:0] M26_CLK_P, M26_CLK_N, M26_MKD_P, M26_MKD_N,
    input wire [5:0] M26_DATA1_P, M26_DATA1_N, M26_DATA0_P, M26_DATA0_N,

    output wire M26_TCK_P, M26_TCK_N,
    output wire M26_TMS_P, M26_TMS_N,
    output wire M26_TDI_P, M26_TDI_N,
    input wire M26_TDO_P, M26_TDO_N,

    output wire M26_CLK_CLK_P, M26_CLK_CLK_N,
    output wire M26_CLK_START_P, M26_CLK_START_N,
    output wire M26_CLK_RESET_P, M26_CLK_RESET_N,
    output wire M26_CLK_SPEAK_P, M26_CLK_SPEAK_N,

    output wire RJ45_BUSY_LEMO_TX1, RJ45_CLK_LEMO_TX0,
    output wire [1:0] LEMO_TX, // individual LEMO TX only available on MMC3 revision 1.2
    input wire RJ45_TRIGGER, RJ45_RESET,
    input wire [1:0] LEMO_RX,
    inout wire [7:0] PMOD // 2-row PMOD header for general purpose IOs
);

// ***********************************************************
// *** change version number in case of functional changes ***
// ***********************************************************
localparam VERSION = 8'd8;

wire RST;
wire CLK125_PLL, CLK125_90_PLL;
wire PLL_FEEDBACK, LOCKED;
PLLE2_BASE #(
    .BANDWIDTH("OPTIMIZED"),  // OPTIMIZED, HIGH, LOW
    .CLKFBOUT_MULT(10),       // Multiply value for all CLKOUT, (2-64)
    .CLKFBOUT_PHASE(0.0),     // Phase offset in degrees of CLKFB, (-360.000-360.000).
    .CLKIN1_PERIOD(10.000),      // Input clock period in ns to ps resolution (i.e. 33.333 is 30 MHz).

    .CLKOUT0_DIVIDE(8),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT0_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT0_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT1_DIVIDE(8),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT1_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT1_PHASE(90.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .DIVCLK_DIVIDE(1),        // Master division value, (1-56)
    .REF_JITTER1(0.0),        // Reference input jitter in UI, (0.000-0.999).
    .STARTUP_WAIT("FALSE")     // Delay DONE until PLL Locks, ("TRUE"/"FALSE")
) PLLE2_BASE_inst (
    .CLKOUT0(CLK125_PLL),
    .CLKOUT1(CLK125_90_PLL),
    .CLKOUT2(),
    .CLKOUT3(),
    .CLKOUT4(),
    .CLKOUT5(),

    .CLKFBOUT(PLL_FEEDBACK),
    .LOCKED(LOCKED),     // 1-bit output: LOCK

    // Input 100 MHz clock
    .CLKIN1(clkin),

    // Control Ports
    .PWRDWN(0),
    .RST(!RESET_N),

    // Feedback
    .CLKFBIN(PLL_FEEDBACK)
);

wire CLK40_PLL, BUS_CLK_PLL;
wire PLL_FEEDBACK2, LOCKED2;
PLLE2_BASE #(
    .BANDWIDTH("OPTIMIZED"),
    .CLKFBOUT_MULT(16),
    .CLKFBOUT_PHASE(0.0),
    .CLKIN1_PERIOD(10.000),

    .CLKOUT0_DIVIDE(40),
    .CLKOUT0_DUTY_CYCLE(0.5),
    .CLKOUT0_PHASE(0.0),

    .CLKOUT1_DIVIDE(12),
    .CLKOUT1_DUTY_CYCLE(0.5),
    .CLKOUT1_PHASE(0.0),

    .DIVCLK_DIVIDE(1),
    .REF_JITTER1(0.0),
    .STARTUP_WAIT("FALSE")
) PLLE2_BASE_inst_2 (
    .CLKOUT0(CLK40_PLL),
    .CLKOUT1(BUS_CLK_PLL),
    .CLKOUT2(),
    .CLKOUT3(),
    .CLKOUT4(),
    .CLKOUT5(),

    .CLKFBOUT(PLL_FEEDBACK2),
    .LOCKED(LOCKED2), // 1-bit output: LOCK

    .CLKIN1(clkin),

    .PWRDWN(0),
    .RST(!RESET_N),

    .CLKFBIN(PLL_FEEDBACK2)
);


wire CLK40, BUS_CLK;
BUFG BUFG_inst_40 (.O(CLK40), .I(CLK40_PLL));
BUFG BUFG_inst_BUS_CLK (.O(BUS_CLK), .I(BUS_CLK_PLL));  // 133.3MHz

assign RST = !RESET_N | !LOCKED | !LOCKED2;


wire   gmii_tx_clk;
wire   gmii_tx_en;
wire  [7:0] gmii_txd;
wire   gmii_tx_er;
wire   gmii_crs;
wire   gmii_col;
wire   gmii_rx_clk;
wire   gmii_rx_dv;
wire  [7:0] gmii_rxd;
wire   gmii_rx_er;
wire   mdio_gem_mdc;
wire   mdio_gem_i;
wire   mdio_gem_o;
wire   mdio_gem_t;
wire   link_status;
wire  [1:0] clock_speed;
wire   duplex_status;
reg GMII_1000M;

wire MII_TX_CLK, MII_TX_CLK_90;
BUFGMUX GMIIMUX (.O(MII_TX_CLK), .I0(rgmii_rxc), .I1(CLK125_PLL), .S(GMII_1000M));
BUFGMUX GMIIMUX90 (.O(MII_TX_CLK_90), .I0(rgmii_rxc), .I1(CLK125_90_PLL), .S(GMII_1000M));

rgmii_io rgmii (
    .rgmii_txd(rgmii_txd),
    .rgmii_tx_ctl(rgmii_tx_ctl),
    .rgmii_txc(rgmii_txc),

    .rgmii_rxd(rgmii_rxd),
    .rgmii_rx_ctl(rgmii_rx_ctl),

    .gmii_txd_int(gmii_txd),      // Internal gmii_txd signal.
    .gmii_tx_en_int(gmii_tx_en),
    .gmii_tx_er_int(gmii_tx_er),
    .gmii_col_int(gmii_col),
    .gmii_crs_int(gmii_crs),
    .gmii_rxd_reg(gmii_rxd),   // RGMII double data rate data valid.
    .gmii_rx_dv_reg(gmii_rx_dv), // gmii_rx_dv_ibuf registered in IOBs.
    .gmii_rx_er_reg(gmii_rx_er), // gmii_rx_er_ibuf registered in IOBs.

    .eth_link_status(link_status),
    .eth_clock_speed(clock_speed),
    .eth_duplex_status(duplex_status),

    // Following are generated by DCMs
    .tx_rgmii_clk_int(MII_TX_CLK),     // Internal RGMII transmitter clock.
    .tx_rgmii_clk90_int(MII_TX_CLK_90),   // Internal RGMII transmitter clock w/ 90 deg phase
    .rx_rgmii_clk_int(rgmii_rxc),     // Internal RGMII receiver clock

    .reset(!phy_rst_n)
);

//assign GMII_1000M = &clock_speed;
always@(posedge BUS_CLK or posedge RST)begin
    if (RST) begin
        GMII_1000M <= 1'b0;
    end else begin
        GMII_1000M <= clock_speed[1];
    end
end

// Instantiate tri-state buffer for MDIO
IOBUF i_iobuf_mdio (
    .O(mdio_gem_i),
    .IO(mdio_phy_mdio),
    .I(mdio_gem_o),
    .T(mdio_gem_t)
);

wire EEPROM_CS, EEPROM_SK, EEPROM_DI;
wire TCP_CLOSE_REQ;
wire RBCP_ACT, RBCP_WE, RBCP_RE;
wire [7:0] RBCP_WD, RBCP_RD;
wire [31:0] RBCP_ADDR;
wire TCP_RX_WR;
wire [7:0] TCP_RX_DATA;
wire [15:0] TCP_RX_WC;
wire RBCP_ACK;
wire SiTCP_RST;

wire TCP_TX_FULL;
wire TCP_TX_WR;
wire [7:0] TCP_TX_DATA;

wire [7:0] PMOD_O;
IOBUF iobuf_pmod [7:0] (
    .O(PMOD_O),
    .IO(PMOD),
    .I({8'b1111_0000}),
    .T({8'b0000_1111})
);
wire [7:0] IP_ADDR_SEL;
assign IP_ADDR_SEL = {4'b0, PMOD_O[3], PMOD_O[2], PMOD_O[1], PMOD_O[0]}; // MSB: PMOD[3]; LSB: PMOD[0]

WRAP_SiTCP_GMII_XC7K_32K #(
    .TIM_PERIOD(8'd133)
) sitcp (
    .CLK(BUS_CLK)                    ,    // in    : System Clock >129MHz
    .RST(RST)                    ,    // in    : System reset
    // Configuration parameters
    .FORCE_DEFAULTn(1'b0)        ,    // in    : Load default parameters
    .EXT_IP_ADDR({8'd192, 8'd168, 8'd10 + IP_ADDR_SEL, 8'd10})            ,    // in    : IP address[31:0] //192.168.10.10
    .EXT_TCP_PORT(16'd24)        ,    // in    : TCP port #[15:0]
    .EXT_RBCP_PORT(16'd4660)        ,    // in    : RBCP port #[15:0]
    .PHY_ADDR(5'd3)            ,    // in    : PHY-device MIF address[4:0]
    // EEPROM
    .EEPROM_CS(EEPROM_CS)            ,    // out    : Chip select
    .EEPROM_SK(EEPROM_SK)            ,    // out    : Serial data clock
    .EEPROM_DI(EEPROM_DI)            ,    // out    : Serial write data
    .EEPROM_DO(1'b0)            ,    // in    : Serial read data
    // user data, intialial values are stored in the EEPROM, 0xFFFF_FC3C-3F
    .USR_REG_X3C()            ,    // out    : Stored at 0xFFFF_FF3C
    .USR_REG_X3D()            ,    // out    : Stored at 0xFFFF_FF3D
    .USR_REG_X3E()            ,    // out    : Stored at 0xFFFF_FF3E
    .USR_REG_X3F()            ,    // out    : Stored at 0xFFFF_FF3F
    // MII interface
    .GMII_RSTn(phy_rst_n)            ,    // out    : PHY reset
    .GMII_1000M(GMII_1000M)            ,    // in    : GMII mode (0:MII, 1:GMII)
    // TX
    .GMII_TX_CLK(MII_TX_CLK)            ,    // in    : Tx clock
    .GMII_TX_EN(gmii_tx_en)            ,    // out    : Tx enable
    .GMII_TXD(gmii_txd)            ,    // out    : Tx data[7:0]
    .GMII_TX_ER(gmii_tx_er)            ,    // out    : TX error
    // RX
    .GMII_RX_CLK(rgmii_rxc)           ,    // in    : Rx clock
    .GMII_RX_DV(gmii_rx_dv)            ,    // in    : Rx data valid
    .GMII_RXD(gmii_rxd)            ,    // in    : Rx data[7:0]
    .GMII_RX_ER(gmii_rx_er)            ,    // in    : Rx error
    .GMII_CRS(gmii_crs)            ,    // in    : Carrier sense
    .GMII_COL(gmii_col)            ,    // in    : Collision detected
    // Management IF
    .GMII_MDC(mdio_phy_mdc)            ,    // out    : Clock for MDIO
    .GMII_MDIO_IN(mdio_gem_i)        ,    // in    : Data
    .GMII_MDIO_OUT(mdio_gem_o)        ,    // out    : Data
    .GMII_MDIO_OE(mdio_gem_t)        ,    // out    : MDIO output enable
    // User I/F
    .SiTCP_RST(SiTCP_RST)            ,    // out    : Reset for SiTCP and related circuits
    // TCP connection control
    .TCP_OPEN_REQ(1'b0)        ,    // in    : Reserved input, shoud be 0
    .TCP_OPEN_ACK()        ,    // out    : Acknowledge for open (=Socket busy)
    .TCP_ERROR()            ,    // out    : TCP error, its active period is equal to MSL
    .TCP_CLOSE_REQ(TCP_CLOSE_REQ)        ,    // out    : Connection close request
    .TCP_CLOSE_ACK(TCP_CLOSE_REQ)        ,    // in    : Acknowledge for closing
    // FIFO I/F
    .TCP_RX_WC(TCP_RX_WC)            ,    // in    : Rx FIFO write count[15:0] (Unused bits should be set 1)
    .TCP_RX_WR(TCP_RX_WR)            ,    // out    : Write enable
    .TCP_RX_DATA(TCP_RX_DATA)            ,    // out    : Write data[7:0]
    .TCP_TX_FULL(TCP_TX_FULL)            ,    // out    : Almost full flag
    .TCP_TX_WR(TCP_TX_WR)            ,    // in    : Write enable
    .TCP_TX_DATA(TCP_TX_DATA)            ,    // in    : Write data[7:0]
    // RBCP
    .RBCP_ACT(RBCP_ACT)            ,    // out    : RBCP active
    .RBCP_ADDR(RBCP_ADDR)            ,    // out    : Address[31:0]
    .RBCP_WD(RBCP_WD)                ,    // out    : Data[7:0]
    .RBCP_WE(RBCP_WE)                ,    // out    : Write enable
    .RBCP_RE(RBCP_RE)                ,    // out    : Read enable
    .RBCP_ACK(RBCP_ACK)            ,    // in    : Access acknowledge
    .RBCP_RD(RBCP_RD)                    // in    : Read data[7:0]
);

// -------  BUS SYGNALING  ------- //

wire BUS_WR, BUS_RD, BUS_RST;
wire [31:0] BUS_ADD;
wire [7:0] BUS_DATA;
wire INVALID;
assign BUS_RST = SiTCP_RST;

tcp_to_bus itcp_to_bus (
    .BUS_RST(BUS_RST),
    .BUS_CLK(BUS_CLK),

    .TCP_RX_WC(TCP_RX_WC),
    .TCP_RX_WR(TCP_RX_WR),
    .TCP_RX_DATA(TCP_RX_DATA),

    .RBCP_ACT(RBCP_ACT),
    .RBCP_ADDR(RBCP_ADDR),
    .RBCP_WD(RBCP_WD),
    .RBCP_WE(RBCP_WE),
    .RBCP_RE(RBCP_RE),
    .RBCP_ACK(RBCP_ACK),
    .RBCP_RD(RBCP_RD),

    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),

    .INVALID(INVALID)
);

// -------  MODULE ADREESSES  ------- //

localparam TLU_BASEADDR = 32'h8200;
localparam TLU_HIGHADDR = 32'h8300-1;

localparam M26_RX_BASEADDR = 32'ha000;
localparam M26_RX_HIGHADDR = 32'ha00f-1;

localparam GPIO_BASEADDR = 32'hb000;
localparam GPIO_HIGHADDR = 32'hb01f;

localparam GPIO_CLK_BASEADDR = 32'hb020;
localparam GPIO_CLK_HIGHADDR = 32'hb02f;

// VERSION READBACK
reg [7:0] BUS_DATA_OUT;
always @ (posedge BUS_CLK) begin
    if(BUS_RD) begin
        if(BUS_ADD == 0)
            BUS_DATA_OUT <= VERSION[7:0];
    end
end

reg DATA_READ;
always @ (posedge BUS_CLK)
    if(BUS_RD & BUS_ADD < 2)
        DATA_READ <= 1;
    else
        DATA_READ <= 0;

assign BUS_DATA = DATA_READ ? BUS_DATA_OUT : 8'bz;


// -------  USER MODULES  ------- //
///////////////////// M26 JTAG
wire M26_TCK, M26_TMS, M26_TDI, M26_TDO, M26_TMS_INV, M26_TDI_INV, M26_TDO_INV;
wire M26_RESETB;
wire M26_CLK_START, M26_CLK_SPEAK, M26_CLK_RESET, M26_CLK_CLK;
wire [2:0] GPIO_JTAG_NC;
wire [3:0] GPIO_NC;
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW")
) OBUFDS_inst_m26_clk_start (
  .O(M26_CLK_START_P),
  .OB(M26_CLK_START_N),
  .I(M26_CLK_START)
);
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW")
) OBUFDS_inst_m26_clk_speak (
  .O(M26_CLK_SPEAK_P),
  .OB(M26_CLK_SPEAK_N),
  .I(M26_CLK_SPEAK)
);
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW")
) OBUFDS_inst_m26_clk_reset (
  .O(M26_CLK_RESET_P),
  .OB(M26_CLK_RESET_N),
  .I(M26_CLK_RESET)
);
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW")
) OBUFDS_inst_m26_clk_clk (
  .O(M26_CLK_CLK_P),
  .OB(M26_CLK_CLK_N),
  .I(M26_CLK_CLK)
);

OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW")
) OBUFDS_inst_m26_tck (
  .O(M26_TCK_P),
  .OB(M26_TCK_N),
  .I(M26_TCK)
);
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW")
) OBUFDS_inst_m26_tms (
  .O(M26_TMS_P),
  .OB(M26_TMS_N),
  .I(M26_TMS)
);
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW")
) OBUFDS_inst_m26_tdi (
  .O(M26_TDI_P),
  .OB(M26_TDI_N),
  .I(M26_TDI)
);
IBUFDS #(
    .DIFF_TERM("TRUE"),
    .IBUF_LOW_PWR("FALSE"),
    .IOSTANDARD("LVDS_25")
) IBUFDS_inst_m26_tdo (
    .O(M26_TDO),
    .I(M26_TDO_P),
    .IB(M26_TDO_N)
);
assign M26_TMS= ~M26_TMS_INV;
assign M26_TDI= ~M26_TDI_INV;
assign M26_TDO_INV = ~M26_TDO;

gpio #(
    .BASEADDR(GPIO_BASEADDR),
    .HIGHADDR(GPIO_HIGHADDR),
    .ABUSWIDTH(32),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hef),
    .IO_TRI(8'h00)
) i_gpio_jtag (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({GPIO_JTAG_NC, M26_TDO, M26_TDI_INV, M26_TMS_INV, M26_TCK, M26_RESETB})
);


gpio #(
    .BASEADDR(GPIO_CLK_BASEADDR),
    .HIGHADDR(GPIO_CLK_HIGHADDR),
    .ABUSWIDTH(32),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hff),
    .IO_TRI(8'h00)
) i_gpio_clk (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({GPIO_NC, M26_CLK_SPEAK, M26_CLK_RESET, M26_CLK_START, M26_CLK_CLK})
);

wire TRIGGER_ENABLE; // from CMD FSM
wire TRIGGER_ACCEPTED_FLAG;
wire EXT_TRIGGER_ENABLE;


wire TRIGGER_ACKNOWLEDGE_FLAG; // to TLU FSM
wire TRIGGER_FIFO_READ;
wire TRIGGER_FIFO_EMPTY;
wire [31:0] TRIGGER_FIFO_DATA;
wire [31:0] TIMESTAMP;
wire TLU_BUSY, TLU_CLOCK;

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(8),
    .ABUSWIDTH(32),
    .TLU_TRIGGER_MAX_CLOCK_CYCLES(32)
) i_tlu_controller (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .TRIGGER_CLK(CLK40),

    .FIFO_READ(TRIGGER_FIFO_READ),
    .FIFO_EMPTY(TRIGGER_FIFO_EMPTY),
    .FIFO_DATA(TRIGGER_FIFO_DATA),

    .FIFO_PREEMPT_REQ(),

    .TRIGGER({5'b0, LEMO_RX, RJ45_TRIGGER}),
    .TRIGGER_VETO({5'b0, LEMO_RX, FIFO_FULL}),
    .TIMESTAMP_RESET(1'b0),

    .TRIGGER_ENABLED(),
    .TRIGGER_SELECTED(),
    .TLU_ENABLED(),

    .EXT_TRIGGER_ENABLE(1'b0),
    .TRIGGER_ACKNOWLEDGE(TRIGGER_ACCEPTED_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),

    .TLU_TRIGGER(RJ45_TRIGGER),
    .TLU_RESET(RJ45_RESET),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),

    .EXT_TIMESTAMP(),
    .TIMESTAMP(TIMESTAMP)
);

assign RJ45_BUSY_LEMO_TX1 = TLU_BUSY;
assign LEMO_TX[1] = RJ45_BUSY_LEMO_TX1; // add LEMO TX0 and TX1 for MMC3 revision 1.2; LEMO TX0 and TX1 are not connected to RJ45_CLK_LEMO_TX0 and RJ45_BUSY_LEMO_TX1 anymore
assign RJ45_CLK_LEMO_TX0 = TLU_CLOCK;
assign LEMO_TX[0] = RJ45_CLK_LEMO_TX0; // add LEMO TX0 and TX1 for MMC3 revision 1.2; LEMO TX0 and TX1 are not connected to RJ45_CLK_LEMO_TX0 and RJ45_BUSY_LEMO_TX1 anymore

reg [31:0] timestamp_gray;
always@(posedge CLK40)
    timestamp_gray <= (TIMESTAMP>>1) ^ TIMESTAMP;

wire [5:0] M26_CLK;
wire [5:0] M26_CLK_BUFG;
wire [5:0] M26_MKD;
wire [5:0] M26_DATA0;
wire [5:0] M26_DATA0_RX;
wire [5:0] M26_DATA1;
wire [5:0] M26_DATA1_RX;

assign M26_DATA0 = ~M26_DATA0_RX;
assign M26_DATA1 = M26_DATA1_RX;

wire [5:0] LOST_ERROR;
wire [5:0] FIFO_READ_M26_RX;
wire [5:0] FIFO_EMPTY_M26_RX;
wire [31:0] FIFO_DATA_M26_RX [5:0];
// wire [5:0] M26_CLK_INV;
genvar ch;
generate
    for (ch = 0; ch < 6; ch = ch + 1) begin: m26_gen

        IBUFDS #(
            .DIFF_TERM("TRUE"),
            .IBUF_LOW_PWR("FALSE"),
            .IOSTANDARD("LVDS_25")
        ) IBUFDS_inst_M26_CLK(
            .O(M26_CLK[ch]),
            .I(M26_CLK_P[ch]),
            .IB(M26_CLK_N[ch])
        );

        IBUFDS #(
            .DIFF_TERM("TRUE"),
            .IBUF_LOW_PWR("FALSE"),
            .IOSTANDARD("LVDS_25")
        ) IBUFDS_inst_M26_MKD(
            .O(M26_MKD[ch]),
            .I(M26_MKD_P[ch]),
            .IB(M26_MKD_N[ch])
        );

        IBUFDS #(
            .DIFF_TERM("TRUE"),
            .IBUF_LOW_PWR("FALSE"),
            .IOSTANDARD("LVDS_25")
        ) IBUFDS_inst_M26_DATA0(
            .O(M26_DATA0_RX[ch]),
            .I(M26_DATA0_P[ch]),
            .IB(M26_DATA0_N[ch])
        );

        IBUFDS #(
            .DIFF_TERM("TRUE"),
            .IBUF_LOW_PWR("FALSE"),
            .IOSTANDARD("LVDS_25")
        ) IBUFDS_inst_M26_DATA1(
            .O(M26_DATA1_RX[ch]),
            .I(M26_DATA1_P[ch]),
            .IB(M26_DATA1_N[ch])
        );

        BUFG BUFG_inst_M26_CLK (.O(M26_CLK_BUFG[ch]), .I(M26_CLK[ch]));

        // assign M26_CLK_INV[ch] = ~M26_CLK[ch];

        reg [31:0] timestamp_cdc0, timestamp_cdc1, timestamp_m26;
        always@(posedge M26_CLK_BUFG[ch]) begin
            timestamp_cdc0 <= timestamp_gray;
            timestamp_cdc1 <= timestamp_cdc0;
        end

        integer gbi;
        always@(*) begin
            timestamp_m26[31] = timestamp_cdc1[31];
            for(gbi = 30; gbi >= 0; gbi = gbi - 1) begin
                timestamp_m26[gbi] = timestamp_cdc1[gbi] ^ timestamp_m26[gbi + 1];
            end
        end

        reg [31:0] TIMESTAMP_M26;
        always@(posedge M26_CLK_BUFG[ch]) begin
            TIMESTAMP_M26 <= timestamp_m26;
        end

        m26_rx
        #(
            .BASEADDR(M26_RX_BASEADDR + ch*16),
            .HIGHADDR(M26_RX_HIGHADDR + ch*16),
            .ABUSWIDTH(32),
            .HEADER(8'h20),
            .IDENTIFIER(ch+1)
        ) i_m26_rx (
            .CLK_RX(M26_CLK_BUFG[ch]),
            .MKD_RX(M26_MKD[ch]),
            .DATA_RX({M26_DATA1[ch], M26_DATA0[ch]}),

            .BUS_CLK(BUS_CLK),
            .BUS_RST(BUS_RST),
            .BUS_ADD(BUS_ADD),
            .BUS_DATA(BUS_DATA[7:0]),
            .BUS_RD(BUS_RD),
            .BUS_WR(BUS_WR),

            .FIFO_READ(FIFO_READ_M26_RX[ch]),
            .FIFO_EMPTY(FIFO_EMPTY_M26_RX[ch]),
            .FIFO_DATA(FIFO_DATA_M26_RX[ch]),

            .TIMESTAMP(TIMESTAMP_M26),

            .LOST_ERROR(LOST_ERROR[ch]),
            .INVALID(),
            .INVALID_FLAG()
        );

end
endgenerate

wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [6:0] READ_GRANT;

rrp_arbiter #(
    .WIDTH(7)
) i_rrp_arbiter (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~FIFO_EMPTY_M26_RX, ~TRIGGER_FIFO_EMPTY}),
    .HOLD_REQ(7'b0),
    .DATA_IN({FIFO_DATA_M26_RX[5], FIFO_DATA_M26_RX[4], FIFO_DATA_M26_RX[3], FIFO_DATA_M26_RX[2], FIFO_DATA_M26_RX[1], FIFO_DATA_M26_RX[0], TRIGGER_FIFO_DATA}),
    .READ_GRANT(READ_GRANT),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign TRIGGER_FIFO_READ = READ_GRANT[0];
assign FIFO_READ_M26_RX = READ_GRANT[6:1];


//cdc_fifo is for timing reasons
wire [31:0] cdc_data_out;
wire full_32to8, cdc_fifo_empty;
cdc_syncfifo #(
    .DSIZE(32),
    .ASIZE(3)
) cdc_syncfifo_i (
    .rdata(cdc_data_out),
    .wfull(FIFO_FULL),
    .rempty(cdc_fifo_empty),
    .wdata(ARB_DATA_OUT),
    .winc(ARB_WRITE_OUT),
    .wclk(BUS_CLK),
    .wrst(BUS_RST),
    .rinc(!full_32to8),
    .rclk(BUS_CLK),
    .rrst(BUS_RST)
);
assign ARB_READY_OUT = !FIFO_FULL;

wire FIFO_EMPTY, FIFO_FULL;
fifo_32_to_8 #(
    .DEPTH(256*1024)
) i_data_fifo (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE(!cdc_fifo_empty),
    .READ(TCP_TX_WR),
    .DATA_IN(cdc_data_out),
    .FULL(full_32to8),
    .EMPTY(FIFO_EMPTY),
    .DATA_OUT(TCP_TX_DATA)
);

assign TCP_TX_WR = !TCP_TX_FULL && !FIFO_EMPTY;

wire CLK_1HZ;
clock_divider #(
    .DIVISOR(40000000)
) i_clock_divisor_40MHz_to_1Hz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(),
    .CLOCK(CLK_1HZ)
);

wire CLK_3HZ;
clock_divider #(
    .DIVISOR(13333333)
) i_clock_divisor_40MHz_to_3Hz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(),
    .CLOCK(CLK_3HZ)
);

assign LED[7:4] = ~{clock_speed, duplex_status, (|clock_speed & link_status & (GMII_1000M ? CLK_1HZ : CLK_3HZ)) | INVALID};
assign LED[0] = CLK_1HZ;
assign LED[1] = ~FIFO_FULL;
assign LED[2] = ~|LOST_ERROR;
assign LED[3] = 1'b1;

endmodule
