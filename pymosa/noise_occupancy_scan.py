import logging
import os
from time import time, sleep

import yaml
import numpy as np
import progressbar
from matplotlib.backends.backend_pdf import PdfPages

from basil.utils.BitLogic import BitLogic

from pymosa.m26 import m26
from pymosa import online as oa
from m26_raw_data import open_raw_data_file, send_meta_data
from pymosa import plotting as plotting


class NoiseOccScan(m26):
    '''Noise Occupancy Scan

    This script measures the noise occupancy.
    '''

    def print_log_status(self):
        m26_rx_names = [rx.name for rx in self.dut.get_modules('m26_rx')]
        logging.info('Mimosa26 RX channel:     %s', " | ".join([name.rjust(3) for name in m26_rx_names]))
        for i, region in enumerate(['A', 'B', 'C', 'D']):
            logging.info('Fake hit rate %s:         %s', region, " | ".join([format(count, '.1e').rjust(max(3, len(m26_rx_names[index]))) for index, count in enumerate(self.fake_hit_rate_meas[:, i])]))
        logging.info('Noise occupancy:         %s', " | ".join([repr(count).rjust(max(3, len(m26_rx_names[index]))) for index, count in enumerate(self.hit_occ_map[:, :, :].sum(axis=(0, 1)))]))

    def take_data(self, update_rate=1):
        with self.readout():
            start = time()
            logging.info('Taking data...')
            self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.Timer()], maxval=self.scan_timeout, poll=10, term_width=80).start()
            for _ in range(self.scan_timeout / update_rate):
                sleep(update_rate)
                try:
                    self.progressbar.update(time() - start)
                except ValueError:
                        pass

            self.progressbar.finish()

        # Get hit occupancy for every plane using fast online analysis
        hit_occ_map = self.hist_occ.get()

        return hit_occ_map

    def init(self, init_conf=None, configure_m26=True):
        # set name of scan
        init_conf["run_id"] = 'noise_occupancy_scan'

        super(NoiseOccScan, self).init(init_conf=init_conf, configure_m26=configure_m26)
        self.hist_occ = oa.OccupancyHistogramming()

        self.scan_timeout = self.telescope_conf.get('scan_timeout', 5)  # time for which noise occupancy is measured in seconds

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
        # Define columns which belong to regions A, B, C, D
        m26_regions = [(0, 288), (288, 576), (576, 864), (864, 1151)]
        self.fake_hit_rate_meas = np.zeros(shape=(6, 4))

        # Take data and get noise occupancy
        self.hit_occ_map = self.take_data()
        for plane in range(6):
            for region in range(4):
                self.fake_hit_rate_meas[plane, region] = self.hit_occ_map[m26_regions[region][0]:m26_regions[region][1], :, plane].sum() / 576. / 288. / self.scan_timeout / 1e6 * 115.2

        self.hist_occ.stop.set()  # stop analysis process

        # Log status (fake hit rate, noise occupoancy, threshold setting)
        self.print_log_status()

    def analyze(self):
        output_file = self.run_filename + '_interpreted.pdf'
        logging.info('Plotting results into %s' % output_file)
        with PdfPages(output_file) as output_pdf:
            for plane in range(6):
                plotting.plot_occupancy(hist=np.ma.masked_where(self.hit_occ_map[:, :, plane] == 0, self.hit_occ_map[:, :, plane]),
                                        title='Occupancy for plane %i' % plane,
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
    parser = argparse.ArgumentParser(description='Tune TLU for pymosa %s\nExample: python tune_tlu.py' % pymosa_version, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-t', '--scan_timeout', type=int, metavar='<scan timeout>', action='store', help='Scan timeout, time in which noise occupancy is integrated, in seconds')
    args = parser.parse_args()

    with open('./m26_configuration.yaml', 'r') as f:
        config = yaml.load(f)

    if args.scan_timeout is not None:
        config["scan_timeout"] = range(args.scan_timeout)

    noise_occ_scan = NoiseOccScan()  # None: use default hardware configuration
    # Initialize telescope hardware and set up parameters
    noise_occ_scan.init(init_conf=config)
    # Start telescope readout
    noise_occ_scan.start()
    # Close the resources
    noise_occ_scan.close()
