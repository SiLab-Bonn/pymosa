set_property PACKAGE_PIN AA3 [get_ports clkin]
set_property IOSTANDARD LVCMOS15 [get_ports clkin]

set_property PACKAGE_PIN C18 [get_ports RESET_N]
set_property IOSTANDARD LVCMOS25 [get_ports RESET_N]
set_property PULLUP true [get_ports RESET_N]

set_property SLEW FAST [get_ports mdio_phy_mdc]
set_property IOSTANDARD LVCMOS25 [get_ports mdio_phy_mdc]
set_property PACKAGE_PIN N16 [get_ports mdio_phy_mdc]

set_property SLEW FAST [get_ports mdio_phy_mdio]
set_property IOSTANDARD LVCMOS25 [get_ports mdio_phy_mdio]
set_property PACKAGE_PIN U16 [get_ports mdio_phy_mdio]

set_property SLEW FAST [get_ports phy_rst_n]
set_property IOSTANDARD LVCMOS25 [get_ports phy_rst_n]
set_property PACKAGE_PIN M20 [get_ports phy_rst_n]

set_property IOSTANDARD LVCMOS25 [get_ports rgmii_rxc]
set_property PACKAGE_PIN R21 [get_ports rgmii_rxc]

set_property IOSTANDARD LVCMOS25 [get_ports rgmii_rx_ctl]
set_property PACKAGE_PIN P21 [get_ports rgmii_rx_ctl]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[0]}]
set_property PACKAGE_PIN P16 [get_ports {rgmii_rxd[0]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[1]}]
set_property PACKAGE_PIN N17 [get_ports {rgmii_rxd[1]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[2]}]
set_property PACKAGE_PIN R16 [get_ports {rgmii_rxd[2]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[3]}]
set_property PACKAGE_PIN R17 [get_ports {rgmii_rxd[3]}]

set_property SLEW FAST [get_ports rgmii_txc]
set_property IOSTANDARD LVCMOS25 [get_ports rgmii_txc]
set_property PACKAGE_PIN R18 [get_ports rgmii_txc]

set_property SLEW FAST [get_ports rgmii_tx_ctl]
set_property IOSTANDARD LVCMOS25 [get_ports rgmii_tx_ctl]
set_property PACKAGE_PIN P18 [get_ports rgmii_tx_ctl]

set_property SLEW FAST [get_ports {rgmii_txd[0]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[0]}]
set_property PACKAGE_PIN N18 [get_ports {rgmii_txd[0]}]
set_property SLEW FAST [get_ports {rgmii_txd[1]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[1]}]
set_property PACKAGE_PIN M19 [get_ports {rgmii_txd[1]}]
set_property SLEW FAST [get_ports {rgmii_txd[2]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[2]}]
set_property PACKAGE_PIN U17 [get_ports {rgmii_txd[2]}]
set_property SLEW FAST [get_ports {rgmii_txd[3]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[3]}]
set_property PACKAGE_PIN T17 [get_ports {rgmii_txd[3]}]


set_property PACKAGE_PIN M17 [get_ports {LED[0]}]
set_property PACKAGE_PIN L18 [get_ports {LED[1]}]
set_property PACKAGE_PIN L17 [get_ports {LED[2]}]
set_property PACKAGE_PIN K18 [get_ports {LED[3]}]
set_property PACKAGE_PIN P26 [get_ports {LED[4]}]
set_property PACKAGE_PIN M25 [get_ports {LED[5]}]
set_property PACKAGE_PIN L25 [get_ports {LED[6]}]
set_property PACKAGE_PIN P23 [get_ports {LED[7]}]
set_property IOSTANDARD LVCMOS25 [get_ports LED*]
set_property SLEW SLOW [get_ports LED*]


# Mimosa26 IO
set_property PACKAGE_PIN F9 [get_ports {M26_DATA1_P[0]}]
set_property PACKAGE_PIN F8 [get_ports {M26_DATA1_N[0]}]
set_property PACKAGE_PIN C12 [get_ports {M26_MKD_P[0]}]
set_property PACKAGE_PIN C11 [get_ports {M26_MKD_N[0]}]
set_property PACKAGE_PIN G12 [get_ports {M26_DATA0_P[0]}]
set_property PACKAGE_PIN F12 [get_ports {M26_DATA0_N[0]}]
set_property PACKAGE_PIN C14 [get_ports {M26_CLK_P[0]}]
set_property PACKAGE_PIN C13 [get_ports {M26_CLK_N[0]}]

set_property PACKAGE_PIN B12 [get_ports {M26_DATA1_P[1]}]
set_property PACKAGE_PIN B11 [get_ports {M26_DATA1_N[1]}]
set_property PACKAGE_PIN B15 [get_ports {M26_MKD_P[1]}]
set_property PACKAGE_PIN A15 [get_ports {M26_MKD_N[1]}]
set_property PACKAGE_PIN B17 [get_ports {M26_DATA0_P[1]}]
set_property PACKAGE_PIN A17 [get_ports {M26_DATA0_N[1]}]
set_property PACKAGE_PIN C19 [get_ports {M26_CLK_P[1]}]
set_property PACKAGE_PIN B19 [get_ports {M26_CLK_N[1]}]

set_property PACKAGE_PIN D15 [get_ports {M26_DATA1_P[2]}]
set_property PACKAGE_PIN D16 [get_ports {M26_DATA1_N[2]}]
set_property PACKAGE_PIN H16 [get_ports {M26_MKD_P[2]}]
set_property PACKAGE_PIN G16 [get_ports {M26_MKD_N[2]}]
set_property PACKAGE_PIN G17 [get_ports {M26_DATA0_P[2]}]
set_property PACKAGE_PIN F18 [get_ports {M26_DATA0_N[2]}]
set_property PACKAGE_PIN J15 [get_ports {M26_CLK_P[2]}]
set_property PACKAGE_PIN J16 [get_ports {M26_CLK_N[2]}]

set_property PACKAGE_PIN J13 [get_ports {M26_CLK_P[3]}]
set_property PACKAGE_PIN H13 [get_ports {M26_CLK_N[3]}]
set_property PACKAGE_PIN H14 [get_ports {M26_DATA0_P[3]}]
set_property PACKAGE_PIN G14 [get_ports {M26_DATA0_N[3]}]
set_property PACKAGE_PIN E10 [get_ports {M26_MKD_P[3]}]
set_property PACKAGE_PIN D10 [get_ports {M26_MKD_N[3]}]
set_property PACKAGE_PIN A9 [get_ports {M26_DATA1_P[3]}]
set_property PACKAGE_PIN A8 [get_ports {M26_DATA1_N[3]}]

set_property PACKAGE_PIN H9 [get_ports {M26_CLK_P[4]}]
set_property PACKAGE_PIN H8 [get_ports {M26_CLK_N[4]}]
set_property PACKAGE_PIN F14 [get_ports {M26_DATA0_P[4]}]
set_property PACKAGE_PIN F13 [get_ports {M26_DATA0_N[4]}]
set_property PACKAGE_PIN E11 [get_ports {M26_MKD_P[4]}]
set_property PACKAGE_PIN D11 [get_ports {M26_MKD_N[4]}]
set_property PACKAGE_PIN D14 [get_ports {M26_DATA1_P[4]}]
set_property PACKAGE_PIN D13 [get_ports {M26_DATA1_N[4]}]

set_property PACKAGE_PIN E13 [get_ports {M26_CLK_P[5]}]
set_property PACKAGE_PIN E12 [get_ports {M26_CLK_N[5]}]
set_property PACKAGE_PIN B14 [get_ports {M26_DATA0_P[5]}]
set_property PACKAGE_PIN A14 [get_ports {M26_DATA0_N[5]}]
set_property PACKAGE_PIN B10 [get_ports {M26_MKD_P[5]}]
set_property PACKAGE_PIN A10 [get_ports {M26_MKD_N[5]}]
set_property PACKAGE_PIN C16 [get_ports {M26_DATA1_P[5]}]
set_property PACKAGE_PIN B16 [get_ports {M26_DATA1_N[5]}]


# Port 7
set_property IOSTANDARD LVDS_25 [get_ports M26_TCK*]
set_property PACKAGE_PIN A18 [get_ports M26_TCK_P]
set_property PACKAGE_PIN A19 [get_ports M26_TCK_N]

set_property IOSTANDARD LVDS_25 [get_ports M26_TMS*]
set_property PACKAGE_PIN F17 [get_ports M26_TMS_P]
set_property PACKAGE_PIN E17 [get_ports M26_TMS_N]

set_property IOSTANDARD LVDS_25 [get_ports M26_TDI*]
set_property PACKAGE_PIN E15 [get_ports M26_TDI_P]
set_property PACKAGE_PIN E16 [get_ports M26_TDI_N]

set_property PACKAGE_PIN G15 [get_ports M26_TDO_P]
set_property PACKAGE_PIN F15 [get_ports M26_TDO_N]
set_property IOSTANDARD LVDS_25 [get_ports M26_TDO*]

set_property PACKAGE_PIN C9 [get_ports M26_CLK_CLK_P]
set_property PACKAGE_PIN D9 [get_ports M26_CLK_RESET_P]
set_property PACKAGE_PIN J11 [get_ports M26_CLK_SPEAK_P]
set_property PACKAGE_PIN H12 [get_ports M26_CLK_START_P]

set_property IOSTANDARD LVDS_25 [get_ports M26_*]


# TLU/Trigger
set_property PACKAGE_PIN V23 [get_ports RJ45_BUSY_LEMO_TX1]
set_property PACKAGE_PIN AB21 [get_ports RJ45_CLK_LEMO_TX0]
set_property PACKAGE_PIN V21 [get_ports RJ45_TRIGGER]
set_property PACKAGE_PIN Y25 [get_ports RJ45_RESET]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_BUSY_LEMO_TX1]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_CLK_LEMO_TX0]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_RESET]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_TRIGGER]

set_property PACKAGE_PIN U26 [get_ports {LEMO_RX[1]}]
set_property PACKAGE_PIN U22 [get_ports {LEMO_RX[0]}]
set_property IOSTANDARD LVCMOS25 [get_ports LEMO_RX*]
# add LEMO TX0 and TX1 for MMC3 revision 1.2; LEMO TX0 and TX1 are not connected to RJ45_CLK_LEMO_TX0 and RJ45_BUSY_LEMO_TX1 anymore
set_property PACKAGE_PIN V22 [get_ports {LEMO_TX[0]}]
set_property PACKAGE_PIN W21 [get_ports {LEMO_TX[1]}]
set_property IOSTANDARD LVCMOS25 [get_ports LEMO_TX*]


# PMOD
# +-------------------------+
# | 6(VCC)  5(GND)  4 3 2 1 |*
# |12(VCC) 11(GND) 10 9 8 7 |
# +-------------------------+
#
# PMOD connector pin 1-->PMOD[0]; pin 2-->PMOD[1]; pin 3-->PMOD[2]; pin 4-->PMOD[3];
set_property PACKAGE_PIN V26 [get_ports {PMOD[0]}]
set_property PACKAGE_PIN V24 [get_ports {PMOD[1]}]
set_property PACKAGE_PIN AB25 [get_ports {PMOD[2]}]
set_property PACKAGE_PIN AA25 [get_ports {PMOD[3]}]
# PMOD connector pin 7-->PMOD[4]; pin 8-->PMOD[5]; pin 9-->PMOD[6]; pin 10-->PMOD[7];
set_property PACKAGE_PIN W26 [get_ports {PMOD[4]}]
set_property PACKAGE_PIN W25 [get_ports {PMOD[5]}]
set_property PACKAGE_PIN AC24 [get_ports {PMOD[6]}]
set_property PACKAGE_PIN AC23 [get_ports {PMOD[7]}]
set_property IOSTANDARD LVCMOS25 [get_ports PMOD*]
set_property DRIVE 16 [get_ports PMOD*]
# pull down the PMOD pins which are used as inputs
set_property PULLDOWN true [get_ports {PMOD[0]}]
set_property PULLDOWN true [get_ports {PMOD[1]}]
set_property PULLDOWN true [get_ports {PMOD[2]}]
set_property PULLDOWN true [get_ports {PMOD[3]}]


# Clocks
create_clock -period 10.000 -name clkin -add [get_ports clkin]
create_clock -period 8.000 -name rgmii_rxc -add [get_ports rgmii_rxc]
# create_generated_clock -name CLK_MII_TX -source [get_pins rgmii/ODDR_inst/C] -divide_by 1 [get_ports rgmii_txc]
set_clock_groups -asynchronous \
-group [get_clocks -include_generated_clocks clkin] \
-group rgmii_rxc
set_clock_groups -logically_exclusive \
-group rgmii_rxc \
-group {CLK125_PLL CLK125_90_PLL}
create_clock -period 12.500 -name m26_clk0 -add [get_ports {M26_CLK_P[0]}]
create_clock -period 12.500 -name m26_clk1 -add [get_ports {M26_CLK_P[1]}]
create_clock -period 12.500 -name m26_clk2 -add [get_ports {M26_CLK_P[2]}]
create_clock -period 12.500 -name m26_clk3 -add [get_ports {M26_CLK_P[3]}]
create_clock -period 12.500 -name m26_clk4 -add [get_ports {M26_CLK_P[4]}]
create_clock -period 12.500 -name m26_clk5 -add [get_ports {M26_CLK_P[5]}]

set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_0]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_1]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_2]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_3]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_4]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_5]


# Timing Constraints
# set false path for GMII mode selector
set_false_path -from [get_pins GMII_1000M_reg/C]
# set false path for some outputs
set_false_path -to [get_ports PMOD*]
set_false_path -to [get_ports LED*]
# set max delay for CDC
set_max_delay -from [get_clocks -of_objects [get_pins PLLE2_BASE_inst_2/CLKOUT1]] -to [get_clocks m26_clk*] 7.5 -datapath_only
set_max_delay -from [get_clocks m26_clk*] -to [get_clocks -of_objects [get_pins PLLE2_BASE_inst_2/CLKOUT1]] 12.5 -datapath_only
# set false path and max delay for some control registers
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_lemo_trigger_synchronizer_trg_clk/out_d_ff_1_reg[0]/D}]
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_lemo_ext_veto_synchronizer_trg_clk/out_d_ff_1_reg[0]/D}]
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_trigger_mode_synchronizer/out_d_ff_1_reg[*]/D}]
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_trigger_data_msb_first_synchronizer/out_d_ff_1_reg[0]/D}]
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_conf_trigger_enable_synchronizer/out_d_ff_1_reg[0]/D}]
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_conf_ext_ts_synchronizer/out_d_ff_1_reg[0]/D}]
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_conf_data_format_synchronizer/out_d_ff_1_reg[*]/D}]
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_enable_tlu_reset_ts_synchronizer/out_d_ff_1_reg[0]/D}]
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/status_regs_reg[*][*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/three_stage_tlu_en_veto_synchronizer/out_d_ff_1_reg[0]/D}]
set_false_path -from [get_pins -regexp {i_tlu_controller/i_tlu_controller_core/status_regs_reg\[([2-7]|2[5-9]|30|33|35)\]\[([0-7])\]/C}]
set_max_delay -from [get_pins {i_tlu_controller/i_tlu_controller_core/TRIGGER_COUNTER_reg[*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/TRIGGER_COUNTER_SYNC_reg[*]/D}] 10.0
set_false_path -from [get_pins {i_tlu_controller/i_tlu_controller_core/LOST_DATA_CNT_reg[*]/C}] -to [get_pins {i_tlu_controller/i_tlu_controller_core/BUS_DATA_OUT_reg[*]/D}]

set_false_path -from [get_pins {m26_gen[*].i_m26_rx/i_m26_rx_core/status_regs_reg[*][*]/C}] -to [get_pins {m26_gen[*].i_m26_rx/i_m26_rx_core/conf_en_synchronizer_clk_rx/out_d_ff_1_reg[0]/D}]
set_false_path -from [get_pins {m26_gen[*].i_m26_rx/i_m26_rx_core/status_regs_reg[*][*]/C}] -to [get_pins {m26_gen[*].i_m26_rx/i_m26_rx_core/conf_timestamp_header_synchronizer_clk_rx/out_d_ff_1_reg[0]/D}]
# set_false_path -from [get_pins {m26_gen[*].i_m26_rx/i_m26_rx_core/LOST_DATA_CNT_reg[*]/C}] -to [get_pins {m26_gen[*].i_m26_rx/i_m26_rx_core/BUS_DATA_OUT_reg[*]/D}]


# Other
set_property BITSTREAM.CONFIG.UNUSEDPIN PULLUP [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
