import logging
import glob
from threading import RLock
import os.path
from os import remove

import numpy as np
import tables as tb
import zmq


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


def open_raw_data_file(filename, mode="w", title="", scan_parameters=None, socket_address=None):
    '''Mimics pytables.open_file() and stores the configuration and run configuration

    Returns:
    RawDataFile Object

    Examples:
    with open_raw_data_file(filename = self.scan_data_filename, title=self.run_id, scan_parameters=[scan_parameter]) as raw_data_file:
        # do something here
        raw_data_file.append(self.readout.data, scan_parameters={scan_parameter:scan_parameter_value})
    '''
    return M26RawDataFile(filename=filename, mode=mode, title=title, scan_parameters=scan_parameters, socket_address=socket_address)


# from pyBAR
class M26RawDataFile(object):

    max_table_size = 2**63 - 1000000  # limit file size, just in case

    '''Raw data file object. Saving data queue to HDF5 file.
    '''

    def __init__(self, filename, mode="w", title='', scan_parameters=None, socket_address=None):  # mode="r+" to append data, raw_data_file_h5 must exist, "w" to overwrite raw_data_file_h5, "a" to append data, if raw_data_file_h5 does not exist it is created):
        self.lock = RLock()
        if os.path.splitext(filename)[1].strip().lower() != '.h5':
            self.base_filename = filename
        else:
            self.base_filename = os.path.splitext(filename)[0]
        if isinstance(scan_parameters, dict):
            self.scan_parameters = scan_parameters
        elif isinstance(scan_parameters, (list, tuple)):
            self.scan_parameters = dict.fromkeys(scan_parameters)
        else:
            self.scan_parameters = {}
        self.raw_data_earray = None
        self.meta_data_table = None
        self.scan_param_table = None
        self.h5_file = None

        if socket_address:
            context = zmq.Context.instance()

        if socket_address and context:
            logging.info('Creating socket connection to server %s', socket_address)
            self.socket = context.socket(zmq.PUB)  # publisher socket
            self.socket.bind(socket_address)
        else:
            self.socket = None

        if mode and mode[0] == 'w':
            h5_files = glob.glob(os.path.splitext(filename)[0] + '*.h5')
            if h5_files:
                logging.info('Removing following file(s): %s', ', '.join(h5_files))
            for h5_file in h5_files:
                remove(h5_file)
        # list of filenames and index
        self.curr_filename = self.base_filename
        self.filenames = {self.curr_filename: 0}
        self.open(self.curr_filename, mode, title)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close(close_socket=True)
        return False  # do not hide exceptions

    def open(self, filename, mode='w', title=''):
        if os.path.splitext(filename)[1].strip().lower() != '.h5':
            filename = os.path.splitext(filename)[0] + '.h5'
        if os.path.isfile(filename) and mode in ('r+', 'a'):
            logging.info('Opening existing raw data file: %s', filename)
        else:
            logging.info('Opening new raw data file: %s', filename)
        if self.socket:
            send_meta_data(self.socket, None, name='Reset')  # send reset to indicate a new scan
            send_meta_data(self.socket, os.path.basename(filename), name='Filename')

        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        self.h5_file = tb.open_file(filename, mode=mode, title=title if title else filename)
        try:
            self.raw_data_earray = self.h5_file.create_earray(self.h5_file.root, name='raw_data', atom=tb.UIntAtom(), shape=(0,), title='raw_data', filters=filter_raw_data)  # expectedrows = ???
        except tb.exceptions.NodeError:
            self.raw_data_earray = self.h5_file.get_node(self.h5_file.root, name='raw_data')
        try:
            self.meta_data_table = self.h5_file.create_table(self.h5_file.root, name='meta_data', description=MetaTable, title='meta_data', filters=filter_tables)
        except tb.exceptions.NodeError:
            self.meta_data_table = self.h5_file.get_node(self.h5_file.root, name='meta_data')
        if self.scan_parameters:
            try:
                scan_param_descr = generate_scan_parameter_description(self.scan_parameters)
                self.scan_param_table = self.h5_file.create_table(self.h5_file.root, name='scan_parameters', description=scan_param_descr, title='scan_parameters', filters=filter_tables)
            except tb.exceptions.NodeError:
                self.scan_param_table = self.h5_file.get_node(self.h5_file.root, name='scan_parameters')

    def close(self, close_socket=True):
        with self.lock:
            self.flush()
            logging.info('Closing raw data file: %s', self.h5_file.filename)
            self.h5_file.close()
            self.h5_file = None
        if self.socket and close_socket:
            logging.info('Closing socket connection')
            self.socket.close()  # close here, do not wait for garbage collector
            self.socket = None

    def append_item(self, data_tuple, scan_parameters=None, new_file=False, flush=True):
        with self.lock:
            if scan_parameters:
                # check for not existing keys
                diff = set(scan_parameters).difference(set(self.scan_parameters))
                if diff:
                    raise ValueError('Unknown scan parameter(s): %s' % ', '.join(diff))
                # parameters that have changed
                diff = [name for name in scan_parameters.keys() if scan_parameters[name] != self.scan_parameters[name]]
                self.scan_parameters.update(scan_parameters)
                if (new_file is True and diff) or (isinstance(new_file, (list, tuple)) and len([name for name in diff if name in new_file]) != 0):
                    self.curr_filename = os.path.splitext(self.base_filename)[0].strip() + '_' + '_'.join([str(item) for item in reduce(lambda x, y: x + y, [(key, value) for key, value in scan_parameters.items() if (new_file is True or (isinstance(new_file, (list, tuple)) and key in new_file))])])
                    index = self.filenames.get(self.curr_filename, 0)
                    if index == 0:
                        filename = self.curr_filename + '.h5'
                        self.filenames[self.curr_filename] = 0  # add to dict
                    else:
                        filename = self.curr_filename + '_' + str(index) + '.h5'
                    # copy nodes to new file
                    nodes = self.h5_file.list_nodes('/', classname='Group')
                    with tb.open_file(filename, mode='a', title=filename) as h5_file:  # append, since file can already exists when scan parameters are jumping back and forth
                        for node in nodes:
                            self.h5_file.copy_node(node, h5_file.root, overwrite=True, recursive=True)
                    self.close(close_socket=False)
                    self.open(filename, 'a', filename)
            total_words = self.raw_data_earray.nrows
            raw_data = data_tuple[0]
            len_raw_data = raw_data.shape[0]
            if total_words + len_raw_data > self.max_table_size:
                index = self.filenames.get(self.curr_filename, 0) + 1  # reached file size limit, increase index by one
                self.filenames[self.curr_filename] = index  # update dict
                filename = self.curr_filename + '_' + str(index) + '.h5'
                # copy nodes to new file
                nodes = self.h5_file.list_nodes('/', classname='Group')
                with tb.open_file(filename, mode='a', title=filename) as h5_file:  # append, since file can already exists when scan parameters are jumping back and forth
                    for node in nodes:
                        self.h5_file.copy_node(node, h5_file.root, overwrite=True, recursive=True)
                self.close(close_socket=False)
                self.open(filename, 'a', filename)
                total_words = self.raw_data_earray.nrows  # in case of re-opening existing file
            self.raw_data_earray.append(raw_data)
            self.meta_data_table.row['timestamp_start'] = data_tuple[1]
            self.meta_data_table.row['timestamp_stop'] = data_tuple[2]
            self.meta_data_table.row['error'] = data_tuple[3]
            self.meta_data_table.row['data_length'] = len_raw_data
            self.meta_data_table.row['index_start'] = total_words
            total_words += len_raw_data
            self.meta_data_table.row['index_stop'] = total_words
            self.meta_data_table.row.append()
            if self.scan_parameters:
                for key in self.scan_parameters:
                    self.scan_param_table.row[key] = self.scan_parameters[key]
                self.scan_param_table.row.append()
            if flush:
                self.flush()
            if self.socket:
                send_data(self.socket, data_tuple, self.scan_parameters)

    def append(self, data_iterable, scan_parameters=None, new_file=False, flush=True):
        with self.lock:
            for data_tuple in data_iterable:
                self.append_item(data_tuple=data_tuple, scan_parameters=scan_parameters, new_file=new_file, flush=False)
            if flush:
                self.flush()

    def flush(self):
        with self.lock:
            self.raw_data_earray.flush()
            self.meta_data_table.flush()
            if self.scan_parameters:
                self.scan_param_table.flush()

    @classmethod
    def from_raw_data_file(cls, input_file, output_filename, mode="a"):
        if os.path.splitext(output_filename)[1].strip().lower() != '.h5':
            output_filename = os.path.splitext(output_filename)[0] + '.h5'
        nodes = input_file.list_nodes('/', classname='Group')
        with tb.open_file(output_filename, mode=mode, title=output_filename) as h5_file:  # append, since file can already exists when scan parameters are jumping back and forth
            for node in nodes:
                input_file.copy_node(node, h5_file.root, overwrite=True, recursive=True)
        try:
            scan_parameters = input_file.root.scan_parameters.fields
        except tb.exceptions.NoSuchNodeError:
            scan_parameters = {}
        return cls(output_filename, mode="a", scan_parameters=scan_parameters)


def save_raw_data_from_data_queue(data_queue, filename, mode='a', title='', scan_parameters=None):  # mode="r+" to append data, raw_data_file_h5 must exist, "w" to overwrite raw_data_file_h5, "a" to append data, if raw_data_file_h5 does not exist it is created
    '''Writing raw data file from data queue

    If you need to write raw data once in a while this function may make it easy for you.
    '''
    if not scan_parameters:
        scan_parameters = {}
    with open_raw_data_file(filename, mode='a', title='', scan_parameters=list(dict.iterkeys(scan_parameters))) as raw_data_file:
        raw_data_file.append(data_queue, scan_parameters=scan_parameters)


class NameValue(tb.IsDescription):
    name = tb.StringCol(256, pos=0)
    value = tb.StringCol(4 * 1024, pos=0)


def save_configuration_dict(h5_file, configuation_name, configuration, **kwargs):
    '''Stores any configuration dictionary to HDF5 file.

    Parameters
    ----------
    h5_file : string, file
        Filename of the HDF5 configuration file or file object.
    configuation_name : str
        Configuration name. Will be used for table name.
    configuration : dict
        Configuration dictionary.
    '''
    def save_conf():
        try:
            h5_file.remove_node(h5_file.root.configuration, name=configuation_name)
        except tb.NodeError:
            pass
        try:
            configuration_group = h5_file.create_group(h5_file.root, "configuration")
        except tb.NodeError:
            configuration_group = h5_file.root.configuration

        scan_param_table = h5_file.create_table(configuration_group, name=configuation_name, description=NameValue, title=configuation_name)
        row_scan_param = scan_param_table.row
        for key, value in dict.items(configuration):
            row_scan_param['name'] = key
            row_scan_param['value'] = str(value)
            row_scan_param.append()
        scan_param_table.flush()

    if isinstance(h5_file, tb.file.File):
        save_conf()
    else:
        if os.path.splitext(h5_file)[1].strip().lower() != ".h5":
            h5_file = os.path.splitext(h5_file)[0] + ".h5"
        with tb.open_file(h5_file, mode="a", title='', **kwargs) as h5_file:
            save_conf()


class MetaTable(tb.IsDescription):
    index_start = tb.UInt32Col(pos=0)
    index_stop = tb.UInt32Col(pos=1)
    data_length = tb.UInt32Col(pos=2)
    # https://github.com/PyTables/PyTables/issues/230
#    timestamp = tb.Time64Col(pos=3)
    timestamp_start = tb.Float64Col(pos=3)
    timestamp_stop = tb.Float64Col(pos=4)
    error = tb.UInt32Col(pos=5)


def generate_scan_parameter_description(scan_parameters):
    '''Generate scan parameter dictionary. This is the only way to dynamically create table with dictionary, cannot be done with tables.IsDescription

    Parameters
    ----------
    scan_parameters : list, tuple
        List of scan parameters names (strings).

    Returns
    -------
    table_description : dict
        Table description.

    Usage
    -----
    pytables.createTable(self.raw_data_file_h5.root, name = 'scan_parameters', description = generate_scan_parameter_description(['PlsrDAC']), title = 'scan_parameters', filters = filter_tables)
    '''
    table_description = np.dtype([(key, tb.Int32Col(pos=idx)) for idx, key in enumerate(scan_parameters)])
    return table_description
