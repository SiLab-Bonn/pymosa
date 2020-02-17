import logging
import datetime
from time import sleep, time, mktime
from threading import Thread, Event, Lock, Condition
from collections import deque, Iterable
import sys

import numpy as np

from basil.HL import sitcp_fifo

data_iterable = ("data", "timestamp_start", "timestamp_stop", "error")

# Python 2/3 compability
try:
    basestring  # noqa
except NameError:
    basestring = str  # noqa


def get_float_time():
    '''returns time as double precision floats - Time64 in pytables - mapping to and from python datetime's
    '''
    t1 = time()
    t2 = datetime.datetime.fromtimestamp(t1)
    return mktime(t2.timetuple()) + 1e-6 * t2.microsecond


class FifoError(Exception):
    pass


class NoDataTimeout(Exception):
    pass


class StopTimeout(Exception):
    pass


# from pyBAR
class M26Readout(object):
    def __init__(self, dut):
        self.dut = dut
        self.is_running_lock = Lock()
        self.data_words_per_second_lock = Lock()
        self.callback = None
        self.errback = None
        self.readout_thread = None
        self.worker_thread = None
        self.writer_threads = None
        self.watchdog_thread = None
        self.fifos = []
        self.fifo_condition = []
        self.fill_buffer = False
        self.filter_func = [None]
        self.converter_func = [None]
        self.fifo_select = [None]
        self.enabled_m26_channels = None
        self.readout_interval = 0.05  # in seconds
        self.write_interval = 1.0  # in seconds
        self.watchdog_interval = 1.0  # in seconds
        self._moving_average_time_period = 10.0  # in seconds
        self._n_empty_reads = 3  # number of empty reads before stopping FIFO readout
        self._fifo_data_deque = None
        self._fifo_conditions = None
        self._data_deque = None  # stores data for writer thread
        self._data_conditions = None
        self._data_buffer = None  # stores data for later readout
        self._data_deque = None
        self._words_per_read = []
        self.stop_readout = Event()
        self.force_stop = None
        self.timestamp = None
        self._is_running = False

    @property
    def is_running(self):
        with self.is_running_lock:
            return self._is_running

    def data_words_per_second(self):
        with self.data_words_per_second_lock:
            result = []
            curr_time = get_float_time()
            for words_per_read in self._words_per_read:
                result.append(sum([item[0] for item in words_per_read if item[1] > (curr_time - self._moving_average_time_period)]) / float(self._moving_average_time_period))
            return result

    def start(self, fifos, callback=None, errback=None, reset_rx=False, reset_fifo=False, fill_buffer=False, no_data_timeout=None, filter_func=None, converter_func=None, fifo_select=None, enabled_m26_channels=None):
        with self.is_running_lock:
            if self._is_running:
                raise RuntimeError('FIFO readout threads already started: use stop()')
            self._is_running = True

            if isinstance(fifos, basestring):
                fifos = [fifos]
            if len(fifos) == 0:
                raise ValueError('"fifos" parameter is empty.')
            if len(set(fifos)) != len(fifos):
                raise ValueError('The following strings are occurring multiple times in "fifos": %s' % set([fifo for fifo in fifos if fifos.count(fifo) > 1]))
            if isinstance(fifo_select, Iterable) and set(fifo_select) - set(fifos):
                raise ValueError("The following FIFOs have filters/converters set but are not read out: %s" % (set(fifo_select) - set(fifos)))
            if isinstance(filter_func, Iterable) or isinstance(converter_func, Iterable) or (isinstance(fifo_select, Iterable) and not isinstance(fifo_select, basestring)):
                if not isinstance(filter_func, Iterable):
                    raise ValueError('"filter_func" is not iterable.')
                if not isinstance(converter_func, Iterable):
                    raise ValueError('"converter_func" is not iterable.')
                if not isinstance(fifo_select, Iterable):
                    raise ValueError('"fifo_select" is not iterable.')
                if len(filter_func) != len(converter_func):
                    raise ValueError('Length of "filter_func" and "converter_func" not equal.')
                if len(filter_func) != len(fifo_select):
                    raise ValueError('Length of "filter_func" and "fifo_select" not equal.')
                if len(converter_func) != len(fifo_select):
                    raise ValueError('Length of "converter_func" and "fifo_select" not equal.')
            else:
                if isinstance(fifo_select, basestring):
                    # convert to iterable
                    filter_func = [filter_func]
                    converter_func = [converter_func]
                    fifo_select = [fifo_select]
                else:
                    # if fifo_select is None:
                    # adding filters and converters for each FIFO
                    filter_func = [filter_func] * len(fifos)
                    converter_func = [converter_func] * len(fifos)
                    fifo_select = fifos
            if not (set(fifos) & set(fifo_select)) == set(fifo_select):
                raise ValueError('"fifo_select" contains non-existing FIFOs: %s' % (set(fifo_select) & set(fifos)))

            if enabled_m26_channels is None:
                self.enabled_m26_channels = [rx.name for rx in self.dut.get_modules('m26_rx')]
            else:
                self.enabled_m26_channels = enabled_m26_channels
            self.fifos = fifos
            self.callback = callback
            self.errback = errback
            self.fill_buffer = fill_buffer
            self.filter_func = filter_func
            self.converter_func = converter_func
            self.fifo_select = fifo_select

            self._fifo_data_deque = {fifo: deque() for fifo in self.fifos}
            self._fifo_conditions = {fifo: Condition() for fifo in self.fifos}
            self._data_deque = [deque() for _ in self.filter_func]
            self._data_conditions = [Condition() for _ in self.filter_func]
            self._data_buffer = [deque() for _ in self.filter_func]
            self.force_stop = {fifo: Event() for fifo in self.fifos}
            self.timestamp = {fifo: None for fifo in self.fifos}
            len_deque = int(self._moving_average_time_period / self.readout_interval)
            curr_time = get_float_time()
            self._words_per_read = [deque(iterable=[(0, curr_time, curr_time)] * len_deque, maxlen=len_deque) for _ in self.filter_func]
            if reset_rx:
                self.reset_rx(m26_channels=self.enabled_m26_channels)
            for fifo in self.fifos:
                if reset_fifo:
                    self.reset_fifo([fifo])
                self.update_timestamp(fifo)
                fifo_size = self.get_fifo_size(fifo)
                if fifo_size != 0:
                    logging.warning('%s contains data: FIFO_SIZE = %i', fifo, fifo_size)
            self.stop_readout.clear()
            for event in self.force_stop.values():
                event.clear()
            logging.info('Starting FIFO readout...')
            if self.errback:
                self.watchdog_thread = Thread(target=self.watchdog, name='WatchdogThread')
                self.watchdog_thread.daemon = True
                self.watchdog_thread.start()
            self.readout_threads = []
            self.worker_threads = []
            self.writer_threads = []
            for fifo in self.fifos:
                readout_thread = Thread(target=self.readout, name='ReadoutThread %s' % fifo, kwargs={'fifo': fifo, 'no_data_timeout': no_data_timeout})
                worker_thread = Thread(target=self.worker, name='WorkerThread %s' % fifo, kwargs={'fifo': fifo})
                readout_thread.daemon = True
                worker_thread.daemon = True
                self.readout_threads.append(readout_thread)
                self.worker_threads.append(worker_thread)
            for index, _ in enumerate(self.filter_func):
                writer_thread = Thread(target=self.writer, name='WriterThread %d' % index, kwargs={'index': index, 'no_data_timeout': no_data_timeout})
                writer_thread.daemon = True
                self.writer_threads.append(writer_thread)
            for writer_thread in self.writer_threads:
                writer_thread.start()
            for worker_thread in self.worker_threads:
                worker_thread.start()
            for readout_thread in self.readout_threads:
                self.update_timestamp(fifo)
                readout_thread.start()
            # enabling RX channels
            for fifo in self.fifos:
                self.update_timestamp(fifo)
            for m26_rx_name in self.enabled_m26_channels:
                self.dut[m26_rx_name].EN = 1

    def stop(self, timeout=10.0):
        with self.is_running_lock:
            if not self._is_running:
                raise RuntimeError('FIFO readout threads not running: use start()')
            self._is_running = False
            # disabling Mimosa26 RX channels, the Mimosa26 RX is continuously providing data
            # and therefore this has to be disabled before readout stop
            for m26_rx_name in self.enabled_m26_channels:
                self.dut[m26_rx_name].EN = 0
            self.stop_readout.set()

            def wait_for_thread_timeout(thread, fifo, timeout):
                try:
                    thread.join(timeout=timeout)
                    if thread.is_alive():
                        raise StopTimeout('Stopping %s readout thread timed out after %0.1fs' % (fifo, timeout))
                except StopTimeout as e:
                    self.force_stop[fifo].set()
                    if self.errback:
                        self.errback(sys.exc_info())
                    else:
                        logging.error(e)

            join_threads = []
            for i, fifo in enumerate(self.fifos):
                join_thread = Thread(target=wait_for_thread_timeout, kwargs={'thread': self.readout_threads[i], 'fifo': fifo, 'timeout': timeout})
                join_thread.daemon = True
                join_thread.start()
                join_threads.append(join_thread)
            for join_thread in join_threads:
                if join_thread.is_alive():
                    join_thread.join()
            for readout_thread in self.readout_threads:
                if readout_thread.is_alive():
                    readout_thread.join()
            self.readout_threads = []
            for worker_thread in self.worker_threads:
                worker_thread.join()
            self.worker_threads = []
            for writer_thread in self.writer_threads:
                writer_thread.join()
            self.writer_threads = []
            if self.errback:
                self.watchdog_thread.join()
                self.watchdog_thread = None
            self.callback = None
            self.errback = None
            logging.info('Stopped FIFO readout')

    def print_readout_status(self):
        self.print_fifo_status()
        self.print_m26_rx_status()

    def print_fifo_status(self):
        fifo_sizes = [self.get_fifo_size(fifo) for fifo in self.fifos]
        fifo_queue_sizes = [len(self._fifo_data_deque[fifo]) for fifo in self.fifos]
        max_len = [max(max(len(repr(fifo_sizes[i])), len(repr(fifo_queue_sizes[i]))), len(fifo)) for i, fifo in enumerate(self.fifos)]
        logging.info('FIFO:            %s', " | ".join([fifo.rjust(max_len[index]) for index, fifo in enumerate(self.fifos)]))
        logging.info('FIFO size:       %s', " | ".join([repr(count).rjust(max_len[index]) for index, count in enumerate(fifo_sizes)]))
        logging.info('FIFO queue size: %s', " | ".join([repr(count).rjust(max_len[index]) for index, count in enumerate(fifo_queue_sizes)]))

    def print_m26_rx_status(self):
        # Mimosa26
        m26_enable_status = self.get_m26_rx_enable_status()
        m26_discard_count = self.get_m26_rx_fifo_discard_count()
        m26_rx_names = [rx.name for rx in self.dut.get_modules('m26_rx')]
        if m26_rx_names:
            logging.info('Mimosa26 RX channel:              %s', " | ".join([name.rjust(3) for name in m26_rx_names]))
            logging.info('Mimosa26 RX enabled:              %s', " | ".join(["YES".rjust(max(3, len(m26_rx_names[index]))) if status is True else "NO".rjust(max(3, len(m26_rx_names[index]))) for index, status in enumerate(m26_enable_status)]))
            logging.info('Mimosa26 RX FIFO discard counter: %s', " | ".join([repr(count).rjust(max(3, len(m26_rx_names[index]))) for index, count in enumerate(m26_discard_count)]))
        if any(m26_discard_count):
            logging.warning('Mimosa26 RX errors detected')

    def readout(self, fifo, no_data_timeout=None):
        '''Readout thread continuously reading FIFO.

        Readout thread, which uses read_raw_data_from_fifo() and appends data to self._fifo_data_deque (collection.deque).
        '''
        logging.info('Starting readout thread for %s', fifo)
        time_last_data = time()
        time_wait = 0.0
        empty_reads = 0
        while not self.force_stop[fifo].wait(time_wait if time_wait >= 0.0 else 0.0):
            time_read = time()
            try:
                if no_data_timeout and time_last_data + no_data_timeout < get_float_time():
                    raise NoDataTimeout('Received no data for %0.1f second(s) from %s' % (no_data_timeout, fifo))
                raw_data = self.read_raw_data_from_fifo(fifo)
            except NoDataTimeout:
                no_data_timeout = None  # raise exception only once
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
            except Exception:
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
                if self.stop_readout.is_set():  # in case of a exception, break immediately
                    break
            else:
                n_data_words = raw_data.shape[0]
                if n_data_words > 0:
                    time_last_data = time()
                    empty_reads = 0
                    time_start_read, time_stop_read = self.update_timestamp(fifo)
                    status = 0
                    self._fifo_data_deque[fifo].append((raw_data, time_start_read, time_stop_read, status))
                    with self._fifo_conditions[fifo]:
                        self._fifo_conditions[fifo].notify_all()
                elif self.stop_readout.is_set():
                    if empty_reads == self._n_empty_reads:
                        break
                    else:
                        empty_reads += 1
            finally:
                # ensure that the readout interval does not depend on the processing time of the data
                # and stays more or less constant over time
                time_wait = self.readout_interval - (time() - time_read)
        self._fifo_data_deque[fifo].append(None)  # last item, None will stop worker
        with self._fifo_conditions[fifo]:
            self._fifo_conditions[fifo].notify_all()
        logging.info('Stopping readout thread for %s', fifo)

    def worker(self, fifo):
        '''Worker thread continuously filtering and converting data when data becomes available.
        '''
        logging.debug('Starting worker thread for %s', fifo)
        self._fifo_conditions[fifo].acquire()
        while True:
            try:
                data_tuple = self._fifo_data_deque[fifo].popleft()
            except IndexError:
                self._fifo_conditions[fifo].wait(self.readout_interval)  # sleep a little bit, reducing CPU usage
            else:
                if data_tuple is None:  # if None then exit
                    break
                else:
                    for index, (filter_func, converter_func, fifo_select) in enumerate(zip(self.filter_func, self.converter_func, self.fifo_select)):
                        if fifo_select is None or fifo_select == fifo:
                            # filter and do the conversion
                            converted_data_tuple = convert_data_iterable((data_tuple,), filter_func=filter_func, converter_func=converter_func)[0]
                            n_data_words = converted_data_tuple[0].shape[0]
                            with self.data_words_per_second_lock:
                                self._words_per_read[index].append((n_data_words, converted_data_tuple[1], converted_data_tuple[2]))
                            self._data_deque[index].append(converted_data_tuple)
                            with self._data_conditions[index]:
                                self._data_conditions[index].notify_all()
        for index, fifo_select in enumerate(self.fifo_select):
            if fifo_select is None or fifo_select == fifo:
                self._data_deque[index].append(None)
                with self._data_conditions[index]:
                    self._data_conditions[index].notify_all()
        self._fifo_conditions[fifo].release()
        logging.debug('Stopping worker thread for %s', fifo)

    def writer(self, index, no_data_timeout=None):
        '''Writer thread continuously calling callback function for writing data when data becomes available.
        '''
        logging.debug('Starting writer thread with index %d', index)
        self._data_conditions[index].acquire()
        time_last_data_all = time()
        time_last_data = {}
        time_write = time()
        converted_data_tuple_list = [None] * len(self.filter_func)
        while True:
            try:
                if no_data_timeout:
                    for m26_id, time_last_data_m26 in time_last_data.items():
                        if time_last_data_m26 + no_data_timeout < time():
                            raise NoDataTimeout('Received no data for %0.1f second(s) from Mimosa26 plane with ID %d' % (no_data_timeout, m26_id))
                    if time_last_data_all + no_data_timeout < time():
                        raise NoDataTimeout('Received no data for %0.1f second(s) from %d Mimosa26 plane(s)' % (no_data_timeout, len(self.enabled_m26_channels) - len(time_last_data)))
                converted_data_tuple = self._data_deque[index].popleft()
            except NoDataTimeout:  # no data timeout
                no_data_timeout = None  # raise exception only once
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
            except IndexError:  # no data in queue
                self._data_conditions[index].wait(self.readout_interval)  # sleep a little bit, reducing CPU usage
            else:
                if converted_data_tuple is None:  # if None then write and exit
                    if self.callback and any(converted_data_tuple_list):
                        try:
                            self.callback(converted_data_tuple_list)
                        except Exception:
                            self.errback(sys.exc_info())
                    break
                else:
                    if no_data_timeout:
                        curr_time = time()
                        m26_ids = convert_data_array(array=converted_data_tuple[0], filter_func=is_m26_word, converter_func=get_m26_ids)
                        for m26_id in m26_ids:  # check for Mimosa26 data words from different planes
                            time_last_data[m26_id] = curr_time
                        if len(time_last_data) == len(self.enabled_m26_channels):
                            time_last_data_all = time()
                    if converted_data_tuple_list[index]:
                        converted_data_tuple_list[index].append(converted_data_tuple)
                    else:
                        converted_data_tuple_list[index] = [converted_data_tuple]  # adding iterable
                    if self.fill_buffer:
                        self._data_buffer[index].append(converted_data_tuple)
            # check if calling the callback function is about time
            if self.callback and any(converted_data_tuple_list) and ((self.write_interval and time() - time_write >= self.write_interval) or not self.write_interval):
                try:
                    self.callback(converted_data_tuple_list)  # callback function gets a list of lists of tuples
                except Exception:
                    self.errback(sys.exc_info())
                else:
                    converted_data_tuple_list = [None] * len(self.filter_func)
                    time_write = time()  # update last write timestamp
        self._data_conditions[index].release()
        logging.debug('Stopping writer thread with index %d', index)

    def watchdog(self):
        logging.debug('Starting %s', self.watchdog_thread.name)
        time_wait = 0.0
        while not self.stop_readout.wait(time_wait if time_wait >= 0.0 else 0.0):
            time_read = time()
            try:
                if any(self.get_m26_rx_fifo_discard_count(channels=self.enabled_m26_channels)):
                    raise FifoError('M26 RX FIFO discard error(s) detected')
            except Exception:
                self.errback(sys.exc_info())
            time_wait = self.watchdog_interval - (time() - time_read)
        logging.debug('Stopping %s', self.watchdog_thread.name)

    def get_data_from_buffer(self, filter_func=None, converter_func=None):
        '''Reads local data buffer and returns data and meta data list.

        Returns
        -------
        data : list
            List of data and meta data dicts.
        '''
        if self._is_running:
            raise RuntimeError('Readout thread running')
        if not self.fill_buffer:
            logging.warning('Data buffer is not activated')
        return [convert_data_iterable(data_iterable, filter_func=filter_func, converter_func=converter_func) for data_iterable in self._data_buffer]

    def get_raw_data_from_buffer(self, filter_func=None, converter_func=None):
        '''Reads local data buffer and returns raw data array.

        Returns
        -------
        data : np.array
            An array containing data words from the local data buffer.
        '''
        if self._is_running:
            raise RuntimeError('Readout thread running')
        if not self.fill_buffer:
            logging.warning('Data buffer is not activated')
        return [convert_data_array(data_array_from_data_iterable(data_iterable), filter_func=filter_func, converter_func=converter_func) for data_iterable in self._data_buffer]

    def read_raw_data_from_fifo(self, fifo, filter_func=None, converter_func=None):
        '''Reads FIFO data and returns raw data array.

        Returns
        -------
        data : np.array
            An array containing FIFO data words.
        '''
        return convert_data_array(self.dut[fifo].get_data(), filter_func=filter_func, converter_func=converter_func)

    def update_timestamp(self, fifo):
        curr_time = get_float_time()
        last_time = self.timestamp[fifo]
        if last_time is None:
            last_time = curr_time
        self.timestamp[fifo] = curr_time
        return last_time, curr_time

    def get_fifo_size(self, fifo):
        return self.dut[fifo]['FIFO_SIZE']

    def reset_rx(self, m26_channels=None):
        logging.info('Resetting RX')
        if m26_channels is None:
            m26_channels = [rx.name for rx in self.dut.get_modules('m26_rx')]
        for m26_rx_name in m26_channels:
            self.dut[m26_rx_name].RESET

    def reset_fifo(self, fifos):
        if isinstance(fifos, basestring):
            fifos = [fifos]
        for fifo in fifos:
            fifo_size = self.dut[fifo]['FIFO_SIZE']
            logging.info('Resetting %s: size = %i', fifo, fifo_size)
            self.dut[fifo]['RESET']
            # sleep for a while, if it is a hardware FIFO
            if not isinstance(self.dut[fifo], (sitcp_fifo.sitcp_fifo,)):
                sleep(0.2)
            fifo_size = self.dut[fifo]['FIFO_SIZE']
            if fifo_size != 0:
                logging.warning('%s not empty after reset: size = %i', fifo, fifo_size)

    def get_m26_rx_enable_status(self, channels=None):
        if channels is None:
            return map(lambda channel: True if channel.EN else False, self.dut.get_modules('m26_rx'))
        else:
            return map(lambda channel: True if self.dut[channel].EN else False, channels)

    def get_m26_rx_fifo_discard_count(self, channels=None):
        if channels is None:
            return map(lambda channel: channel.LOST_COUNT, self.dut.get_modules('m26_rx'))
        else:
            return map(lambda channel: self.dut[channel].LOST_COUNT, channels)


def data_array_from_data_iterable(data_iterable):
    '''Convert data iterable to raw data numpy array.

    Parameters
    ----------
    data_iterable : iterable
        Iterable where each element is a tuple with following content: (raw data, timestamp_start, timestamp_stop, status).

    Returns
    -------
    data_array : numpy.array
        concatenated data array
    '''
    try:
        data_array = np.concatenate([item[0] for item in data_iterable])
    except ValueError:  # length is 0
        data_array = np.empty(0, dtype=np.uint32)
    return data_array


def convert_data_iterable(data_iterable, filter_func=None, converter_func=None):  # TODO: add concatenate parameter
    '''Convert raw data in data iterable.

    Parameters
    ----------
    data_iterable : iterable
        Iterable where each element is a tuple with following content: (raw data, timestamp_start, timestamp_stop, status).
    filter_func : function
        Function that takes array and returns true or false for each item in array.
    converter_func : function
        Function that takes array and returns an array or tuple of arrays.

    Returns
    -------
    data_list : list
        Data list of the form [(converted data, timestamp_start, timestamp_stop, status), (...), ...]
    '''
    data_list = []
    for item in data_iterable:
        data_list.append((convert_data_array(item[0], filter_func=filter_func, converter_func=converter_func), item[1], item[2], item[3]))
    return data_list


def convert_data_array(array, filter_func=None, converter_func=None):  # TODO: add copy parameter, otherwise in-place
    '''Filter and convert raw data numpy array (numpy.ndarray).

    Parameters
    ----------
    array : numpy.array
        Raw data array.
    filter_func : function
        Function that takes array and returns true or false for each item in array.
    converter_func : function
        Function that takes array and returns an array or tuple of arrays.

    Returns
    -------
    data_array : numpy.array
        Data numpy array of specified dimension (converter_func) and content (filter_func)
    '''
#     if filter_func != None:
#         if not hasattr(filter_func, '__call__'):
#             raise ValueError('Filter is not callable')
    if filter_func:
        array = array[filter_func(array)]
#     if converter_func != None:
#         if not hasattr(converter_func, '__call__'):
#             raise ValueError('Converter is not callable')
    if converter_func:
        array = converter_func(array)
    return array


def is_trigger_word(value):
    return np.equal(np.bitwise_and(value, 0x80000000), 0x80000000)


def is_m26_word(value):
    ''' Check for Mimosa26 data words.

    Note: the Mimosa26 header is set in the firmware.
    '''
    return np.equal(np.bitwise_and(value, 0xFF000000), 0x20000000)  # header: 0x20


def get_m26_ids(array):
    ''' Check for and return different Mimosa26 identifiers.

    Parameters
    ----------
    array : numpy.array
        Raw data array.

    Returns
    -------
    Mimosa26 identifiers in data stream.
    '''
    return np.unique(np.right_shift(np.bitwise_and(array, 0x00F00000), 20))
