import time

import numpy as np
from PyQt5 import Qt
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
import pyqtgraph.ptime as ptime
from pyqtgraph.dockarea import DockArea, Dock

from online_monitor.receiver.receiver import Receiver
from online_monitor.utils import utils


class PymosaMimosa26(Receiver):

    def setup_receiver(self):
        self.set_bidirectional_communication()  # We want to change converter settings

    def setup_widgets(self, parent, name):
        dock_area = DockArea()
        parent.addTab(dock_area, name)
        # Occupancy Docks
        self.occupancy_images = []
        self.event_status_plots = []
        # Plots with axis stored in here
        self.plots = []
        self.event_status_widgets = []
        poss = np.array([0.0, 0.01, 0.5, 1.0])
        color = np.array([[1.0, 1.0, 1.0, 1.0], [0.267004, 0.004874, 0.329415, 1.0], [0.127568, 0.566949, 0.550556, 1.0], [0.993248, 0.906157, 0.143936, 1.0]])  # Zero is white
        mapp = pg.ColorMap(poss, color)
        lutt = mapp.getLookupTable(0.0, 1.0, 100)

        self.occ_hist_sum = np.zeros(shape=(6,))
        for plane in range(3):  # Loop over 3 * 2 plot widgets
            # Dock left
            dock_occcupancy = Dock("Occupancy plane %d" % (2 * plane + 1), size=(100, 150))
            dock_event_status = Dock("Event status plane %d" % (2 * plane + 1), size=(100, 50))
            if plane > 0:
                dock_area.addDock(dock_occcupancy, 'bottom')
            else:
                dock_area.addDock(dock_occcupancy, 'left')
            dock_area.addDock(dock_event_status, 'right', dock_occcupancy)
            occupancy_graphics = pg.GraphicsLayoutWidget()  # Plot docks
            occupancy_graphics.show()
            view = occupancy_graphics.addViewBox()
            self.occupancy_images.append(pg.ImageItem(border='w'))
            view.addItem(self.occupancy_images[2 * plane])
            self.occupancy_images[2 * plane].setLookupTable(lutt, update=True)
            self.plots.append(pg.PlotWidget(viewBox=view, labels={'bottom': 'Column', 'left': 'Row'}, title='Occupancy Map, Sum: %i' % self.occ_hist_sum[2 * plane]))
            self.plots[2 * plane].addItem(self.occupancy_images[2 * plane])
            dock_occcupancy.addWidget(self.plots[2 * plane])

#             event_status_widget = pg.PlotWidget()
#             self.event_status_plots.append(event_status_widget.plot(np.linspace(-0.5, 15.5, 17), np.zeros((16)), stepMode=True))
#             event_status_widget.showGrid(y=True)
#             dock_event_status.addWidget(event_status_widget)

            self.event_status_widgets.append(pg.PlotWidget())
            self.event_status_plots.append(self.event_status_widgets[2 * plane].plot(np.linspace(-0.5, 15.5, 17), np.zeros((16)), stepMode=True))
            self.event_status_widgets[2 * plane].showGrid(y=True)
            dock_event_status.addWidget(self.event_status_widgets[2 * plane])

            # Dock right
            dock_occcupancy_2 = Dock("Occupancy plane %d" % (2 * plane + 2), size=(100, 150))
            dock_event_status_2 = Dock("Event status plane %d" % (2 * plane + 2), size=(100, 50))
            dock_area.addDock(dock_occcupancy_2, 'right', dock_event_status)
            dock_area.addDock(dock_event_status_2, 'right', dock_occcupancy_2)
            occupancy_graphics = pg.GraphicsLayoutWidget()  # Plot docks
            occupancy_graphics.show()
            view = occupancy_graphics.addViewBox()
            self.occupancy_images.append(pg.ImageItem(border='w'))
            view.addItem(self.occupancy_images[2 * plane + 1])
            self.occupancy_images[2 * plane + 1].setLookupTable(lutt, update=True)
            self.plots.append(pg.PlotWidget(viewBox=view, labels={'bottom': 'Column', 'left': 'Row'}, title='Occupancy Map, Sum: %i' % self.occ_hist_sum[2 * plane + 1]))
            self.plots[2 * plane + 1].addItem(self.occupancy_images[2 * plane + 1])
            dock_occcupancy_2.addWidget(self.plots[2 * plane + 1])

            self.event_status_widgets.append(pg.PlotWidget())
            self.event_status_plots.append(self.event_status_widgets[2 * plane + 1].plot(np.linspace(-0.5, 15.5, 17), np.zeros((16)), stepMode=True))
            self.event_status_widgets[2 * plane + 1].showGrid(y=True)
            # self.event_status_widgets[2 * plane + 1].setLogMode(y=True)
            dock_event_status_2.addWidget(self.event_status_widgets[2 * plane + 1])

        dock_status = Dock("Status", size=(800, 40))
        dock_area.addDock(dock_status, 'top')

        # Status dock on top
        cw = QtGui.QWidget()
        cw.setStyleSheet("QWidget {background-color:white}")
        layout = QtGui.QGridLayout()
        cw.setLayout(layout)
        self.rate_label = QtGui.QLabel("Readout Rate\n0 Hz")
        self.hit_rate_label = QtGui.QLabel("Hit Rate\n0 Hz")
        self.event_rate_label = QtGui.QLabel("Event Rate\n0 Hz")
        self.timestamp_label = QtGui.QLabel("Data Timestamp\n")
        self.plot_delay_label = QtGui.QLabel("Plot Delay\n")
        self.scan_parameter_label = QtGui.QLabel("Scan Parameters\n")
        self.spin_box = Qt.QSpinBox(value=0)
        self.spin_box.setMaximum(1000000)
        self.spin_box.setSuffix(" Readouts")
        self.reset_button = QtGui.QPushButton('Reset')
        self.noisy_checkbox = QtGui.QCheckBox('Mask noisy pixels')
        self.convert_checkbox = QtGui.QCheckBox('Axes in ' + u'\u03BC' + 'm')
        layout.addWidget(self.timestamp_label, 0, 0, 0, 1)
        layout.addWidget(self.plot_delay_label, 0, 1, 0, 1)
        layout.addWidget(self.rate_label, 0, 2, 0, 1)
        layout.addWidget(self.hit_rate_label, 0, 3, 0, 1)
        layout.addWidget(self.event_rate_label, 0, 4, 0, 1)
        layout.addWidget(self.scan_parameter_label, 0, 5, 0, 1)
        layout.addWidget(self.spin_box, 0, 6, 0, 1)
        layout.addWidget(self.noisy_checkbox, 0, 7, 0, 1)
        layout.addWidget(self.convert_checkbox, 0, 8, 0, 1)
        layout.addWidget(self.reset_button, 0, 9, 0, 1)
        dock_status.addWidget(cw)

        # Connect widgets
        self.reset_button.clicked.connect(lambda: self.send_command('RESET'))
        self.spin_box.valueChanged.connect(lambda value: self.send_command(str(value)))
        self.noisy_checkbox.stateChanged.connect(lambda value: self.send_command('MASK %d' % value))

        # Change axis scaling
        def scale_axes(scale_state):
            for plot in self.plots:
                if scale_state == 0:
                    plot.getAxis('bottom').setScale(1.0)
                    plot.getAxis('left').setScale(1.0)
                    plot.getAxis('bottom').setLabel('Columns')
                    plot.getAxis('left').setLabel('Rows')
                elif scale_state == 2:
                    plot.getAxis('bottom').setScale(18.4)
                    plot.getAxis('left').setScale(18.4)
                    plot.getAxis('bottom').setLabel('Columns / ' + u'\u03BC' + 'm')
                    plot.getAxis('left').setLabel('Rows / ' + u'\u03BC' + 'm')

        self.convert_checkbox.stateChanged.connect(lambda value: scale_axes(value))
        self.plot_delay = 0

    def deserialize_data(self, data):

        datar, meta = utils.simple_dec(data)
        if 'occupancies' in meta:
            meta['occupancies'] = datar
        return meta

    def handle_data(self, data):
        def update_rate(fps, hps, recent_total_hits, eps, recent_total_events):
            self.rate_label.setText("Readout Rate\n%d Hz" % fps)
            if self.spin_box.value() == 0:  # show number of hits, all hits are integrated
                self.hit_rate_label.setText("Total Hits\n%d" % int(recent_total_hits))
            else:
                self.hit_rate_label.setText("Hit Rate\n%d Hz" % int(hps))
            if self.spin_box.value() == 0:  # show number of events
                self.event_rate_label.setText("Total Events\n%d" % int(recent_total_events))
            else:
                self.event_rate_label.setText("Event Rate\n%d Hz" % int(eps))

        if 'meta_data' not in data:
            for plane, plot in enumerate(self.plots):
                self.occupancy_images[plane].setImage(data['occupancies'][plane], autoDownsample=True)
                self.occ_hist_sum[plane] = data['occupancies'][plane].sum()
                self.event_status_plots[plane].setData(x=np.linspace(-0.5, 31.5, 33), y=data['event_status'][plane], stepMode=True, fillLevel=0, brush=(0, 0, 255, 150))
                plot.setTitle('Occupancy Map, Sum: %i' % self.occ_hist_sum[plane])
        else:
            update_rate(data['meta_data']['fps'], data['meta_data']['hps'], data['meta_data']['total_hits'], data['meta_data']['eps'], data['meta_data']['total_events'])
            self.timestamp_label.setText("Data Timestamp\n%s" % time.asctime(time.localtime(data['meta_data']['timestamp_stop'])))
            self.scan_parameter_label.setText("Scan Parameters\n%s" % ', '.join('%s: %s' % (str(key), str(val)) for key, val in data['meta_data']['scan_parameters'].items()))
            now = ptime.time()
            self.plot_delay = self.plot_delay * 0.9 + (now - data['meta_data']['timestamp_stop']) * 0.1
            self.plot_delay_label.setText("Plot Delay\n%s" % 'not realtime' if abs(self.plot_delay) > 5 else "%1.2f ms" % (self.plot_delay * 1.e3))
