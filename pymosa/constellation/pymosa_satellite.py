from constellation.core.configuration import Configuration
from constellation.core.satellite import Satellite
import time
from constellation.core.cmdp import MetricsType
from constellation.core.fsm import SatelliteState
from constellation.core.monitoring import schedule_metric
import os
import yaml
import pymosa
from pymosa.m26 import m26
import logging
from pymosa.m26_raw_data import save_configuration_dict
from time import sleep, strftime, time
from tqdm import tqdm
from typing import Any


class Pymosa(Satellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_initializing(self, config: Configuration) -> str:
        # Open Mimosa26 std. configuration
        pymosa_path = os.path.dirname(pymosa.__file__)
        with open(os.path.join(pymosa_path, 'm26_configuration.yaml'), 'r') as f:
            self.yaml_config = yaml.safe_load(f)
        self._load_config(config)
        # Create telescope object and load hardware configuration
        self.telescope = m26(conf=None)  # None: use default hardware configuration
        return "init done"

    def do_launching(self) -> str:
        # Initialize telescope hardware and set up parameters
        self.telescope.init(init_conf=self.yaml_config)
        return "launching done"

    def do_run(self, payload=None) -> str:
        self._pre_run()
        with self.telescope.access_file():
            save_configuration_dict(self.telescope.raw_data_file.h5_file, 'configuration', self.telescope.telescope_conf)
            with self.telescope.readout(enabled_m26_channels=self.telescope.enabled_m26_channels):
                got_data = False
                start = time()
                while not self.stop_scan and not self._state_thread_evt.is_set():
                    sleep(1.0)
                    if not got_data:
                        if self.telescope.m26_readout.data_words_per_second()[0] > 0:
                            got_data = True
                            logging.info('Taking data...')
                            if self.telescope.max_triggers:
                                self.pbar = tqdm(total=self.telescope.max_triggers, ncols=80)
                            else:
                                self.pbar = tqdm(total=self.telescope.scan_timeout, ncols=80)
                    else:
                        triggers = self.telescope.dut['TLU']['TRIGGER_COUNTER']
                        try:
                            if self.telescope.max_triggers:
                                self.pbar.update(triggers - self.pbar.n)
                            else:
                                self.pbar.update(time() - start - self.pbar.n)
                        except ValueError:
                            pass
                        if self.telescope.max_triggers and triggers >= self.telescope.max_triggers:
                            self.stop_scan = True
                            self.pbar.close()
                            logging.info('Trigger limit was reached: %i' % self.telescope.max_triggers)
        logging.info('Total amount of triggers collected: %d', self.telescope.dut['TLU']['TRIGGER_COUNTER'])
        self.logger.removeHandler(self.fh)
        logging.info('Data Output Filename: %s', self.telescope.run_filename + '.h5')
        self.telescope.analyze()
        return "running done"

    def do_landing(self) -> str:
        # Close the resources
        self.telescope.close()
        return "landing done"

    def _pre_run(self) -> None:
        self.stop_scan = False
        # signal.signal(signal.SIGINT, self.telescope._signal_handler)
        logging.info('Press Ctrl-C to stop run')

        # check for filename that is not in use
        while True:
            if not self.telescope.output_filename and self.telescope.run_number:
                filename = 'run_' + str(self.telescope.run_number) + '_' + self.telescope.run_id

            else:
                if self.telescope.output_filename:
                    filename = self.telescope.output_filename
                else:
                    filename = strftime("%Y%m%d-%H%M%S") + '_' + self.telescope.run_id
            if filename in [os.path.splitext(f)[0] for f in os.listdir(self.telescope.working_dir) if os.path.isfile(os.path.join(self.telescope.working_dir, f))]:
                if not self.telescope.output_filename and self.telescope.run_number:
                    self.telescope.run_number += 1  # increase run number and try again
                    continue
                else:
                    raise IOError("Filename %s already exists." % filename)
            else:
                self.telescope.run_filename = os.path.join(self.telescope.working_dir, filename)
                break

        # set up logger
        self.fh = logging.FileHandler(self.telescope.run_filename + '.log')
        self.fh.setLevel(logging.DEBUG)
        FORMAT = '%(asctime)s [%(name)-17s] - %(levelname)-7s %(message)s'
        self.fh.setFormatter(logging.Formatter(FORMAT))
        self.logger = logging.getLogger()
        self.logger.addHandler(self.fh)
        self.telescope.dut['TLU']['TRIGGER_COUNTER'] = 0

    def _load_config(self, config: Configuration) -> None:
        config.set_default(key='scan_timeout', value=None)
        config.set_default(key='run_number', value=None)
        config.set_default(key='output_folder', value=None)
        config.set_default(key='m26_configuration_file', value=None)
        config.set_default(key='m26_jtag_configuration', value=True)
        config.set_default(key='enabled_m26_channels', value=None)

        self.yaml_config['no_data_timeout'] = config.get(key='no_data_timeout')
        self.yaml_config['send_data'] = config.get(key='send_data')
        self.yaml_config['max_triggers'] = config.get(key='max_triggers')
        self.yaml_config['scan_timeout'] = config.get(key='scan_timeout')
        self.yaml_config['run_number'] = config.get(key='run_number')
        self.yaml_config['output_folder'] = config.get(key='output_folder')
        self.yaml_config['m26_configuration_file'] = config.get(key='m26_configuration_file')
        self.yaml_config['m26_jtag_configuration'] = config.get(key='m26_jtag_configuration')
        self.yaml_config['enabled_m26_channels'] = config.get(key='enabled_m26_channels')

    @schedule_metric("", MetricsType.LAST_VALUE, 1)
    def trigger_number(self) -> int | None:
        if self.fsm.current_state_value == SatelliteState.RUN:
            return self.telescope.dut['TLU']['TRIGGER_COUNTER']
        else:
            return None
