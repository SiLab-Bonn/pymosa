#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from contextlib import contextmanager
from threading import Timer

import logging
import os
import time
import progressbar
import yaml
import zmq
import tables as tb
import numpy as np

from basil.dut import Dut
from basil.utils.BitLogic import BitLogic
from fifo_readout import FifoReadout

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def send_meta_data(socket, conf, name):
    '''Sends the config via ZeroMQ to a specified socket. Is called at the beginning of a run and when the config changes. Conf can be any config dictionary.
    '''
    meta_data = dict(
        name=name,
        conf=conf
    )
    try:
        socket.send_json(meta_data, flags=zmq.NOBLOCK)
    except zmq.Again:
        pass


def send_data(socket, data, scan_parameters={}, name='ReadoutData'):
    '''Sends the data of every read out (raw data and meta data) via ZeroMQ to a specified socket
    '''
    if not scan_parameters:
        scan_parameters = {}
    data_meta_data = dict(
        name=name,
        dtype=str(data[0].dtype),
        shape=data[0].shape,
        timestamp_start=data[1],  # float
        timestamp_stop=data[2],  # float
        readout_error=data[3],  # int
        scan_parameters=scan_parameters  # dict
    )
    try:
        socket.send_json(data_meta_data, flags=zmq.SNDMORE | zmq.NOBLOCK)
        socket.send(data[0], flags=zmq.NOBLOCK)  # PyZMQ supports sending numpy arrays without copying any data
    except zmq.Again:
        pass


class m26(Dut):
    ''' Mimosa26 telescope readout with MMC3 hardware.

    Note:
    - Remove not used Mimosa26 planes by commenting out the drivers in the DUT file (i.e. m26.yaml).
    - Setup run and trigger in configuration file (e.g. configuration.yaml)
    '''

    VERSION = 1  # required version for mmc3_m26_eth.v

    def __init__(self, conf=None, context=None, socket_address=None):
        self.meta_data_dtype = np.dtype([('index_start', 'u4'), ('index_stop', 'u4'), ('data_length', 'u4'),
                                         ('timestamp_start', 'f8'), ('timestamp_stop', 'f8'), ('error', 'u4')])

        if conf is None:
            conf = os.path.dirname(os.path.abspath(__file__)) + os.sep + "m26.yaml"

        if socket_address and not context:
            logging.info('Creating ZMQ context')
            context = zmq.Context()

        if socket_address and context:
            logging.info('Creating socket connection to server %s', socket_address)
            self.socket = context.socket(zmq.PUB)  # publisher socket
            self.socket.bind(socket_address)
            send_meta_data(self.socket, None, name='Reset')  # send reset to indicate a new scan
        else:
            self.socket = None

        logger.info("Loading DUT configuration from file %s" % conf)

        super(m26, self).__init__(conf)

    def init(self, **kwargs):
        super(m26, self).init()

        # check firmware version
        fw_version = self['ETH'].read(0x0000, 1)[0]
        logging.info("MMC3 firmware version: %s" % (fw_version))
        if fw_version != self.VERSION:
            raise Exception("MMC3 firmware version does not satisfy version requirements (read: %s, require: %s)" % (fw_version, self.VERSION))

        logging.info('Initializing %s', self.__class__.__name__)

        if 'output_folder' in kwargs:
            self.working_dir = os.path.join(os.getcwd(), kwargs['output_folder'])
        else:
            self.working_dir = os.path.join(os.getcwd(), "output_data")
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        logger.info("Store output data in %s" % self.working_dir)

        self.scan_id = 'M26_TELESCOPE'

        self.run_name = time.strftime("%Y%m%d_%H%M%S_") + self.scan_id
        self.output_filename = os.path.join(self.working_dir, self.run_name)

        self.fh = logging.FileHandler(self.output_filename + '.log')
        self.fh.setLevel(logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.addHandler(self.fh)

        # configure Mimosa26 sensors
        self.configure(kwargs)

    def configure(self, kwargs):
        '''Configure Mimosa26 sensors via JTAG and configure triggers (TLU).
        '''

        # reset M26 RX
        map(lambda channel: channel.reset(), self.get_modules('m26_rx'))

        # reset JTAG; this is important otherwise JTAG programming works not properly.
        self['jtag'].reset()

        m26_config_file = kwargs['m26_configuration_file']
        logger.info('Loading M26 configuration file %s', m26_config_file)

        # set M26 configuration file
        self.set_configuration(m26_config_file)

        IR = {"BSR_ALL": '00101', "DEV_ID_ALL": '01110', "BIAS_DAC_ALL": '01111', "LINEPAT0_REG_ALL": '10000',
              "DIS_DISCRI_ALL": '10001', "SEQUENCER_PIX_REG_ALL": '10010', "CONTROL_PIX_REG_ALL": '10011',
              "LINEPAT1_REG_ALL": '10100', "SEQUENCER_SUZE_REG_ALL": '10101', "HEADER_REG_ALL": '10110',
              "CONTROL_SUZE_REG_ALL": '10111', "CTRL_8b10b_REG0_ALL": '11000', "CTRL_8b10b_REG1_ALL": '11001',
              "RO_MODE1_ALL": '11101', "RO_MODE0_ALL": '11110', "BYPASS_ALL": '11111'}

        # write JTAG
        irs = ["BIAS_DAC_ALL", "BYPASS_ALL", "BSR_ALL", "RO_MODE0_ALL", "RO_MODE1_ALL", "DIS_DISCRI_ALL",
               "LINEPAT0_REG_ALL", "LINEPAT1_REG_ALL", "CONTROL_PIX_REG_ALL", "SEQUENCER_PIX_REG_ALL",
               "HEADER_REG_ALL", "CONTROL_SUZE_REG_ALL", "SEQUENCER_SUZE_REG_ALL", "CTRL_8b10b_REG0_ALL",
               "CTRL_8b10b_REG1_ALL"]
        for i, ir in enumerate(irs):
            logger.info('Programming M26 JTAG configuration reg %s', ir)
            logger.debug(self[ir][:])
            self['jtag'].scan_ir([BitLogic(IR[ir])] * 6)
            self['jtag'].scan_dr([self[ir][:]])[0]

        # read JTAG in order to check configuration
        irs = ["DEV_ID_ALL", "BSR_ALL", "BIAS_DAC_ALL", "RO_MODE1_ALL", "RO_MODE0_ALL", "DIS_DISCRI_ALL",
               "LINEPAT0_REG_ALL", "LINEPAT1_REG_ALL", "CONTROL_PIX_REG_ALL", "SEQUENCER_PIX_REG_ALL",
               "HEADER_REG_ALL", "CONTROL_SUZE_REG_ALL", "SEQUENCER_SUZE_REG_ALL", "CTRL_8b10b_REG0_ALL",
               "CTRL_8b10b_REG1_ALL", "BYPASS_ALL"]
        ret = {}
        for i, ir in enumerate(irs):
            logger.info('Reading M26 JTAG configuration reg %s', ir)
            self['jtag'].scan_ir([BitLogic(IR[ir])] * 6)
            ret[ir] = self['jtag'].scan_dr([self[ir][:]])[0]

        # check if registers are properly programmed by reading them and comparing to settings.
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

        # START procedure
        logger.info('Starting M26')
        temp = self['RO_MODE0_ALL'][:]
        # disable extstart
        for reg in self["RO_MODE0_ALL"]["RO_MODE0"]:
            reg['En_ExtStart'] = 0
            reg['JTAG_Start'] = 0
        self['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
        self['jtag'].scan_dr([self['RO_MODE0_ALL'][:]])
        # JTAG start
        for reg in self["RO_MODE0_ALL"]["RO_MODE0"]:
            reg['JTAG_Start'] = 1
        self['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
        self['jtag'].scan_dr([self['RO_MODE0_ALL'][:]])
        for reg in self["RO_MODE0_ALL"]["RO_MODE0"]:
            reg['JTAG_Start'] = 0
        self['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
        self['jtag'].scan_dr([self['RO_MODE0_ALL'][:]])
        # write original configuration
        self['RO_MODE0_ALL'][:] = temp
        self['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
        self['jtag'].scan_dr([self['RO_MODE0_ALL'][:]])
        # readback?
        self['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])] * 6)
        self['jtag'].scan_dr([self['RO_MODE0_ALL'][:]] * 6)

        # setup trigger configuration
        self['TLU']['RESET'] = 1
        self['TLU']['TRIGGER_MODE'] = kwargs['TLU']['TRIGGER_MODE']
        self['TLU']['TRIGGER_LOW_TIMEOUT'] = kwargs['TLU']['TRIGGER_LOW_TIMEOUT']
        self['TLU']['TRIGGER_SELECT'] = kwargs['TLU']['TRIGGER_SELECT']
        self['TLU']['TRIGGER_INVERT'] = kwargs['TLU']['TRIGGER_INVERT']
        self['TLU']['TRIGGER_VETO_SELECT'] = kwargs['TLU']['TRIGGER_VETO_SELECT']
        self['TLU']['TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES'] = kwargs['TLU']['TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES']
        self['TLU']['DATA_FORMAT'] = kwargs['TLU']['DATA_FORMAT']
        self['TLU']['EN_TLU_VETO'] = kwargs['TLU']['EN_TLU_VETO']
        self['TLU']['TRIGGER_DATA_DELAY'] = kwargs['TLU']['TRIGGER_DATA_DELAY']
        self['TLU']['TRIGGER_COUNTER'] = kwargs['TLU']['TRIGGER_COUNTER']
        # self['TLU']['TRIGGER_THRESHOLD'] = kwargs['TLU']['TRIGGER_THRESHOLD']
        # self['TLU']['TRIGGER_COUNTER'] = 0 TODO: what is this,needed?

        for plane in range(1, 7):
            self['M26_RX%d' % plane].reset()
            self['M26_RX%d' % plane]['TIMESTAMP_HEADER'] = 1

    def scan(self, **kwargs):
        '''Scan Mimosa26 telescope loop.
        '''
        with self.readout(**kwargs):
            got_data = False
            self.stop_scan = False
            while not self.stop_scan:
                try:
                    time.sleep(1.0)
                    self.fifo_readout.print_readout_status()
                    if not got_data:
                        if self.fifo_readout.data_words_per_second() > 0:
                            got_data = True
                            logging.info('Taking data...')
                            self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=kwargs['max_triggers'], poll=10, term_width=80).start()
                    else:
                        triggers = self['TLU']['TRIGGER_COUNTER']
                        try:
                            self.progressbar.update(triggers)
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
        filename = self.output_filename + '.h5'
        self.filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        self.filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        self.h5_file = tb.open_file(filename, mode='w', title=self.scan_id)
        self.raw_data_earray = self.h5_file.create_earray(self.h5_file.root, name='raw_data', atom=tb.UIntAtom(),
                                                          shape=(0,), title='raw_data', filters=self.filter_raw_data)
        self.meta_data_table = self.h5_file.create_table(self.h5_file.root, name='meta_data', description=self.meta_data_dtype,
                                                         title='meta_data', filters=self.filter_tables)

        self.meta_data_table.attrs.kwargs = yaml.dump(kwargs)

        self.fifo_readout = FifoReadout(self)

        self.scan(**kwargs)

        self.h5_file.close()
        logging.info('Data Output Filename: %s', self.output_filename + '.h5')

        self.logger.removeHandler(self.fh)

    def start_readout(self, **kwargs):
        '''Start readout of Mimosa26 sensors.
        '''
        self.fifo_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data,
                                errback=self.handle_err, no_data_timeout=kwargs['no_data_timeout'])

        # enable all M26 planes
        for plane in range(1, 7):
            self['M26_RX%d' % plane].set_en(True)

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
        self['M26_RX1'].set_en(False)
        self['M26_RX2'].set_en(False)
        self['M26_RX3'].set_en(False)
        self['M26_RX4'].set_en(False)
        self['M26_RX5'].set_en(False)
        self['M26_RX6'].set_en(False)
        self.fifo_readout.stop(timeout=timeout)

    @contextmanager
    def readout(self, *args, **kwargs):
        timeout = kwargs.pop('timeout', 10.0)
        self.start_readout(*args, **kwargs)
        try:
            yield
            self.stop_readout(timeout=timeout)
        finally:
            # in case something fails, call this on last resort
            if self.fifo_readout.is_running:
                self.fifo_readout.stop(timeout=0.0)

    def handle_data(self, data_tuple):
        '''Handling of raw data and meta data during readout.
        '''
        def get_bin(x, n):
            return format(x, 'b').zfill(n)

        total_words = self.raw_data_earray.nrows

        self.raw_data_earray.append(data_tuple[0])
        self.raw_data_earray.flush()

        len_raw_data = data_tuple[0].shape[0]
        self.meta_data_table.row['timestamp_start'] = data_tuple[1]
        self.meta_data_table.row['timestamp_stop'] = data_tuple[2]
        self.meta_data_table.row['error'] = data_tuple[3]
        self.meta_data_table.row['data_length'] = len_raw_data
        self.meta_data_table.row['index_start'] = total_words
        total_words += len_raw_data
        self.meta_data_table.row['index_stop'] = total_words
        counter = 0
        for _ in data_tuple[0]:
            counter = counter + int(get_bin(int(data_tuple[0][0]), 32)[1])
        self.meta_data_table.row.append()
        self.meta_data_table.flush()
        if self.socket:
                send_data(self.socket, data_tuple)

    def handle_err(self, exc):
        '''Handling of error messages during readout.
        '''
        msg = '%s' % exc[1]
        if msg:
            logging.error('%s%s Aborting run...', msg, msg[-1])
        else:
            logging.error('Aborting run...')


if __name__ == '__main__':
    with open('./configuration.yaml', 'r') as f:
        config = yaml.load(f)

    dut = m26(socket_address=config['send_data'])
    # initialize telescope
    dut.init(**config)
    # start telescope readout using run config
    dut.start(**config)
