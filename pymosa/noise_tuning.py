import logging
import os
from time import sleep

import yaml
import numpy as np
from tqdm import tqdm
from matplotlib.backends.backend_pdf import PdfPages

from basil.utils.BitLogic import BitLogic

from pymosa.m26 import m26
from pymosa import online as oa
from pymosa.m26_raw_data import open_raw_data_file, send_meta_data
from pymosa import plotting as plotting


class NoiseOccTuning(m26):
    '''Noise Occupancy Tuning

    This script finds the lowest possible threshold setting for a specified fake hit rate (per pixel, per readout frame [115.2 us])
    by setting for each Mimosa26 plane the corresponding threshold of the four regions A, B, C, D.
    '''

    def store_configuration(self, config_file=None):
        if config_file is None:
            config_file = './m26_config/m26_noise_tuning.yaml'
        logging.info('Dumping configuration to {0:s}'.format(config_file))
        with open(config_file, mode='w') as f:
            yaml.dump(self.dut.get_configuration(), f)

    def print_log_status(self):
        m26_rx_names = [rx.name for rx in self.dut.get_modules('m26_rx')]
        logging.info('Mimosa26 RX channel:     %s', " | ".join([name.rjust(3) for name in m26_rx_names]))
        for i, region in enumerate(['A', 'B', 'C', 'D']):
            logging.info('Threshold setting %s:     %s', region, " | ".join([repr(count).rjust(max(3, len(m26_rx_names[index]))) for index, count in enumerate(self.thr[:len(m26_rx_names), i])]))
        for i, region in enumerate(['A', 'B', 'C', 'D']):
            logging.info('Fake hit rate %s:         %s', region, " | ".join([format(count, '.1e').rjust(max(3, len(m26_rx_names[index]))) for index, count in enumerate(self.fake_hit_rate_meas[:len(m26_rx_names), i])]))
        logging.info('Noise occupancy:         %s', " | ".join([repr(count).rjust(max(3, len(m26_rx_names[index]))) for index, count in enumerate(self.hit_occ_map[:, :, :len(m26_rx_names)].sum(axis=(0, 1)))]))

    def set_threshold(self, thr_a=None, thr_b=None, thr_c=None, thr_d=None, thr_global=None):
        '''
        Sets and writes thresholds to Mimosa26. It can be written a global threshold (IVDREF2) or
        a local threshold (IVDREF1A - D) for four regions (A, B, C, D) of the chip.

        Note:
        - Threshold configuration belongs to BIAS_DAC_ALL register (6 x 152 bits for 6 planes, MSB: plane 6, LSB: plane 1)
        - Local threshold: IVDREF1A - D stored in bits 104-112, 96-104, 88-96, 80-88 of 152 bit word
        - Global threshold: IVDREF2 stored in bits 112-120 of 152 bit word
        '''
        self.dut['JTAG'].reset()
        # Convert binary string to array in order to modify it
        bias_dac_all = np.array(list(map(int, self.dut['BIAS_DAC_ALL'][:])))
        # Set local thresholds A - D. MSB: plane 6, LSB: plane 1
        if thr_a is not None:
            for i, thr in enumerate(thr_a):
                bias_dac_all[(5 - i) * 152 + 104:(5 - i) * 152 + 112] = np.array(list(map(int, format(thr, '008b')[::-1])))
        if thr_b is not None:
            for i, thr in enumerate(thr_b):
                bias_dac_all[(5 - i) * 152 + 96:(5 - i) * 152 + 104] = np.array(list(map(int, format(thr, '008b')[::-1])))
        if thr_c is not None:
            for i, thr in enumerate(thr_c):
                bias_dac_all[(5 - i) * 152 + 88:(5 - i) * 152 + 96] = np.array(list(map(int, format(thr, '008b')[::-1])))
        if thr_d is not None:
            for i, thr in enumerate(thr_d):
                bias_dac_all[(5 - i) * 152 + 80:(5 - i) * 152 + 88] = np.array(list(map(int, format(thr, '008b')[::-1])))
        # Set global threshold
        if thr_global is not None:
            for i, thr in enumerate(thr_global):
                bias_dac_all[(5 - i) * 152 + 112:(5 - i) * 152 + 120] = np.array(list(map(int, format(thr, '008b')[::-1])))

        # Set configuration
        self.dut['BIAS_DAC_ALL'][:] = ''.join(map(str, bias_dac_all[::-1]))
        # Write register
        self.dut['JTAG'].scan_ir([BitLogic('01111')] * 6)
        self.dut['JTAG'].scan_dr([self.dut['BIAS_DAC_ALL'][:]])[0]

    def deactivate_column(self, disable_columns):
        '''
        Deactivate specific columns of Mimosa26.
        MSB: plane 6, LSB: plane 1
        '''
        self.dut['JTAG'].reset()
        # Convert binary string to array in order to modify it
        dis_discri_all_old = np.array(map(int, self.dut['DIS_DISCRI_ALL'][:]))
        dis_discri_all = np.logical_or(dis_discri_all_old, disable_columns).astype(int)
        # Set configuration
        self.dut['DIS_DISCRI_ALL'][:] = ''.join(map(str, dis_discri_all[::-1]))
        # Write register
        self.dut['JTAG'].scan_ir([BitLogic('10001')] * 6)
        self.dut['JTAG'].scan_dr([self.dut['DIS_DISCRI_ALL'][:]])[0]

    def take_data(self, update_rate=1):
        with self.readout():
            logging.info('Taking data...')
            self.pbar = tqdm(total=self.scan_timeout, ncols=80)
            for _ in range(int(self.scan_timeout / update_rate)):
                sleep(update_rate)
                try:
                    self.pbar.update(update_rate)
                except ValueError:
                        pass

            self.pbar.close()

        # Get hit occupancy for every plane using fast online analysis
        hit_occ_map = self.hist_occ.get()

        return hit_occ_map

    def init(self, init_conf=None, configure_m26=True):
        # set name of scan
        init_conf["run_id"] = 'noise_occupancy_tuning'

        super(NoiseOccTuning, self).init(init_conf=init_conf, configure_m26=configure_m26)
        self.hist_occ = oa.OccupancyHistogramming()

        self.scan_timeout = self.telescope_conf.get('scan_timeout', 5)  # time for which noise occupancy is measured in seconds
        self.fake_hit_rate = self.telescope_conf.get('fake_hit_rate', 1e-6)  # average fake hits per pixel per 115.2 us
        self.thr_start = self.telescope_conf.get('thr_start', 255)  # start value from which threshold is lowered, same value for all regions A, B, C, D
        self.thr_step = self.telescope_conf.get('thr_step', 2)  # step size for lowering threshold, same value for all regions A, B, C, D

    def open_file(self):
        self.raw_data_file = open_raw_data_file(filename=self.run_filename,
                                                mode='w',
                                                title=os.path.basename(self.run_filename),
                                                socket_address=self.send_data)
        if self.raw_data_file.socket:
            # send reset to indicate a new scan for the online monitor
            send_meta_data(self.raw_data_file.socket, None, name='Reset')

    def handle_data(self, data, new_file=False, flush=True):
        '''Handling of raw data and meta data during readout.
        '''
        for data_tuple in data:
            if data_tuple is None:
                continue
            self.raw_data_file.append(data_iterable=data_tuple, scan_parameters=None, new_file=new_file, flush=flush)
            # Add every raw data chunk to online analysis
            for data in data_tuple:
                self.hist_occ.add(raw_data=data[0])

    def scan(self):
        logging.info('Allowed fake hit rate (per pixel / 115.2 us): {0:.1e}'.format(self.fake_hit_rate))
        logging.info('Starting from threshold setting {0} in steps of {1}'.format(self.thr_start, self.thr_step))

        # Define columns which belong to regions A, B, C, D
        m26_regions = [(0, 288), (288, 576), (576, 864), (864, 1151)]

        # Find lowest threshold setting until max fake hit rate is reached.
        proceed = np.ones(shape=(6, 4), dtype=np.bool)  # Indicator if fake hit rate is reached (6 planes, 4 regions)
        self.fake_hit_rate_meas = np.full(shape=proceed.shape, fill_value=np.nan)
        thr_start = np.full(shape=proceed.shape, fill_value=self.thr_start)
        self.thr = thr_start
        init = True

        while np.any(proceed):
            # Set threshold for all planes
            self.set_threshold(thr_a=self.thr[:, 0], thr_b=self.thr[:, 1], thr_c=self.thr[:, 2], thr_d=self.thr[:, 3])
            # Take data and get hit occupancy
            self.hit_occ_map = self.take_data()

            # Calculate fake hit rate
            for region in range(4):
                occs = self.hit_occ_map[slice(m26_regions[region][0], m26_regions[region][1]), :, :].sum(axis=(0, 1))
                self.fake_hit_rate_meas[np.nonzero(occs), region] = occs[np.nonzero(occs)] / 576. / 288. / self.scan_timeout / 1e6 * 115.2

            # Log status (fake hit rate, noise occupoancy, threshold setting)
            self.print_log_status()
            # Check if threshold needs to be lowered or increased
            for plane in range(6):
                for region in range(4):
                    if proceed[plane, region]:
                        if (self.fake_hit_rate_meas[plane, region] < self.fake_hit_rate) or np.isnan(self.fake_hit_rate_meas[plane, region]):
                            self.thr[plane, region] -= self.thr_step
                        else:
                            if self.thr[plane, region] + self.thr_step <= 255:
                                self.thr[plane, region] += self.thr_step
                            else:
                                self.thr[plane, region] = 255
                            proceed[plane, region] = False

            # Append measured fake hit rate for later result plot
            if init:
                self.fake_hit_rate_meas_all = self.fake_hit_rate_meas[np.newaxis, :, :]
                init = False
            else:
                self.fake_hit_rate_meas_all = np.concatenate([self.fake_hit_rate_meas_all, self.fake_hit_rate_meas[np.newaxis, :, :]], axis=0)

        for plane in range(6):
            logging.info('Fake hit rate limit is reached. Final thresholds are {0:s}'.format([val for val in self.thr[plane, :]]))

        self.hist_occ.stop.set()  # stop analysis process

        # Store configuration to file
        self.store_configuration()

    def analyze(self):
        output_file = self.run_filename + '_interpreted.pdf'
        logging.info('Plotting results into {0:s}'.format(output_file))
        with PdfPages(output_file) as output_pdf:
            plotting.plot_noise_tuning_result(fake_hit_rate=self.fake_hit_rate_meas_all,
                                              fake_hit_rate_spec=self.fake_hit_rate,
                                              output_pdf=output_pdf)


if __name__ == "__main__":
    try:
        from pymosa import __version__ as pymosa_version
    except ImportError:
        try:
            with open(os.path.join(os.path.split(os.path.split(os.path.abspath(__file__))[0])[0], 'VERSION')) as version_file:
                pymosa_version = version_file.read().strip()
        except IOError:
            raise
            pymosa_version = "(local)"

    import argparse
    parser = argparse.ArgumentParser(description='Noise occupancy tuning for pymosa %s\nExample: python noise_tuning.py' % pymosa_version, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-t', '--scan_timeout', type=int, metavar='<scan timeout>', action='store', help='Scan timeout, time in which noise occupancy is integrated, in seconds')
    parser.add_argument('-r', '--fake_hit_rate', type=int, metavar='<fake hit rate>', action='store', help='Allowed (average) fake hit rate, per pixel per readout frame (115.2 us)')
    parser.add_argument('-s', '--thr_start', type=int, metavar='<thr start>', action='store', help='Start value from which threshold is lowered, same value for all regions A, B, C, D')
    parser.add_argument('-w', '--thr_step', type=int, metavar='<thr step>', action='store', help='Step width for lowering threshold, same value for all regions A, B, C, D')
    args = parser.parse_args()

    with open('./m26_configuration.yaml', 'r') as f:
        config = yaml.safe_load(f)

    if args.scan_timeout is not None:
        config["scan_timeout"] = range(args.scan_timeout)
    if args.fake_hit_rate is not None:
        config["fake_hit_rate"] = args.fake_hit_rate
    if args.thr_start is not None:
        config["thr_start"] = args.thr_start
    if args.fake_hit_rate is not None:
        config["thr_step"] = args.thr_step

    noise_tuning = NoiseOccTuning()  # None: use default hardware configuration
    # Initialize telescope hardware and set up parameters
    noise_tuning.init(init_conf=config)
    # Start telescope readout
    noise_tuning.start()
    # Close the resources
    noise_tuning.close()
