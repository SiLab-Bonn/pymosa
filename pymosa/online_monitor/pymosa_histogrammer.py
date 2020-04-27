''' Histograms the Mimosa26 hit table'''

import numpy as np
from numba import njit

# Online monitor imports
from online_monitor.converter.transceiver import Transceiver
from online_monitor.utils import utils


@njit
def create_occupancy_hist(hist, hits):
    for hit_index in range(hits.shape[0]):
        col = hits[hit_index]['column']
        row = hits[hit_index]['row']
        plane_id = hits[hit_index]['plane']
        hist[plane_id - 1, col, row] += 1


@njit
def create_event_status_hist(hist, hits):
    for hit_index in range(hits.shape[0]):
        event_status = hits[hit_index]['event_status']
        plane = hits[hit_index]['plane']
        for i in range(32):
            if event_status & (1 << i):
                hist[plane - 1][i] += 1


class PymosaMimosa26Histogrammer(Transceiver):

    def setup_transceiver(self):
        self.set_bidirectional_communication()  # We want to be able to change the histogrammmer settings

    def setup_interpretation(self):
        self.occupancy_arrays = np.zeros(shape=(6, 1152, 576), dtype=np.int32)
        self.event_status_hist = np.zeros(shape=(6, 32), dtype=np.int32)
        # Variables
        self.n_readouts = 0
        self.readout = 0
        self.ts_last_readout = 0  # timestamp of last readout
        self.fps = 0  # data frames per second
        self.hps = 0  # hits per second
        self.eps = 0  # events per second
        self.plot_delay = 0
        self.total_hits = 0
        self.total_events = 0
        self.updateTime = 0
        self.mask_noisy_pixel = False

    def deserialize_data(self, data):
        # return jsonapi.loads(data, object_hook=utils.json_numpy_obj_hook)
        datar, meta = utils.simple_dec(data)
        if 'hits' in meta:
            meta['hits'] = datar
        return meta

    def interpret_data(self, data):
        if 'meta_data' in data[0][1]:
            meta_data = data[0][1]['meta_data']
            total_hits_now = meta_data['n_hits']
            self.hits_last_readout = total_hits_now
            total_events_now = meta_data['n_events']
            self.events_last_readout = total_events_now
            ts_now = float(meta_data['timestamp_stop'])
            # Calculate readout per second with smoothing
            recent_fps = 1.0 / (ts_now - self.ts_last_readout)
            self.fps = self.fps * 0.95 + recent_fps * 0.05
            # Calulate hits per second with smoothing
            recent_hps = self.hits_last_readout * recent_fps
            self.hps = self.hps * 0.95 + recent_hps * 0.05
            # Calulate hits per second with smoothing
            recent_eps = self.events_last_readout * recent_fps
            self.eps = self.eps * 0.95 + recent_eps * 0.05

            self.ts_last_readout = ts_now
            self.total_hits += total_hits_now
            self.total_events += total_events_now

            meta_data.update({'fps': self.fps, 'hps': self.hps, 'total_hits': self.total_hits, 'eps': self.eps, 'total_events': self.total_events})
            return [data[0][1]]

        self.readout += 1

        if self.n_readouts != 0:
            if self.readout % self.n_readouts == 0:
                self.occupancy_arrays = np.zeros(shape=(6, 1152, 576), dtype=np.int32)  # Reset occ hists
                self.event_status_hist = np.zeros(shape=(6, 32), dtype=np.int32)  # Reset event status hists
                self.readouts = 0
        hits = data[0][1]['hits']

        if hits.shape[0] == 0:  # Empty array
            return

        # Create histograms
        create_occupancy_hist(self.occupancy_arrays, hits)
        create_event_status_hist(self.event_status_hist, hits)

        # Mask Noisy pixels
        if self.mask_noisy_pixel:
            for plane in range(6):
                self.occupancy_arrays[plane, self.occupancy_arrays[plane, :, :] > self.config['noisy_threshold']] = 0

        histogrammed_data = {
            'occupancies': self.occupancy_arrays,
            'event_status': self.event_status_hist
        }

        return [histogrammed_data]

    def serialize_data(self, data):
        # return jsonapi.dumps(data, cls=utils.NumpyEncoder)
        if 'occupancies' in data:
            hits_data = data['occupancies']
            data['occupancies'] = None
            return utils.simple_enc(hits_data, data)
        else:
            return utils.simple_enc(None, data)

    def handle_command(self, command):
        if command[0] == 'RESET':
            self.occupancy_arrays = np.zeros(shape=(6, 1152, 576), dtype=np.int32)  # Reset occ hists
            self.event_status_hist = np.zeros(shape=(6, 32), dtype=np.int32)  # Reset event status hists
            self.total_hits = 0
            self.total_events = 0
        elif 'MASK' in command[0]:
            if '0' in command[0]:
                self.mask_noisy_pixel = False
            else:
                self.mask_noisy_pixel = True
        else:
            self.n_readouts = int(command[0])
            self.occupancy_arrays = np.zeros(shape=(6, 1152, 576), dtype=np.int32)  # Reset occ hists
            self.event_status_hist = np.zeros(shape=(6, 32), dtype=np.int32)  # Reset event status hists
