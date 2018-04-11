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


class m26(Dut):
    ''' Mimosa26 telescope readout with MMC3 hardware.

    Note:
    - Remove not used Mimosa26 planes by commenting out the drivers in the DUT file (i.e. m26.yaml).
    - Set up trigger in DUT configuration file (i.e. m26_configuration.yaml).
    '''
    VERSION = 2  # required version for mmc3_m26_eth.v

    def __init__(self, conf=None, context=None, socket_address=None):
        if conf is None:
            conf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m26.yaml")
        logger.info("Loading DUT configuration from file %s" % conf)

        # initialize class
        super(m26, self).__init__(conf)

    def init(self, **kwargs):
        # initialize hardware
        super(m26, self).init()

        # check firmware version
        fw_version = self['ETH'].read(0x0000, 1)[0]
        logging.info("MMC3 firmware version: %s" % (fw_version))
        if fw_version != self.VERSION:
            raise Exception("MMC3 firmware version does not satisfy version requirements (read: %s, require: %s)" % (fw_version, self.VERSION))

        logging.info('Initializing %s', self.__class__.__name__)

        self.working_dir = os.path.join(os.getcwd(), kwargs.pop("output_folder", "output_data"))
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        logger.info("Store output data in %s" % self.working_dir)

        self.scan_id = 'M26_TELESCOPE'

        self.output_filename = kwargs.pop('filename', None)
        if self.output_filename is None:
            self.run_name = strftime("%Y%m%d_%H%M%S_") + self.scan_id
            self.output_filename = os.path.join(self.working_dir, self.run_name)
        else:
            self.run_name = os.path.basename(os.path.realpath(self.output_filename))

        # configure Mimosa26 sensors
        self.configure(**kwargs)

        # FIFO readout
        self.fifo_readout = M26Readout(self)

    def configure(self, **kwargs):
        '''Configure Mimosa26 sensors via JTAG and configure triggers (TLU).
        '''
        def write_jtag(irs, IR):
            for i, ir in enumerate(irs):
                logger.info('Programming M26 JTAG configuration reg %s', ir)
                logger.debug(self[ir][:])
                self['JTAG'].scan_ir([BitLogic(IR[ir])] * 6)
                self['JTAG'].scan_dr([self[ir][:]])[0]

        def check_jtag(irs, IR):
            # read first registers
            ret = {}
            for i, ir in enumerate(irs):
                logger.info('Reading M26 JTAG configuration reg %s', ir)
                self['JTAG'].scan_ir([BitLogic(IR[ir])] * 6)
                ret[ir] = self['JTAG'].scan_dr([self[ir][:]])[0]
            # check registers
            for k, v in ret.iteritems():
                if k == "CTRL_8b10b_REG1_ALL":
                    pass
                elif k == "BSR_ALL":
                    pass  # TODO mask clock bits and check others
                elif self[k][:] != v:
                    logger.error(
                        "JTAG data does not match %s get=%s set=%s" % (k, v, self[k][:]))
                else:
                    logger.info("Checking M26 JTAG %s ok" % k)

        # set the clock distributer inputs in correct states.
        self.set_clock_distributer()

        m26_config_file = kwargs['m26_configuration_file']
        logger.info('Loading M26 configuration file %s', m26_config_file)

        # set M26 configuration file
        self.set_configuration(m26_config_file)

        m26_config = kwargs.pop('m26_runconfig', "ON")
        if m26_config == "ON":
            # reset JTAG; this is important otherwise JTAG programming works not properly.
            self['JTAG'].reset()

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
            temp = self['RO_MODE0_ALL'][:]
            # disable extstart
            for reg in self["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['En_ExtStart'] = 0
                reg['JTAG_Start'] = 0
            self['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self['JTAG'].scan_dr([self['RO_MODE0_ALL'][:]])
            # JTAG start
            for reg in self["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['JTAG_Start'] = 1
            self['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self['JTAG'].scan_dr([self['RO_MODE0_ALL'][:]])
            for reg in self["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['JTAG_Start'] = 0
            self['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self['JTAG'].scan_dr([self['RO_MODE0_ALL'][:]])
            # write original configuration
            self['RO_MODE0_ALL'][:] = temp
            self['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self['JTAG'].scan_dr([self['RO_MODE0_ALL'][:]])
            # readback?
            self['JTAG'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
            self['JTAG'].scan_dr([self['RO_MODE0_ALL'][:]] * 6)
        else:
            logger.info("Skipping M26 JTAG configuration")
        # setup trigger configuration
        self['TLU']['RESET'] = 1
        self['TLU']['TRIGGER_MODE'] = kwargs["TLU"]['TRIGGER_MODE']
        self['TLU']['TRIGGER_LOW_TIMEOUT'] = kwargs["TLU"]['TRIGGER_LOW_TIMEOUT']
        self['TLU']['TRIGGER_SELECT'] = kwargs["TLU"]['TRIGGER_SELECT']
        self['TLU']['TRIGGER_INVERT'] = kwargs["TLU"]['TRIGGER_INVERT']
        self['TLU']['TRIGGER_VETO_SELECT'] = kwargs["TLU"]['TRIGGER_VETO_SELECT']
        self['TLU']['TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES'] = kwargs["TLU"]['TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES']
        self['TLU']['DATA_FORMAT'] = kwargs["TLU"]['DATA_FORMAT']
        self['TLU']['EN_TLU_VETO'] = kwargs["TLU"]['EN_TLU_VETO']
        self['TLU']['TRIGGER_DATA_DELAY'] = kwargs["TLU"]['TRIGGER_DATA_DELAY']
        self['TLU']['TRIGGER_COUNTER'] = kwargs["TLU"]['TRIGGER_COUNTER']
        # self['TLU']['TRIGGER_THRESHOLD'] = kwargs['TLU']['TRIGGER_THRESHOLD']

    def set_clock_distributer(self, clk=0, start=1, reset=0, speak=1):
        # Default values -same as in GUI- (self, clk=0, start=1, reset=0, speak=1)
        self["START_RESET"]["CLK"] = clk
        self["START_RESET"]["START"] = start
        self["START_RESET"]["RESET"] = reset
        self["START_RESET"]["SPEAK"] = speak
        self["START_RESET"].write()

    def reset(self, reset_time=2):
        self["START_RESET"]["RESET"] = 1
        self["START_RESET"].write()
        sleep(reset_time)
        self["START_RESET"]["RESET"] = 0
        self["START_RESET"].write()

    def scan(self, **kwargs):
        '''Scan Mimosa26 telescope loop.
        '''
        with self.readout(**kwargs):
            got_data = False
            self.stop_scan = False
            start = time()
            while not self.stop_scan:
                try:
                    sleep(1.0)
                    self.fifo_readout.print_readout_status()
                    if not got_data:
                        if self.fifo_readout.data_words_per_second() > 0:
                            got_data = True
                            logging.info('Taking data...')
                            if kwargs['max_triggers']:
                                self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=kwargs['max_triggers'], poll=10, term_width=80).start()
                            else:
                                self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.Timer()], maxval=kwargs['scan_timeout'], poll=10, term_width=80).start()
                    else:
                        triggers = self['TLU']['TRIGGER_COUNTER']
                        try:
                            if kwargs['max_triggers']:
                                self.progressbar.update(triggers)
                            else:
                                self.progressbar.update(time() - start)
                        except ValueError:
                            pass
                        if kwargs['max_triggers'] and triggers >= kwargs['max_triggers']:
                            self.stop_scan = True
                            self.progressbar.finish()
                            logging.info('Trigger limit was reached: %i' % kwargs['max_triggers'])
                except KeyboardInterrupt:  # react on keyboard interupt
                    logging.info('Scan was stopped due to keyboard interrupt')
                    self.stop_scan = True

        logging.info('Total amount of triggers collected: %d', self['TLU']['TRIGGER_COUNTER'])

    def start(self, **kwargs):
        '''Start Mimosa26 telescope scan.
        '''
        self.fh = logging.FileHandler(self.output_filename + '.log')
        self.fh.setLevel(logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.addHandler(self.fh)

        with self.access_file():
            save_configuration_dict(self.raw_data_file.h5_file, 'configuration', kwargs)
            self.scan(**kwargs)

        self.logger.removeHandler(self.fh)

        logging.info('Data Output Filename: %s', self.output_filename + '.h5')

    @contextmanager
    def readout(self, *args, **kwargs):
        timeout = kwargs.pop('timeout', 10.0)
        self.start_readout(*args, **kwargs)
        try:
            yield
        finally:
            try:
                self.stop_readout(timeout=timeout)
            except Exception:
                # in case something fails, call this on last resort
                if self.fifo_readout.is_running:
                    self.fifo_readout.stop(timeout=0.0)

    def start_readout(self, **kwargs):
        '''Start readout of Mimosa26 sensors.
        '''
        self.fifo_readout.start(
            fifos="SITCP_FIFO",
            callback=self.handle_data,
            errback=self.handle_err,
            reset_rx=True,
            reset_fifo=True,
            no_data_timeout=kwargs['no_data_timeout'],
            enabled_m26_channels=[rx.name for rx in self.get_modules('m26_rx')])

        if kwargs['max_triggers']:
            self['TLU']['MAX_TRIGGERS'] = kwargs['max_triggers']
        else:
            self['TLU']['MAX_TRIGGERS'] = 0  # infinity triggers
        self['TLU']['TRIGGER_ENABLE'] = True

        def timeout():
            try:
                self.progressbar.finish()
            except AttributeError:
                pass
            self.stop_scan = True
            logging.info('Scan timeout was reached')

        self.scan_timeout_timer = Timer(kwargs['scan_timeout'], timeout)
        if kwargs['scan_timeout']:
            self.scan_timeout_timer.start()

    def stop_readout(self, timeout=10.0):
        '''Stop readout of Mimosa26 sensors.
        '''
        self.scan_timeout_timer.cancel()
        self['TLU']['TRIGGER_ENABLE'] = False
        self.fifo_readout.stop(timeout=timeout)

    @contextmanager
    def access_file(self):
        try:
            self.open_file()
            yield
            self.close_file()
        finally:
            # in case something fails, call this on last resort
            self.raw_data_file = None

    def open_file(self):
        self.raw_data_file = open_raw_data_file(filename=self.output_filename,
                                                mode='w',
                                                title=self.run_name,
                                                socket_address=config['send_data'])
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
    import argparse
    parser = argparse.ArgumentParser(description='Pymosa \n Example: python /<path to pymosa>/m26.py --m26_runconfig --scan_timeout 300 --filename /<path to output file>/<output file name>', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--scan_timeout', type=int, default=0, help="Scan time in seconds. Default=disabled, disable=0")
    parser.add_argument('-f', '--filename', type=str, default=None, help='Name of data file')
    parser.add_argument('--m26_runconfig', type=str, default="ON", help='configure MIMOSA or skip default= ON, ON: configure, OFF: skip')
    args = parser.parse_args()

    with open('./m26_configuration.yaml', 'r') as f:
        config = yaml.load(f)

    config["scan_timeout"] = args.scan_timeout
    config["filename"] = args.filename
    config["m26_runconfig"] = args.m26_runconfig

    dut = m26(socket_address=config['send_data'])
    # initialize telescope
    dut.init(**config)
    # start telescope readout using run config
    dut.start(**config)
