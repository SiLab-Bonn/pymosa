from constellation.core.configuration import Configuration
from constellation.core.satellite import Satellite
import time
from constellation.core.commandmanager import cscp_requestable
from constellation.core.cscp import CSCPMessage
from constellation.core.cmdp import MetricsType
import os
import yaml
import pymosa
from pymosa.m26 import m26
import logging
from pymosa.m26_raw_data import save_configuration_dict
from time import sleep, strftime, time
from tqdm import tqdm


class Pymosa(Satellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_initializing(self, config: Configuration) -> None:
        # Open Mimosa26 std. configuration
        pymosa_path = os.path.dirname(pymosa.__file__)
        with open(os.path.join(pymosa_path, 'm26_configuration.yaml'), 'r') as f:
            self.yaml_config = yaml.safe_load(f)
        # overwrite some configuration variables with toml config
        configuration = config.get_dict()
        if configuration["run_number"] == "None":
            configuration["run_number"] = None
        if configuration["output_folder"] == "None":
            configuration["output_folder"] = None
        if configuration["m26_configuration_file"] == "None":
            configuration["m26_configuration_file"] = None
        if configuration["enabled_m26_channels"] == "None":
            configuration["enabled_m26_channels"] = None
        for key in configuration.keys():
            self.yaml_config[key] = configuration[key]
        # Create telescope object and load hardware configuration
        self.telescope = m26(conf=None)  # None: use default hardware configuration
        return "init done"

    def do_launching(self):
        # Initialize telescope hardware and set up parameters
        self.telescope.init(init_conf=self.yaml_config)
        return "launching done"

    def do_run(self, payload=None) -> None:
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

    def do_landing(self):
        # Close the resources
        self.telescope.close()
        return "landing done"

    def _pre_run(self):
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


