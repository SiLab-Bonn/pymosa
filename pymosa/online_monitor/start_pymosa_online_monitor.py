#!/usr/bin/env python
''' Entry point to simplify the usage from command line for
the online_monitor with pymosa plugins. Not really needed
start_online_monitor config.yaml would also work...
'''
import logging
import sys
import os
import subprocess

import psutil
from PyQt5 import Qt

from online_monitor.OnlineMonitor import OnlineMonitorApplication
from online_monitor.utils import utils


def kill(proc):
    ''' Kill process by id, including subprocesses.

        Works for Linux and Windows
    '''
    process = psutil.Process(proc.pid)
    for child_proc in process.children(recursive=True):
        child_proc.kill()
    process.kill()


def run_script_in_shell(script, arguments, command=None):
    if os.name == 'nt':
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        creationflags = 0
    return subprocess.Popen("%s %s %s" % ('python' if not command else command,
                                          script, arguments), shell=True,
                            creationflags=creationflags)


def main():
    if sys.argv[1:]:
        args = utils.parse_arguments()
    else:  # no config yaml provided -> start online monitor with std. settings
        class Dummy(object):
            def __init__(self):
                folder = os.path.dirname(os.path.realpath(__file__))
                self.config_file = os.path.join(folder, r'configuration.yaml')
                self.log = 'INFO'
        args = Dummy()
        logging.info('No configuration file provided! Use std. settings!')

    utils.setup_logging(args.log)

    # Start the producer
    producer_manager_process = run_script_in_shell('',
                                                   args.config_file,
                                                   'start_producer_sim')
    # Start the converter
    converter_manager_process = run_script_in_shell('',
                                                    args.config_file,
                                                    'start_converter')

# Helper function to run code after OnlineMonitor Application exit
    def appExec():
        app.exec_()
        # Stop other processes
        try:
            kill(converter_manager_process)
            kill(producer_manager_process)
        # If the process was never started it cannot be killed
        except psutil.NoSuchProcess:
            pass
    # Start the online monitor
    app = Qt.QApplication(sys.argv)
    win = OnlineMonitorApplication(args.config_file)
    win.show()
    sys.exit(appExec())


if __name__ == '__main__':
    main()
