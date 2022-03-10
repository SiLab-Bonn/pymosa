#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import logging
import os
import signal
from contextlib import contextmanager
from threading import Timer
from time import sleep, strftime, time

import yaml
from basil.dut import Dut
from basil.utils.BitLogic import BitLogic
from tqdm import tqdm

import pymosa
from pymosa.m26_raw_data import open_raw_data_file, save_configuration_dict, send_meta_data
from pymosa.m26_readout import M26Readout

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
FORMAT = '%(asctime)s [%(name)-17s] - %(levelname)-7s %(message)s'


class m26(object):
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
        logging.info("Pymosa MMC3 firmware version: %s" % (fw_version))
        if int(self.dut.version) != fw_version:
            raise Exception("Pymosa MMC3 firmware version does not match DUT configuration file (read: %s, require: %s)" % (fw_version, int(self.dut.version)))

        # default configuration
        # use self.telescope_conf to store conf dict to telescope data file
        self.telescope_conf["fw_version"] = fw_version
        self.run_id = self.telescope_conf.get('run_id', 'M26_TELESCOPE')
        self.working_dir = self.telescope_conf.get("output_folder", None)
        if not self.working_dir:
            self.working_dir = os.path.join(os.getcwd(), "telescope_data")
        self.working_dir = os.path.normpath(self.working_dir.replace('\\', '/'))
        self.output_filename = self.telescope_conf.get('filename', None)  # default None: filename is generated
        if self.output_filename:
            self.output_filename = os.path.basename(self.output_filename)
        self.run_number = self.telescope_conf.get('run_number', None)
        self.m26_configuration_file = self.telescope_conf.get('m26_configuration_file', None)
        if not self.m26_configuration_file:
            self.m26_configuration_file = 'm26_config/m26_threshold_8.yaml'
        self.m26_jtag_configuration = self.telescope_conf.get('m26_jtag_configuration', True)  # default True
        self.no_data_timeout = self.telescope_conf.get('no_data_timeout', 0)  # default None: no data timeout
        self.scan_timeout = self.telescope_conf.get('scan_timeout', 0)  # default 0: no scan timeout
        self.max_triggers = self.telescope_conf.get('max_triggers', 0)  # default 0: infinity triggers
        self.send_data = self.telescope_conf.get('send_data', None)  # default None: do not send data to online monitor
        self.enabled_m26_channels = self.telescope_conf.get('enabled_m26_channels', None)  # default None: all channels enabled

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        logger.info("Storing telescope data in %s" % self.working_dir)

        # configure Mimosa26 sensors
        if configure_m26:
            self.configure_m26()

        # FIFO readout
        self.m26_readout = M26Readout(dut=self.dut)

    def close(self):
        self.dut.close()

    def configure_m26(self, m26_configuration_file=None, m26_jtag_configuration=None):
        '''Configure Mimosa26 sensors via JTAG.
        '''
        if m26_configuration_file:
            self.m26_configuration_file = m26_configuration_file
        else:
            m26_configuration_file = os.path.join(os.path.dirname(pymosa.__file__), self.m26_configuration_file)
        if not self.m26_configuration_file:
            raise ValueError('M26 configuration file not provided')
        logger.info('Loading M26 configuration file %s', m26_configuration_file)

        def write_jtag(irs, IR):
            for ir in irs:
                logger.info('Programming M26 JTAG configuration reg %s', ir)
                logger.debug(self.dut[ir][:])
                self.dut['JTAG'].scan_ir([BitLogic(IR[ir])] * 6)
                self.dut['JTAG'].scan_dr([self.dut[ir][:]])[0]

        def check_jtag(irs, IR):
            # read first registers
            ret = {}
            for ir in irs:
                logger.info('Reading M26 JTAG configuration reg %s', ir)
                self.dut['JTAG'].scan_ir([BitLogic(IR[ir])] * 6)
                ret[ir] = self.dut['JTAG'].scan_dr([self.dut[ir][:]])[0]
            # check registers
            for k, v in ret.items():
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
        with self.readout(enabled_m26_channels=self.enabled_m26_channels):
            got_data = False
            start = time()
            while not self.stop_scan:
                sleep(1.0)
                if not got_data:
                    if self.m26_readout.data_words_per_second()[0] > 0:
                        got_data = True
                        logging.info('Taking data...')
                        if self.max_triggers:
                            self.pbar = tqdm(total=self.max_triggers, ncols=80)
                        else:
                            self.pbar = tqdm(total=self.scan_timeout, ncols=80)
                else:
                    triggers = self.dut['TLU']['TRIGGER_COUNTER']
                    try:
                        if self.max_triggers:
                            self.pbar.update(triggers - self.pbar.n)
                        else:
                            self.pbar.update(time() - start - self.pbar.n)
                    except ValueError:
                        pass
                    if self.max_triggers and triggers >= self.max_triggers:
                        self.stop_scan = True
                        self.pbar.close()
                        logging.info('Trigger limit was reached: %i' % self.max_triggers)

        logging.info('Total amount of triggers collected: %d', self.dut['TLU']['TRIGGER_COUNTER'])

    def analyze(self):
        pass

    def start(self):
        '''Start Mimosa26 telescope scan.
        '''
        self.stop_scan = False
        signal.signal(signal.SIGINT, self._signal_handler)
        logging.info('Press Ctrl-C to stop run')

        # check for filename that is not in use
        while True:
            if not self.output_filename and self.run_number:
                filename = 'run_' + str(self.run_number) + '_' + self.run_id

            else:
                if self.output_filename:
                    filename = self.output_filename
                else:
                    filename = strftime("%Y%m%d-%H%M%S") + '_' + self.run_id
            if filename in [os.path.splitext(f)[0] for f in os.listdir(self.working_dir) if os.path.isfile(os.path.join(self.working_dir, f))]:
                if not self.output_filename and self.run_number:
                    self.run_number += 1  # increase run number and try again
                    continue
                else:
                    raise IOError("Filename %s already exists." % filename)
            else:
                self.run_filename = os.path.join(self.working_dir, filename)
                break

        # set up logger
        self.fh = logging.FileHandler(self.run_filename + '.log')
        self.fh.setLevel(logging.DEBUG)
        self.fh.setFormatter(logging.Formatter(FORMAT))
        self.logger = logging.getLogger()
        self.logger.addHandler(self.fh)

        with self.access_file():
            save_configuration_dict(self.raw_data_file.h5_file, 'configuration', self.telescope_conf)
            self.scan()

        self.logger.removeHandler(self.fh)

        logging.info('Data Output Filename: %s', self.run_filename + '.h5')
        self.analyze()

    @contextmanager
    def readout(self, *args, **kwargs):
        try:
            self.start_readout(*args, **kwargs)
            yield
        finally:
            try:
                self.stop_readout(timeout=10.0)
            except Exception:
                # in case something fails, call this on last resort
                if self.m26_readout.is_running:
                    self.m26_readout.stop(timeout=0.0)

    def start_readout(self, *args, **kwargs):
        '''Start readout of Mimosa26 sensors.
        '''
        enabled_m26_channels = kwargs.get('enabled_m26_channels', None)  # None will enable all existing Mimosa26 channels
        self.m26_readout.start(
            fifos="SITCP_FIFO",
            callback=self.handle_data,
            errback=self.handle_err,
            reset_rx=True,
            reset_fifo=True,
            no_data_timeout=self.no_data_timeout,
            enabled_m26_channels=enabled_m26_channels)

        self.dut['TLU']['MAX_TRIGGERS'] = self.max_triggers
        self.dut['TLU']['TRIGGER_ENABLE'] = True
        self.m26_readout.print_readout_status()

        def timeout():
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
        self.raw_data_file = open_raw_data_file(filename=self.run_filename,
                                                mode='w',
                                                title=os.path.basename(self.run_filename),
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
        for data_tuple in data:
            if data_tuple is None:
                continue
            self.raw_data_file.append(data_iterable=data_tuple, new_file=new_file, flush=flush)

    def handle_err(self, exc):
        '''Handling of error messages during readout.
        '''
        msg = '%s' % exc[1]
        if msg:
            logging.error('%s%s Aborting run...', msg, msg[-1])
        else:
            logging.error('Aborting run...')
        self.stop_scan = True

    def _signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler... pressing Ctrl-C a second time will kill application
        logging.info('Pressed Ctrl-C')
        self.stop_scan = True


def main():
    ''' Main entry point to start a scan '''
    try:
        import pymosa
        from pymosa import __version__ as pymosa_version
    except ImportError:
        try:
            with open(os.path.join(os.path.split(os.path.split(os.path.abspath(__file__))[0])[0], 'VERSION')) as version_file:
                pymosa_version = version_file.read().strip()
        except IOError:
            raise
            pymosa_version = "(local)"

    import argparse
    parser = argparse.ArgumentParser(description='Pymosa %s\nExample: python m26.py --no-m26-jtag-configuration --filename <output filename>' % pymosa_version, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-f', '--filename', type=str, metavar='<output filename>', action='store', help='filename of the telescope data file')
    parser.add_argument('-r', '--run_number', type=int, metavar='<run number>', action='store', help='base run number (will be automatically increased)')
    parser.add_argument('--scan_timeout', type=int, metavar='<scan timeout>', action='store', help="scan timeout in seconds, default: 0 (disabled)")
    parser.add_argument('--max_triggers', type=int, metavar='<number of triggers>', action='store', help="maximum number of triggers, default: 0 (disabled)")
    parser.add_argument('--no_m26_jtag_configuration', dest='no_m26_jtag_configuration', action='store_true', help='disable Mimosa26 configuration via JTAG')
    parser.set_defaults(no_m26_jtag_configuration=False)
    args = parser.parse_args()

    # Open Mimosa26 std. configuration
    pymosa_path = os.path.dirname(pymosa.__file__)
    with open(os.path.join(pymosa_path, 'm26_configuration.yaml'), 'r') as f:
        config = yaml.safe_load(f)

    # Set config from arguments
    if args.filename is not None:
        config["filename"] = args.filename
    if args.run_number is not None:
        config["run_number"] = args.run_number
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
    # Close the resources
    telescope.close()


if __name__ == '__main__':
    main()
