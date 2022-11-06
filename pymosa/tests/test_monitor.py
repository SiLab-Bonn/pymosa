''' Script to check the pymosa modules for the online monitor

    Simulation producer, interpreter converter and receiver.
'''

import os
import sys
import unittest
import yaml
import time
import psutil
from PyQt5.QtWidgets import QApplication

from online_monitor import OnlineMonitor

import pymosa
from pymosa.online_monitor import start_pymosa_online_monitor

pymosa_path = os.path.dirname(pymosa.__file__)
data_folder = os.path.abspath(os.path.join(pymosa_path, '..', 'data'))


# Create online monitor yaml config with pymosa monitor entities
def create_config_yaml():
    conf = {}
    # Add producer
    devices = {}
    devices['PYMOSA_Producer'] = {'backend': 'tcp://127.0.0.1:8500',
                                  'kind': 'pymosa_producer_sim',
                                  'delay': 0.1,
                                  'data_file': os.path.join(data_folder, 'telescope_data.h5')
                                  }
    conf['producer_sim'] = devices
    # Add converter
    devices = {}
    devices['PYMOSA_Interpreter'] = {'kind': 'pymosa_converter',
                                     'frontend': 'tcp://127.0.0.1:8500',
                                     'backend': 'tcp://127.0.0.1:8700'
                                     }
    devices['PYMOSA_Histogrammer'] = {'kind': 'pymosa_histogrammer',
                                      'frontend': 'tcp://127.0.0.1:8700',
                                      'backend': 'tcp://127.0.0.1:8800'
                                      }
    devices['HIT_Correlator'] = {'kind': 'hit_correlator_converter',
                                 'frontend': 'tcp://127.0.0.1:8700',
                                 'backend': 'tcp://127.0.0.1:8900',
                                 'duts': {'M26': {'n_columns': 1152, 'n_rows': 576, 'column_size': 18.4, 'row_size': 18.4}},
                                 'correlation_planes': [{'name': 'Mimosa26 Plane 1', 'dut_type': 'M26', 'address': 'tcp://127.0.0.1:8700', 'id': 0},
                                                        {'name': 'Mimosa26 Plane 2', 'dut_type': 'M26', 'address': 'tcp://127.0.0.1:8700', 'id': 1}]
                                 }

    conf['converter'] = devices
    # Add receiver
    devices = {}
    devices['PYMOSA_Receiver'] = {'kind': 'pymosa_receiver',
                                  'frontend': 'tcp://127.0.0.1:8800'
                                  }
    devices['HIT_Correlator'] = {'kind': 'hit_correlator_receiver',
                                 'frontend': 'tcp://127.0.0.1:8900',
                                 'duts': {'M26': {'n_columns': 1152, 'n_rows': 576, 'column_size': 18.4, 'row_size': 18.4}},
                                 'correlation_planes': [{'name': 'Mimosa26 Plane 1', 'dut_type': 'M26'},
                                                        {'name': 'Mimosa26 Plane 2', 'dut_type': 'M26'}]
                                 }
    conf['receiver'] = devices
    return yaml.dump(conf, default_flow_style=False)


def get_python_processes():  # return the number of python processes
    n_python = 0
    for proc in psutil.process_iter():
        try:
            if 'python' in proc.name():
                n_python += 1
        except psutil.AccessDenied:
            pass
    return n_python


class TestOnlineMonitor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open('tmp_cfg.yml', 'w') as outfile:
            config_file = create_config_yaml()
            outfile.write(config_file)
        # Linux CIs run usually headless, thus virtual x server is needed for gui testing
        if os.getenv('CI', False):
            # raise unittest.SkipTest("CERN CI runner with Miniconda python docker has segfault in these tests.")
            from xvfbwrapper import Xvfb
            cls.vdisplay = Xvfb()
            cls.vdisplay.start()
        # Start the simulation producer to create some fake data
        cls.prod_sim_proc = start_pymosa_online_monitor.run_script_in_shell('', 'tmp_cfg.yml', 'start_producer_sim')
        # Start converter
        cls.conv_manager_proc = start_pymosa_online_monitor.run_script_in_shell('', 'tmp_cfg.yml', command='start_converter')
        # Create Gui
        time.sleep(2)
        cls.app = QApplication(sys.argv)
        cls.online_monitor = OnlineMonitor.OnlineMonitorApplication('tmp_cfg.yml')
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):  # Remove created files
        time.sleep(1)
        start_pymosa_online_monitor.kill(cls.prod_sim_proc)
        start_pymosa_online_monitor.kill(cls.conv_manager_proc)
        time.sleep(1)
        os.remove('tmp_cfg.yml')
        cls.online_monitor.close()
        time.sleep(1)

    def test_data_chain(self):
        ''' Checks for received data for the 2 receivers

            This effectively checks the full chain:
            producer --> converter --> receiver
        '''

        # Qt evsent loop does not run in tests, thus we have to trigger the
        # event queue manually
        self.app.processEvents()
        # Check all receivers present
        self.assertEqual(len(self.online_monitor.receivers), 2, 'Number of receivers wrong')
        self.app.processEvents()  # Clear event queue

        # Case 1: Activate status widget, no data should be received
        self.online_monitor.tab_widget.setCurrentIndex(0)
        self.app.processEvents()
        time.sleep(5)
        self.app.processEvents()
        time.sleep(5)
        # Data structure to check for no data since receiver widget
        # is not active
        data_recv_0 = []
        self.app.processEvents()
        for receiver in self.online_monitor.receivers:
            if receiver.name == 'PYMOSA_Receiver':
                # Check histogram for each plane
                for k in range(6):
                    data_recv_0.append(receiver.occupancy_images[k].getHistogram(bins=100, step=100))

        # Case 2: Activate DUT widget, receiver 1 should show data
        self.online_monitor.tab_widget.setCurrentIndex(2)  # Yaml dumps dict in alphabetical order.
        self.app.processEvents()
        time.sleep(5)
        self.app.processEvents()
        time.sleep(5)
        # Data structure to check for data since receiver widget
        # is active
        data_recv_1 = []
        for receiver in self.online_monitor.receivers:
            if receiver.name == 'PYMOSA_Receiver':
                # Check histogram for each plane
                for k in range(6):
                    data_recv_1.append(receiver.occupancy_images[k].getHistogram(bins=100, step=100))

        # Case 3: Activate correlator tab, receiver 2 should have no data since start button not pressed
        self.online_monitor.tab_widget.setCurrentIndex(1)  # Yaml dumps dict in alphabetical order.
        self.app.processEvents()
        time.sleep(5)
        self.app.processEvents()
        time.sleep(5)
        data_recv_2 = []
        for receiver in self.online_monitor.receivers:
            if receiver.name == 'HIT_Correlator':
                data_recv_2.append(receiver.occupancy_images_rows.getHistogram(bins=100, step=100))

        # Case 4: Activate correlator tab, receiver 2 should show data since start button is pressed
        self.online_monitor.tab_widget.setCurrentIndex(1)  # Yaml dumps dict in alphabetical order.
        self.app.processEvents()
        time.sleep(5)
        self.app.processEvents()
        time.sleep(5)
        data_recv_3 = []
        for receiver in self.online_monitor.receivers:
            if receiver.name == 'HIT_Correlator':
                receiver.send_command('combobox1 0')  # Select DUT
                self.app.processEvents()
                time.sleep(2)
                self.app.processEvents()
                time.sleep(2)
                receiver.send_command('combobox2 1')  # Select DUT
                self.app.processEvents()
                time.sleep(2)
                self.app.processEvents()
                time.sleep(2)
                receiver.send_command('START 0')  # send command in order to start correlation
                self.app.processEvents()
                time.sleep(2)
                self.app.processEvents()
                time.sleep(2)
                data_recv_3.append(receiver.occupancy_images_rows.getHistogram(bins=100, step=100))

        self.assertListEqual(data_recv_0, [(None, None), (None, None), (None, None), (None, None), (None, None), (None, None)])
        for k in range(6):
            self.assertTrue(data_recv_1[k][0] is not None)
        self.assertListEqual(data_recv_2, [(None, None)])
        self.assertTrue(data_recv_3[0][0] is not None)

    #  Test the UI
    def test_ui(self):
        # 2 receiver + status widget expected
        self.assertEqual(self.online_monitor.tab_widget.count(), 3, 'Number of tab widgets wrong')


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOnlineMonitor)
    unittest.TextTestRunner(verbosity=2).run(suite)
