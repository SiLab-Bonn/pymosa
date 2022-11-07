#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import logging
import os
import threading
import time

from mock import patch

import pytest
import tables as tb
import numpy as np
import matplotlib
matplotlib.use('Agg')  # noqa: E402 Allow headless plotting

import pymosa  # noqa: E731 E402
from pymosa import online as oa  # noqa: E402
from pymosa.tests import utils  # noqa: E40


@pytest.fixture()
def data_folder():
    pymosa_path = os.path.dirname(pymosa.__file__)
    print(os.path.abspath(os.path.join(pymosa_path, 'tests')))
    return os.path.abspath(os.path.join(pymosa_path, 'tests'))


@pytest.fixture()
def ana_log_messages():
    ana_logger = logging.getLogger('OnlineAnalysis')
    _ana_log_handler = utils.MockLoggingHandler(level='DEBUG')
    ana_logger.addHandler(_ana_log_handler)
    ana_log_messages = _ana_log_handler.messages
    yield ana_log_messages
    ana_logger.removeHandler(_ana_log_handler)  # cleanup


@pytest.fixture()
def occ_hist_oa():
    h = oa.OccupancyHistogramming()
    yield h
    h.close()
    del h


def get_raw_data(raw_data_file):
    ''' Yield data of one readout

        Delay return if replay is too fast
    '''
    with tb.open_file(raw_data_file, mode="r") as in_file_h5:
        meta_data = in_file_h5.root.meta_data[:]
        raw_data = in_file_h5.root.raw_data
        n_readouts = meta_data.shape[0]

        for i in range(n_readouts):
            # Raw data indeces of readout
            i_start = meta_data['index_start'][i]
            i_stop = meta_data['index_stop'][i]

            yield raw_data[i_start:i_stop]


def test_occupancy_histogramming(data_folder, occ_hist_oa):
    ''' Test online occupancy histogramming '''

    raw_data_file = os.path.join(data_folder, 'anemone_raw_data.h5')
    raw_data_file_result = os.path.join(data_folder, 'anemone_raw_data_interpreted_result.h5')
    for words in get_raw_data(raw_data_file):
        occ_hist_oa.add(words)

    # FIXME: Bad practice, use Queue wait or timeout below
    time.sleep(5.0)

    occ_hist = occ_hist_oa.get()

    with tb.open_file(raw_data_file_result) as in_file:
        for i in range(6):
            occ_hist_exptected = in_file.get_node(in_file.root, 'HistOcc_plane%d' % (i + 1))
            assert(np.array_equal(occ_hist_exptected[:, :], occ_hist[:, :, i]))


# def test_occupancy_histogramming_errors(data_folder, occ_hist_oa, ana_log_messages):
#     # Check error message when requesting histogram before analysis finished

#     def add_data():
#         for words in get_raw_data(raw_data_file):
#             for _ in range(100):
#                 occ_hist_oa.add(words)

#     raw_data_file = os.path.join(data_folder, 'anemone_raw_data.h5')
#     occ_hist_oa.reset()
#     thread = threading.Thread(target=add_data)
#     thread.start()
#     time.sleep(0.5)  # wait for first data to be added to queue
#     occ_hist_oa.get(wait=False)
#     thread.join()
#     # Check that warning was given
#     assert('Getting histogram while analyzing data' in ana_log_messages['warning'])


if __name__ == '__main__':
    import pytest
    pytest.main(['-s', __file__])
