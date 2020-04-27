''' This is a producer faking data coming from Pymosa by taking real data and sending these in chunks'''

import logging
import time

import numpy as np
import tables as tb
import zmq

from online_monitor.utils.producer_sim import ProducerSim


class Pymosa(ProducerSim):

    def setup_producer_device(self):
        ProducerSim.setup_producer_device(self)
        self.in_file_h5 = tb.open_file(self.config['data_file'], mode="r")
        self.meta_data = self.in_file_h5.root.meta_data[:]
        self.raw_data = self.in_file_h5.root.raw_data
        self.n_readouts = self.meta_data.shape[0]
        self.total_data = 0  # amount of replayed data in MB
        self.time_start = time.time()  # calculate duration of replay
        self.time_end = 0  # calculate duration of replay

        try:
            self.scan_parameter_name = self.in_file_h5.root.scan_parameters.dtype.names
            self.scan_parameters = self.in_file_h5.root.scan_parameters[:]
        except tb.NoSuchNodeError:
            self.scan_parameter_name = 'No parameter'
            self.scan_parameters = None

        self.readout_word_indeces = np.column_stack((self.meta_data['index_start'], self.meta_data['index_stop']))
        self.actual_readout = 0
        self.last_readout_time = None

    def get_data(self):  # Return the data of one readout
        if self.actual_readout < self.n_readouts:
            index_start, index_stop = self.readout_word_indeces[self.actual_readout]
            data = []
            data.append(self.raw_data[index_start:index_stop])
            data.extend((float(self.meta_data[self.actual_readout]['timestamp_start']),
                         float(self.meta_data[self.actual_readout]['timestamp_stop']),
                         int(self.meta_data[self.actual_readout]['error'])))

            # FIXME: Simple syncronization to replay with similar timing, does not really work
            now = time.time()
            if self.last_readout_time is not None:
                delay = now - self.last_readout_time
                additional_delay = self.meta_data[self.actual_readout]['timestamp_stop'] - self.meta_data[self.actual_readout]['timestamp_start'] - delay
                if additional_delay > 0:
                    time.sleep(additional_delay)
            self.last_readout_time = now

            if self.scan_parameters is not None:
                return data, {str(self.scan_parameter_name): int(self.scan_parameters[self.actual_readout][0])}
            else:
                return data, {'No parameter': 0}

    def send_data(self):
        '''Sends the data of every read out (raw data and meta data) via ZeroMQ to a specified socket
        '''
        time.sleep(float(self.config['delay']))  # Delay is given in seconds

        try:
            data, scan_parameters = self.get_data()  # Get data of actual readout
        except TypeError:  # Data is fully replayes
            self.time_end = time.time()
            logging.warning('%s producer: No data to replay anymore! Data send in %.2f s is %.2f MB' % (self.name, self.time_end - self.time_start, self.total_data / (1024.0 ** 2)))  # show amount of sent data after replay ended
            time.sleep(10)
            return

        self.actual_readout += 1

        data_meta_data = dict(
            name='ReadoutData',
            dtype=str(data[0].dtype),
            shape=data[0].shape,
            timestamp_start=data[1],  # float
            timestamp_stop=data[2],  # float
            readout_error=data[3],  # int
            scan_parameters=scan_parameters  # dict
        )
        try:
            self.total_data += data[0].nbytes  # sum up sent data packages
            self.sender.send_json(data_meta_data, flags=zmq.SNDMORE | zmq.NOBLOCK)
            self.sender.send(data[0], flags=zmq.NOBLOCK)  # PyZMQ supports sending numpy arrays without copying any data
        except zmq.Again:
            pass

    def __del__(self):
        self.in_file_h5.close()
