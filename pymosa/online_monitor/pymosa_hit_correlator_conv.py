from numba import njit

from zmq.utils import jsonapi
import numpy as np
import gc
import os
from online_monitor.converter.transceiver import Transceiver
from online_monitor.utils import utils
import yaml


@njit
def correlate_position_on_event_number(ref_event_numbers, dut_event_numbers, ref_x_indices, ref_y_indices, dut_x_indices, dut_y_indices, x_corr_histo, y_corr_histo, transpose=False):
    """Correlating the hit/cluster positions on event basis including all permutations.
    The hit/cluster positions are used to fill the X and Y correlation histograms.

    Does the same than the merge of the pandas package:
        df = data_1.merge(data_2, how='left', on='event_number')
        df.dropna(inplace=True)
        correlation_column = np.hist2d(df[column_mean_dut_0], df[column_mean_dut_x])
        correlation_row = np.hist2d(df[row_mean_dut_0], df[row_mean_dut_x])
    The following code is > 10x faster than the above code.

    Parameters
    ----------
    ref_event_numbers: array
        Event number array of the reference DUT.
    dut_event_numbers: array
        Event number array of the second DUT.
    ref_x_indices: array
        X position indices of the refernce DUT.
    ref_y_indices: array
        Y position indices of the refernce DUT.
    dut_x_indices: array
        X position indices of the second DUT.
    dut_y_indices: array
        Y position indices of the second DUT.
    x_corr_hist: array
        X correlation array (2D).
    y_corr_hist: array
        Y correlation array (2D).
    transpose: boolean
        If True tranpose x/y of reference DUT. Default is False.
    """
    dut_index = 0

    # Loop to determine the needed result array size.astype(np.uint32)
    for ref_index in range(ref_event_numbers.shape[0]):
        while dut_index < dut_event_numbers.shape[0] and dut_event_numbers[dut_index] < ref_event_numbers[ref_index]:  # Catch up with outer loop
            dut_index += 1

        for curr_dut_index in range(dut_index, dut_event_numbers.shape[0]):
            if ref_event_numbers[ref_index] == dut_event_numbers[curr_dut_index]:
                if transpose:
                    x_index_ref = ref_y_indices[ref_index]
                    y_index_ref = ref_x_indices[ref_index]
                else:
                    x_index_ref = ref_x_indices[ref_index]
                    y_index_ref = ref_y_indices[ref_index]
                x_index_dut = dut_x_indices[curr_dut_index]
                y_index_dut = dut_y_indices[curr_dut_index]

                # Add correlation to histogram
                x_corr_histo[x_index_dut, x_index_ref] += 1
                y_corr_histo[y_index_dut, y_index_ref] += 1
            else:
                break


class HitCorrelator(Transceiver):
    def setup_transceiver(self):
        self.set_bidirectional_communication()  # We want to be able to change the histogrammmer settings

    def setup_interpretation(self):
        self.active_tab = None  # Stores name of active tab in online monitor
        self.hit_corr_tab = 'HIT_Correlator'  # name of correlator tab, has to match with name specified in configuration.yaml for online monitor
        self.start_signal = 1  # will be set in handle_command function; correlation starts if this is set to 0
        self.active_dut1 = 0
        self.active_dut2 = 0
        self.fps = 0
        self.updateTime = 0
        self.remove_background = False  # Remove noisy background
        self.remove_background_checkbox = 0
        self.remove_background_percentage = 99.0
        self.transpose = False  # If True transpose column and row
        self.transpose_checkbox = 0
        # Data buffer and correlation histogramms
        self.hit_data = {}  # Dict which contains separated data
        self.data_buffer = {}  # Data buffer dictionary which contains the data of the DUTs which should be correlated
        self.x_corr_hist = 0  # Correlation histogram
        self.y_corr_hist = 0  # Correlation histogram
        self.iter = 0

        # Load correlation DUT types
        config = os.path.join(os.path.dirname(__file__), 'correlation_duts.yaml')
        with open(config) as f:
            self.correlator_config = yaml.load(f)

    def deserialize_data(self, data):  # According to pyBAR data serilization
        datar, meta = utils.simple_dec(data)
        if 'hits' in meta:
            meta['hits'] = datar
        return meta

    def interpret_data(self, data):
        # Since correlation is CPU intensive process, do correlation only if Correlator Tab is active
        if self.active_tab != self.hit_corr_tab:
            return

        # Each DUT specified in configuration will get a unique index. Store index of selected DUTs
        self.active_duts = [self.active_dut1, self.active_dut2]

        # Do correlation only if start button is pressed, stop correlation if stop button is pressed
        if self.start_signal != 0:
            return

        # Show readout rate in GUI
        if 'meta_data' in data[0][1]:
            meta_data = data[0][1]['meta_data']
            now = float(meta_data['timestamp_stop'])
            if now != self.updateTime:  # FIXME: sometimes = ZeroDivisionError: because of https://github.com/SiLab-Bonn/pyBAR/issues/48
                recent_fps = 1.0 / (now - self.updateTime)  # FIXME: does not show real rate, shows rate data was recorded with
                self.updateTime = now
                self.fps = self.fps * 0.7 + recent_fps * 0.3
                meta_data.update({'fps': self.fps})
                return [data[0][1]]

        # Loop over incoming data
        for actual_dut_data in data:
            # Skip meta data
            if 'meta_data' in actual_dut_data[1]:
                continue
            if actual_dut_data[1]['hits'].shape[0] == 0:  # empty array is skipped
                continue

            # Separate hits by identifier
            for i, device in enumerate(self.config['correlation_planes']):
                # Check if tcp address of incoming data matches with specified tcp address
                if actual_dut_data[0] == device['address']:
                    # If more than one plane from the same address an additional field 'id' is used in order to separate data of same address
                    if 'id' in device:
                        sel = (actual_dut_data[1]['hits']['plane'] == device['id'] + 1)
                        actual_dut_hit_data = actual_dut_data[1]['hits'][sel]
                    else:
                        actual_dut_hit_data = actual_dut_data[1]['hits']
                    # Apppend to dict
                    if i in self.hit_data.keys():
                        self.hit_data[i] = np.append(self.hit_data[i], actual_dut_hit_data)
                    else:
                        self.hit_data[i] = actual_dut_hit_data

        # Copy hits to buffer
        for i, active_dut in enumerate(self.active_duts):
            try:
                if i in self.data_buffer.keys():
                    self.data_buffer[i] = np.append(self.data_buffer[i], self.hit_data[active_dut])
                else:
                    self.data_buffer[i] = self.hit_data[active_dut]
            except KeyError:
                return

        # In order to correlate data, data from two planes have to be selected (via GUI)
        if len(self.data_buffer) != 2:
            return

        # Check if datas are not empty
        elif len(self.data_buffer[0]) == 0 or len(self.data_buffer[1]) == 0:
            return

        # Remove background function in order to exclude noisy pixels
        def remove_background(cols_corr, rows_corr, percentage):
            cols_corr[cols_corr < np.percentile(cols_corr, percentage)] = 0
            rows_corr[rows_corr < np.percentile(rows_corr, percentage)] = 0

        # Main correlation function
        correlate_position_on_event_number(ref_event_numbers=self.data_buffer[0]['event_number'],
                                           dut_event_numbers=self.data_buffer[1]['event_number'],
                                           ref_x_indices=self.data_buffer[0]['row'],
                                           ref_y_indices=self.data_buffer[0]['column'],
                                           dut_x_indices=self.data_buffer[1]['row'],
                                           dut_y_indices=self.data_buffer[1]['column'],
                                           x_corr_histo=self.x_corr_hist,
                                           y_corr_histo=self.y_corr_hist,
                                           transpose=self.transpose)
        self.iter += 1

        if self.remove_background:
            remove_background(self.hist_cols_corr, self.hist_rows_corr, self.remove_background_percentage)

        return [{'column': self.x_corr_hist, 'row': self.y_corr_hist}]

    def serialize_data(self, data):
        return jsonapi.dumps(data, cls=utils.NumpyEncoder)

    def handle_command(self, command):
        # Reset histogramms and data buffer, call garbage collector
        def reset():
            self.x_corr_hist = np.zeros_like(self.x_corr_hist)
            self.y_corr_hist = np.zeros_like(self.y_corr_hist)
            self.data_buffer = {}
            gc.collect()  # garbage collector is called to free unused memory

        # Determine the needed histogramm size according to selected DUTs
        def create_corr_hist(dut1, dut2, transpose):
            n_cols_dut_1 = self.correlator_config[self.config['correlation_planes'][dut1]['dut_type']]['n_columns']
            n_rows_dut_1 = self.correlator_config[self.config['correlation_planes'][dut1]['dut_type']]['n_rows']
            n_cols_dut_2 = self.correlator_config[self.config['correlation_planes'][dut2]['dut_type']]['n_columns']
            n_rows_dut_2 = self.correlator_config[self.config['correlation_planes'][dut2]['dut_type']]['n_rows']
            if transpose:
                self.x_corr_hist = np.zeros(shape=(n_rows_dut_1, n_cols_dut_2), dtype=np.uint32)
                self.y_corr_hist = np.zeros(shape=(n_cols_dut_1, n_rows_dut_2), dtype=np.uint32)
            else:
                self.x_corr_hist = np.zeros(shape=(n_cols_dut_1, n_cols_dut_2), dtype=np.uint32)
                self.y_corr_hist = np.zeros(shape=(n_rows_dut_1, n_rows_dut_2), dtype=np.uint32)
            reset()

        # Commands
        if command[0] == 'RESET':
            reset()
        elif 'combobox1' in command[0]:
            # Get active DUT from combobox selection
            self.active_dut1 = int(command[0].split()[1])
            create_corr_hist(self.active_dut1, self.active_dut2, self.transpose)
        elif 'combobox2' in command[0]:
            # Get active DUT from combobox selection
            self.active_dut2 = int(command[0].split()[1])
            create_corr_hist(self.active_dut1, self.active_dut2, self.transpose)
        elif 'START' in command[0]:
            # Get status of start button. Only do correlation if start buton is pressed
            self.start_signal = int(command[0].split()[1])
            create_corr_hist(self.active_dut1, self.active_dut2, self.transpose)
        elif 'ACTIVETAB' in command[0]:
            # Get active tab. Only do correlation if active tab is correlator tab
            self.active_tab = str(command[0].split()[1])
        elif 'STOP' in command[0]:
            # Get status of stop button. If pressed, stop correlation
            self.start_signal = int(command[0].split()[1]) + 1
            reset()
        elif 'BACKGROUND' in command[0]:
            self.remove_background_checkbox = int(command[0].split()[1])
            if self.remove_background_checkbox == 0:
                self.remove_background = False
                reset()
            elif self.remove_background_checkbox == 2:
                self.remove_background = True
        elif 'PERCENTAGE' in command[0]:
            self.remove_background_percentage = float(command[0].split()[1])
            if self.remove_background:
                reset()
        elif 'TRANSPOSE' in command[0]:
            self.transpose_checkbox = int(command[0].split()[1])
            if self.active_dut1 == 0 or self.active_dut2 == 0:
                if self.transpose_checkbox == 0:
                    self.transpose = False
                elif self.transpose_checkbox == 2:
                    self.transpose = True
                create_corr_hist(self.active_dut1, self.active_dut2, self.transpose)