import logging
import os
import time

import yaml
import numpy as np
import tables as tb
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages

from pymosa.m26 import m26
from m26_raw_data import open_raw_data_file, send_meta_data


class TluTuning(m26):
    '''TLU Tuning

    This script tries to find a delay value for the TLU module that the error rate in the trigger number transfer is 0.
    An error is detected when the trigger number does not increase by one.

    Note:
    The TLU has to be started with internal trigger generation (e.g. pytlu -t 10000 -c 1000000).
    '''
    def init(self, init_conf=None, configure_m26=True):
        # set JTAG configuration always False, not needed here
        init_conf["m26_jtag_configuration"] = False
        # set name of scan
        init_conf["run_id"] = 'tune_tlu'
        # set unlimited amount of triggers
        init_conf["max_triggers"] = False
        # set correct trigger data format
        init_conf['TLU']['DATA_FORMAT'] = 0  # TLU trigger number only
        init_conf['TLU']['TRIGGER_MODE'] = 3  # TLU handshake

        self.scan_parameters = {"TRIGGER_DATA_DELAY": None}

        super(TluTuning, self).init(init_conf=init_conf, configure_m26=configure_m26)

        self.sleep = self.telescope_conf.get('sleep', 2)  # time for which trigger data delay is scanned in seconds
        self.trigger_data_delay_range = self.telescope_conf.get('trigger_data_delay_range', range(16))  # time for which trigger data delay is scanned in seconds

    def open_file(self):
        self.raw_data_file = open_raw_data_file(filename=self.run_filename,
                                                mode='w',
                                                title=os.path.basename(self.run_filename),
                                                socket_address=self.send_data,
                                                scan_parameters=self.scan_parameters)
        if self.raw_data_file.socket:
            # send reset to indicate a new scan for the online monitor
            send_meta_data(self.raw_data_file.socket, None, name='Reset')

    def handle_data(self, data, new_file=False, flush=True):
        '''Handling of raw data and meta data during readout.
        '''
        for data_tuple in data:
            if data_tuple is None:
                continue
            self.raw_data_file.append(data_iterable=data_tuple, scan_parameters=self.scan_parameters, new_file=new_file, flush=flush)

    def scan(self):
        for value in self.trigger_data_delay_range:  # loop over trigger data delays
            logging.info('Setting trigger data delay to %i' % value)
            self.dut['TLU']['TRIGGER_DATA_DELAY'] = value
            self.scan_parameters['TRIGGER_DATA_DELAY'] = value
            with self.readout(enabled_m26_channels=[]):
                self.dut['TLU']['TRIGGER_ENABLE'] = True
                time.sleep(self.sleep)
                self.dut['TLU']['TRIGGER_ENABLE'] = False
                if self.dut['TLU']['TRIGGER_COUNTER'] == 0:
                    raise RuntimeError('No triggers collected. Check if TLU is on and the IO is set correctly.')

    def analyze(self):
        # Small analysis helper functions
        def _get_meta_data_index_at_scan_parameter(scan_parameter_values):
            diff = np.concatenate(([1], np.diff(scan_parameter_values)))
            idx = np.concatenate((np.where(diff)[0], [len(scan_parameter_values)]))
            return idx[:-1]

        def _get_ranges_from_array(arr, append_last=True):
            right = arr[1:]
            if append_last:
                left = arr[:]
                right = np.append(right, None)
            else:
                left = arr[:-1]
            return np.column_stack((left, right))

        with tb.open_file(self.run_filename + '.h5', 'r') as in_file_h5:
            scan_parameters = in_file_h5.root.scan_parameters[:]['TRIGGER_DATA_DELAY']  # Table with the scan parameter value for every readout
            meta_data = in_file_h5.root.meta_data[:]
            data_words = in_file_h5.root.raw_data[:]
            if data_words.shape[0] == 0:
                raise RuntimeError('No trigger words recorded')
            readout_indices = _get_meta_data_index_at_scan_parameter(scan_parameter_values=scan_parameters)  # Readout indices where the scan parameter changed
            with tb.open_file(self.run_filename + '_interpreted.h5', 'w') as out_file_h5:
                with PdfPages(self.run_filename + '_interpreted.pdf', 'w') as output_pdf:
                    description = [('TRIGGER_DATA_DELAY', np.uint8), ('error_rate', np.float)]  # Output data table description
                    data_array = np.zeros((len(readout_indices),), dtype=description)
                    data_table = out_file_h5.create_table(out_file_h5.root, name='error_rate', description=np.zeros((1,), dtype=description).dtype,
                                                          title='Trigger number error rate for different data delay values')
                    for index, (index_low, index_high) in enumerate(_get_ranges_from_array(readout_indices)):  # Loop over the scan parameter data
                        data_array['TRIGGER_DATA_DELAY'][index] = scan_parameters[index_low]
                        word_index_start = meta_data[index_low]['index_start']
                        word_index_stop = meta_data[index_high]['index_start'] if index_high is not None else meta_data[-1]['index_stop']
                        actual_raw_data = data_words[word_index_start:word_index_stop]
                        selection = np.bitwise_and(actual_raw_data, 0x80000000) == 0x80000000
                        trigger_numbers = np.bitwise_and(actual_raw_data[selection], 0x7FFFFFFF)  # Get the trigger number
                        if selection.shape[0] != word_index_stop - word_index_start:
                            logging.warning('There are not only trigger words in the data stream')
                        # the counter can wrap arount at any power of 2
                        diff = np.diff(trigger_numbers)
                        where = np.where(diff != 1)[0]
                        actual_errors = np.count_nonzero((trigger_numbers[where] + diff[diff != 1]) != 0 | ~((trigger_numbers[where] & (trigger_numbers[where] + 1)) == 0))
                        data_array['error_rate'][index] = float(actual_errors) / selection.shape[0]

                        # Plot trigger number
                        fig = Figure()
                        FigureCanvas(fig)
                        ax = fig.add_subplot(111)
                        ax.plot(range(trigger_numbers.shape[0]), trigger_numbers, '-', label='data')
                        ax.set_title('Trigger words for delay setting index %d' % index)
                        ax.set_xlabel('Trigger word index')
                        ax.set_ylabel('Trigger word')
                        ax.grid(True)
                        ax.legend(loc=0)
                        output_pdf.savefig(fig)

                    data_table.append(data_array)  # Store valid data
                    if np.all(data_array['error_rate'] != 0):
                        raise ValueError('There is no delay setting without errors. Errors: %s' % str(data_array['error_rate']))
                    logging.info('Errors: %s', str(data_array['error_rate']))

                    # Determine best delay setting (center of working delay settings)
                    good_indices = np.where(np.logical_and(data_array['error_rate'][:-1] == 0, np.diff(data_array['error_rate']) == 0))[0]
                    best_index = good_indices[good_indices.shape[0] // 2]
                    best_delay_setting = data_array['TRIGGER_DATA_DELAY'][best_index]
                    logging.info('The best delay setting for this setup is %d', best_delay_setting)

                    # Plot error rate plot
                    fig = Figure()
                    FigureCanvas(fig)
                    ax = fig.add_subplot(111)
                    ax.plot(data_array['TRIGGER_DATA_DELAY'], data_array['error_rate'], '.-', label='data')
                    ax.plot([best_delay_setting, best_delay_setting], [0, 1], '--', label='best delay setting')
                    ax.set_title('Trigger word error rate for different data delays')
                    ax.set_xlabel('TRIGGER_DATA_DELAY')
                    ax.set_ylabel('Error rate')
                    ax.grid(True)
                    ax.legend(loc=0)
                    output_pdf.savefig(fig)


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
    parser.add_argument('-r', '--trigger_data_delay_range', type=int, metavar='<trigger data delay range>', action='store', help='Values for which trigger data delay is scanned, range(trigger_data_delay_range)')
    parser.add_argument('-s', '--sleep', type=int, metavar='<sleep>', action='store', help='Time each trigger data delay is scanned, in seconds')
    args = parser.parse_args()

    with open('./m26_configuration.yaml', 'r') as f:
        config = yaml.load(f)

    if args.trigger_data_delay_range is not None:
        config["trigger_data_delay_range"] = range(args.trigger_data_delay_range)
    if args.sleep is not None:
        config["sleep"] = args.sleep

    tune_tlu = TluTuning()  # None: use default hardware configuration
    # Initialize telescope hardware and set up parameters
    tune_tlu.init(init_conf=config)
    # Start telescope readout
    tune_tlu.start()
    # Close the resources
    tune_tlu.close()
