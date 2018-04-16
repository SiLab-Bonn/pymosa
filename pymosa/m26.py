#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import logging
import os
from time import time, sleep, strftime
from contextlib import contextmanager
from threading import Timer

import yaml
import progressbar

from basil.dut import Dut
from basil.utils.BitLogic import BitLogic

from m26_raw_data import open_raw_data_file, send_meta_data, save_configuration_dict
from m26_readout import M26Readout

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REQUIRED_FW_VERSION = 3  # required version for mmc3_m26_eth.v


class m26():
    ''' Mimosa26 telescope readout with MMC3 hardware.

    Note:
    - Remove not used Mimosa26 planes by commenting out the drivers in the DUT file (i.e. m26.yaml).
    - Set up trigger in DUT configuration file (i.e. m26_configuration.yaml).
    '''
    def __init__(self, conf=None):
        if conf is None:
            conf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m26.yaml")
        logger.info("Loading DUT configuration from file %s" % conf)

        # initialize class
        self.dut = Dut(conf=conf)

    def init(self, init_conf=None, configure_m26=True):
        # initialize hardware
        logging.info("Initializing Telescope...")
        self.dut.init(init_conf=init_conf)
        self.telescope_conf = init_conf

        # check firmware version
        fw_version = self.dut['ETH'].read(0x0000, 1)[0]
        logging.info("MMC3 firmware version: %s" % (fw_version))
        if fw_version != REQUIRED_FW_VERSION:
            raise Exception("MMC3 firmware version does not satisfy version requirements (read: %s, require: %s)" % (fw_version, REQUIRED_FW_VERSION))

        # default configuration
        # use self.telescope_conf to store conf dict to telescope data file
        self.telescope_conf["fw_version"] = fw_version
        self.m26_configuration_file = self.telescope_conf.get("m26_configuration_file", None)
        self.m26_jtag_configuration = self.telescope_conf.get('m26_jtag_configuration', True)  # default True
        self.no_data_timeout = self.telescope_conf.get('no_data_timeout', 0)  # default None: no data timeout
        self.scan_timeout = self.telescope_conf.get('scan_timeout', 0)  # default 0: no scan timeout
        self.max_triggers = self.telescope_conf.get('max_triggers', 0)  # default 0: infinity triggers
        self.send_data = self.telescope_conf.get('send_data', None)  # default None: do not send data to online monitor
        self.working_dir = os.path.join(os.getcwd(), self.telescope_conf.get("output_folder", "telescope_data"))
        self.output_filename = self.telescope_conf.get('filename', None)  # default None: filename is generated

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        logger.info("Storing telescope data in %s" % self.working_dir)

        self.scan_id = 'M26_TELESCOPE'

        if self.output_filename is None:
            self.run_name = strftime("%Y%m%d_%H%M%S_") + self.scan_id
            self.output_filename = os.path.join(self.working_dir, self.run_name)
        else:
            self.run_name = os.path.basename(os.path.realpath(self.output_filename))

        # configure Mimosa26 sensors
        if configure_m26:
            self.configure_m26()

        # FIFO readout
        self.m26_readout = M26Readout(dut=self.dut)

    def configure_m26(self, m26_configuration_file=None, m26_jtag_configuration=None):
        '''Configure Mimosa26 sensors via JTAG.
        '''
        if m26_configuration_file:
            self.m26_configuration_file = m26_configuration_file
        else:
            m26_configuration_file = self.m26_configuration_file
        if not self.m26_configuration_file:
            raise ValueError('M26 configuration file not provided')
        logger.info('Loading M26 configuration file %s', m26_configuration_file)

        def write_jtag(irs, IR):
            for i, ir in enumerate(irs):
                logger.info('Programming M26 JTAG configuration reg %s', ir)
                logger.debug(self.dut[ir][:])
                self.dut['JTAG'].scan_ir([BitLogic(IR[ir])] * 6)
                self.dut['JTAG'].scan_dr([self.dut[ir][:]])[0]

        def check_jtag(irs, IR):
            # read first registers
            ret = {}
            for i, ir in enumerate(irs):
                logger.info('Reading M26 JTAG configuration reg %s', ir)
                self.dut['JTAG'].scan_ir([BitLogic(IR[ir])] * 6)
                ret[ir] = self.dut['JTAG'].scan_dr([self.dut[ir][:]])[0]
            # check registers
            for k, v in ret.iteritems():
                if k == "CTRL_8b10b_REG1_ALL":
                    pass
                elif k == "BSR_ALL":
                    pass  # TODO mask clock bits and check others
                elif self.dut[k][:] != v:
                    logger.error(
                        "JTAG data does not match %s get=%s set=%s" % (k, v, self.dut[k][:]))
                else:
                    logger.info("Checking M26 JTAG %s ok" % k)

        # set the clock distributer inputs in correct states.
        self.set_clock_distributer()

        # set M26 configuration file
        self.dut.set_configuration(m26_configuration_file)

        if m26_jtag_configuration is not None:
            self.m26_jtag_configuration = m26_jtag_configuration
        else:
            m26_jtag_configuration = self.m26_jtag_configuration
        if m26_jtag_configuration:
            # reset JTAG; this is important otherwise JTAG programming works not properly.
            self.dut['JTAG'].reset()

            IR = {"BSR_ALL": '00101', "DEV_ID_ALL": '01110', "BIAS_DAC_ALL": '01111', "LINEPAT0_REG_ALL": '10000',
                  "DIS_DISCRI_ALL": '10001', "SEQUENCER_PIX_REG_ALL": '10010', "CONTROL_PIX_REG_ALL": '10011',
                  "LINEPAT1_REG_ALL": '10100', "SEQUENCER_SUZE_REG_ALL": '10101', "HEADER_REG_ALL": '10110',
                  "CONTROL_SUZE_REG_ALL": '10111', "CTRL_8b10b_REG0_ALL": '11000', "CTRL_8b10b_REG1_ALL": '11001',
                  "RO_MODE1_ALL": '11101', "RO_MODE0_ALL": '11110', "BYPASS_ALL": '11111'}

            irs = ["DEV_ID_ALL", "BIAS_DAC_ALL", "BYPASS_ALL", "BSR_ALL", "RO_MODE0_ALL", "RO_MODE1_ALL", "DIS_DISCRI_ALL",
                   "LINEPAT0_REG_ALL", "LINEPAT1_REG_ALL", "CONTROL_PIX_REG_ALL", "SEQUENCER_PIX_REG_ALL",
                   "HEADER_REG_ALL", "CONTROL_SUZE_REG_ALL", "SEQUENCER_SUZE_REG_ALL", "CTRL_8b10b_REG0_ALL",
                   "CTRL_8b10b_REG1_ALL"]

            # write JTAG configuration
            write_jtag(irs, IR)

            # check if registers are properly programmed by reading them and comparing to settings.
            check_jtag(irs, IR)

            # START procedure
            logger.info('Starting M26')
            temp = self.dut['RO_MODE0_ALL'][:]
            # disable extstart
            for reg in self.dut["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['En_ExtStart'] = 0
                reg['JTAG_Start'] = 0
            self.dut['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self.dut['JTAG'].scan_dr([self.dut['RO_MODE0_ALL'][:]])
            # JTAG start
            for reg in self.dut["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['JTAG_Start'] = 1
            self.dut['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self.dut['JTAG'].scan_dr([self.dut['RO_MODE0_ALL'][:]])
            for reg in self.dut["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['JTAG_Start'] = 0
            self.dut['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self.dut['JTAG'].scan_dr([self.dut['RO_MODE0_ALL'][:]])
            # write original configuration
            self.dut['RO_MODE0_ALL'][:] = temp
            self.dut['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self.dut['JTAG'].scan_dr([self.dut['RO_MODE0_ALL'][:]])
            # readback?
            self.dut['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self.dut['JTAG'].scan_dr([self.dut['RO_MODE0_ALL'][:]] * 6)
        else:
            logger.info("Skipping M26 JTAG configuration")

    def set_clock_distributer(self, clk=0, start=1, reset=0, speak=1):
        # Default values -same as in GUI- (self, clk=0, start=1, reset=0, speak=1)
        self.dut["START_RESET"]["CLK"] = clk
        self.dut["START_RESET"]["START"] = start
        self.dut["START_RESET"]["RESET"] = reset
        self.dut["START_RESET"]["SPEAK"] = speak
        self.dut["START_RESET"].write()

    def reset(self, reset_time=2):
        self.dut["START_RESET"]["RESET"] = 1
        self.dut["START_RESET"].write()
        sleep(reset_time)
        self.dut["START_RESET"]["RESET"] = 0
        self.dut["START_RESET"].write()

    def scan(self):
        '''Scan Mimosa26 telescope loop.
        '''
        with self.readout():
            got_data = False
            self.stop_scan = False
            start = time()
            while not self.stop_scan:
                try:
                    sleep(1.0)
                    if not got_data:
                        if self.m26_readout.data_words_per_second() > 0:
                            got_data = True
                            logging.info('Taking data...')
                            if self.max_triggers:
                                self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=self.max_triggers, poll=10, term_width=80).start()
                            else:
                                self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.Timer()], maxval=self.scan_timeout, poll=10, term_width=80).start()
                    else:
                        triggers = self.dut['TLU']['TRIGGER_COUNTER']
                        try:
                            if self.max_triggers:
                                self.progressbar.update(triggers)
                            else:
                                self.progressbar.update(time() - start)
                        except ValueError:
                            pass
                        if self.max_triggers and triggers >= self.max_triggers:
                            self.stop_scan = True
                            self.progressbar.finish()
                            logging.info('Trigger limit was reached: %i' % self.max_triggers)
                except KeyboardInterrupt:  # react on keyboard interupt
                    logging.info('Scan was stopped due to keyboard interrupt')
                    self.stop_scan = True

        logging.info('Total amount of triggers collected: %d', self.dut['TLU']['TRIGGER_COUNTER'])

    def start(self):
        '''Start Mimosa26 telescope scan.
        '''
        self.fh = logging.FileHandler(self.output_filename + '.log')
        self.fh.setLevel(logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.addHandler(self.fh)

        with self.access_file():
            save_configuration_dict(self.raw_data_file.h5_file, 'configuration', self.telescope_conf)
            self.scan()

        self.logger.removeHandler(self.fh)

        logging.info('Data Output Filename: %s', self.output_filename + '.h5')

    @contextmanager
    def readout(self):
        try:
            self.start_readout()
            yield
        finally:
            try:
                self.stop_readout(timeout=10.0)
            except Exception:
                # in case something fails, call this on last resort
                if self.m26_readout.is_running:
                    self.m26_readout.stop(timeout=0.0)

    def start_readout(self):
        '''Start readout of Mimosa26 sensors.
        '''
        self.m26_readout.start(
            fifos="SITCP_FIFO",
            callback=self.handle_data,
            errback=self.handle_err,
            reset_rx=True,
            reset_fifo=True,
            no_data_timeout=self.no_data_timeout,
            enabled_m26_channels=[rx.name for rx in self.dut.get_modules('m26_rx')])

        self.dut['TLU']['MAX_TRIGGERS'] = self.max_triggers
        self.dut['TLU']['TRIGGER_ENABLE'] = True
        self.m26_readout.print_readout_status()

        def timeout():
            try:
                self.progressbar.finish()
            except AttributeError:
                pass
            self.stop_scan = True
            logging.info('Scan timeout was reached')

        self.scan_timeout_timer = Timer(self.scan_timeout, timeout)
        if self.scan_timeout:
            self.scan_timeout_timer.start()

    def stop_readout(self, timeout=10.0):
        '''Stop readout of Mimosa26 sensors.
        '''
        self.scan_timeout_timer.cancel()
        self.dut['TLU']['TRIGGER_ENABLE'] = False
        self.m26_readout.stop(timeout=timeout)
        self.m26_readout.print_readout_status()

    @contextmanager
    def access_file(self):
        try:
            self.open_file()
            yield
        finally:
            try:
                self.close_file()
            except Exception:
                # in case something fails, call this on last resort
                self.raw_data_file = None

    def open_file(self):
        self.raw_data_file = open_raw_data_file(filename=self.output_filename,
                                                mode='w',
                                                title=self.run_name,
                                                socket_address=self.send_data)
        if self.raw_data_file.socket:
            # send reset to indicate a new scan for the online monitor
            send_meta_data(self.raw_data_file.socket, None, name='Reset')

    def close_file(self):
        # close file object
        self.raw_data_file.close()
        # delete file object
        self.raw_data_file = None

    def handle_data(self, data, new_file=False, flush=True):
        '''Handling of raw data and meta data during readout.
        '''
        for i, data_tuple in enumerate(data):
            if data_tuple is None:
                continue
            self.raw_data_file.append(data_iterable=data_tuple, new_file=new_file, flush=True)

    def handle_err(self, exc):
        '''Handling of error messages during readout.
        '''
        msg = '%s' % exc[1]
        if msg:
            logging.error('%s%s Aborting run...', msg, msg[-1])
        else:
            logging.error('Aborting run...')
        self.stop_scan = True


if __name__ == '__main__':
    from pymosa import __version__ as pymosa_version
    import argparse
    parser = argparse.ArgumentParser(description='Pymosa %s\nExample: python m26.py --no-m26-jtag-configuration --filename <output filename>' % pymosa_version, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-f', '--filename', type=str, metavar='<output filename>', action='store', help='filename of the telescope data file')
    parser.add_argument('--scan_timeout', type=int, metavar='<scan timeout>', action='store', help="scan timeout in seconds, default: 0 (disabled)")
    parser.add_argument('--max_triggers', type=int, metavar='<number of triggers>', action='store', help="maximum number of triggers, default: 0 (disabled)")
    parser.add_argument('--no-m26-jtag-configuration', dest='no_m26_jtag_configuration', action='store_true', help='disable Mimosa26 configuration via JTAG.')
    parser.set_defaults(no_m26_jtag_configuration=False)
    args = parser.parse_args()

    with open('./m26_configuration.yaml', 'r') as f:
        config = yaml.load(f)

    print args
    if args.filename is not None:
        config["filename"] = args.filename
    if args.scan_timeout is not None:
        config["scan_timeout"] = args.scan_timeout
    if args.max_triggers is not None:
        config["max_triggers"] = args.max_triggers
    if args.no_m26_jtag_configuration:
        config["m26_jtag_configuration"] = False

    # Create telescope object and load hardware configuration
    telescope = m26(conf=None)  # None: use default hardware configuration
    # Initialize telescope hardware and set up parameters
    telescope.init(init_conf=config)
    # Start telescope readout
    telescope.start()
