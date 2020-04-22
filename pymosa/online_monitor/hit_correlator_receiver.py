import os

import yaml
import numpy as np
from PyQt5 import Qt
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
from pyqtgraph.dockarea import DockArea, Dock
from zmq.utils import jsonapi

from online_monitor.utils import utils
from online_monitor.receiver.receiver import Receiver


class HitCorrelator(Receiver):

    def setup_receiver(self):
        self.set_bidirectional_communication()  # We want to change converter settings
        # Load correlation DUT types
        config = os.path.join(os.path.dirname(__file__), 'correlation_duts.yaml')
        with open(config) as f:
            self.correlator_config = yaml.safe_load(f)

    def setup_widgets(self, parent, name):
        self.occupancy_images_columns = {}
        self.occupancy_images_rows = {}

        dut_names = []
        for device in self.config['correlation_planes']:
            dut_names.append(device['name'])

        dock_area = DockArea()
        parent.addTab(dock_area, name)
        # Send active tab index to converter so that it only does something when user is looking at corresponding receiver
        parent.currentChanged.connect(lambda value: self.send_command('ACTIVETAB %s' % str(parent.tabText(value))))

        dock_status = Dock("Status")
        dock_status.setMinimumSize(400, 90)
        dock_status.setMaximumHeight(110)
        dock_select_duts = Dock("Select DUT's")
        dock_select_duts.setMinimumSize(400, 90)
        dock_select_duts.setMaximumHeight(110)
        dock_corr_column = Dock('Column Correlation')
        dock_corr_column.setMinimumSize(400, 400)
        dock_corr_row = Dock('Row Correlation')
        dock_corr_row.setMinimumSize(400, 400)

        cb = QtGui.QWidget()
        layout0 = QtGui.QGridLayout()
        cb.setLayout(layout0)
        self.combobox1 = Qt.QComboBox()
        self.combobox1.addItems(dut_names)
        self.combobox1.setMinimumSize(100, 50)
        self.combobox1.setMaximumSize(200, 50)
        self.combobox2 = Qt.QComboBox()
        self.combobox2.addItems(dut_names)
        self.combobox2.setMinimumSize(100, 50)
        self.combobox2.setMaximumSize(200, 50)
        self.select_label = QtGui.QLabel('Correlate:')
        self.select_label1 = QtGui.QLabel('    to    ')
        self.start_button = QtGui.QPushButton('Start')
        self.stop_button = QtGui.QPushButton('Stop')
        self.start_button.setMinimumSize(75, 38)
        self.start_button.setMaximumSize(150, 38)
        self.stop_button.setMinimumSize(75, 38)
        self.stop_button.setMaximumSize(150, 38)
        layout0.setHorizontalSpacing(25)
        layout0.addWidget(self.select_label, 0, 0, 0, 1)
        layout0.addWidget(self.combobox1, 0, 1, 0, 1)
        layout0.addWidget(self.select_label1, 0, 2, 0, 1)
        layout0.addWidget(self.combobox2, 0, 3, 0, 1)
        layout0.addWidget(self.start_button, 0, 4, 0, 1)
        layout0.addWidget(self.stop_button, 0, 5, 0, 1)
        dock_select_duts.addWidget(cb)
        self.combobox1.activated.connect(lambda value: self.send_command('combobox1 %d' % value))
        self.combobox2.activated.connect(lambda value: self.send_command('combobox2 %d' % value))
        self.start_button.clicked.connect(lambda value: self.send_command('START %d' % value))
        self.stop_button.clicked.connect(lambda value: self.send_command('STOP %d' % value))

        cw = QtGui.QWidget()
        layout = QtGui.QGridLayout()
        cw.setLayout(layout)
        reset_button = QtGui.QPushButton('Reset')
        reset_button.setMinimumSize(100, 30)
        reset_button.setMaximumSize(300, 30)
        layout.setHorizontalSpacing(25)
        layout.addWidget(reset_button, 0, 1, 0, 1)
        remove_background_checkbox = QtGui.QCheckBox('Remove background:')
        layout.addWidget(remove_background_checkbox, 0, 2, 1, 1)
        remove_background_spinbox = QtGui.QDoubleSpinBox()
        remove_background_spinbox.setRange(0.0, 100.0)
        remove_background_spinbox.setValue(99.0)
        remove_background_spinbox.setSingleStep(1.0)
        remove_background_spinbox.setDecimals(1)
        remove_background_spinbox.setPrefix('< ')
        remove_background_spinbox.setSuffix(' % maximum occupancy')
        layout.addWidget(remove_background_spinbox, 0, 3, 1, 1)
        self.transpose_checkbox = QtGui.QCheckBox('Transpose columns and rows (of ref. plane)')
        layout.addWidget(self.transpose_checkbox, 1, 3, 1, 1)
        self.convert_checkbox = QtGui.QCheckBox('Axes in ' + u'\u03BC' + 'm')
        layout.addWidget(self.convert_checkbox, 1, 2, 1, 1)
        self.rate_label = QtGui.QLabel("Readout Rate: Hz")
        layout.addWidget(self.rate_label, 0, 4, 1, 1)
        dock_status.addWidget(cw)
        reset_button.clicked.connect(lambda: self.send_command('RESET'))
        self.transpose_checkbox.stateChanged.connect(lambda value: self.send_command('TRANSPOSE %d' % value))
        remove_background_checkbox.stateChanged.connect(lambda value: self.send_command('BACKGROUND %d' % value))
        remove_background_spinbox.valueChanged.connect(lambda value: self.send_command('PERCENTAGE %f' % value))
        # Add plot docks for column correlation
        occupancy_graphics1 = pg.GraphicsLayoutWidget()
        occupancy_graphics1.show()
        view1 = occupancy_graphics1.addViewBox()
        occupancy_img_col = pg.ImageItem(border='w')
        poss = np.array([0.0, 0.01, 0.5, 1.0])
        color = np.array([[1.0, 1.0, 1.0, 1.0], [0.267004, 0.004874, 0.329415, 1.0], [0.127568, 0.566949, 0.550556, 1.0], [0.993248, 0.906157, 0.143936, 1.0]])  # Zero is white
        mapp = pg.ColorMap(poss, color)
        lutt = mapp.getLookupTable(0.0, 1.0, 100)
        occupancy_img_col.setLookupTable(lutt, update=True)
        self.plot1 = pg.PlotWidget(viewBox=view1)
        self.plot1.getAxis('bottom').setLabel(text='Columns')
        self.plot1.getAxis('left').setLabel(text='Columns')
        self.plot1.addItem(occupancy_img_col)
        dock_corr_column.addWidget(self.plot1)
        self.occupancy_images_columns = occupancy_img_col
        # Add plot docks for row correlation
        occupancy_graphics2 = pg.GraphicsLayoutWidget()
        occupancy_graphics2.show()
        view2 = occupancy_graphics2.addViewBox()
        occupancy_img_rows = pg.ImageItem(border='w')
        occupancy_img_rows.setLookupTable(lutt, update=True)
        self.plot2 = pg.PlotWidget(viewBox=view2)
        self.plot2.getAxis('bottom').setLabel(text='Rows')
        self.plot2.getAxis('left').setLabel(text='Rows')
        self.plot2.addItem(occupancy_img_rows)
        dock_corr_row.addWidget(self.plot2)
        self.occupancy_images_rows = occupancy_img_rows
        dock_area.addDock(dock_status, 'top')
        dock_area.addDock(dock_select_duts, 'left')
        dock_area.addDock(dock_corr_column, 'bottom')
        dock_area.addDock(dock_corr_row, 'right', dock_corr_column)

        def scale_and_label_axes(scale_state, dut1, dut2, transpose_state):
            ''' Rescale axis and change labels (according to tranpose and scale option).
            '''
            dut1_name = self.config['correlation_planes'][dut1]['name']
            dut2_name = self.config['correlation_planes'][dut2]['name']
            if scale_state == 0:  # Column/Row scaling
                self.plot1.getAxis('bottom').setScale(1.0)
                self.plot1.getAxis('left').setScale(1.0)
                self.plot2.getAxis('bottom').setScale(1.0)
                self.plot2.getAxis('left').setScale(1.0)
                self.plot1.getAxis('bottom').setTickSpacing()
                self.plot1.getAxis('left').setTickSpacing()
                self.plot2.getAxis('bottom').setTickSpacing()
                self.plot2.getAxis('left').setTickSpacing()
                if transpose_state == 0:  # False
                    self.plot1.getAxis('bottom').setLabel(text=dut1_name + ' Columns')
                    self.plot2.getAxis('bottom').setLabel(text=dut1_name + ' Rows')
                elif transpose_state == 2:  # True
                    self.plot1.getAxis('bottom').setLabel(text=dut1_name + ' Rows')
                    self.plot2.getAxis('bottom').setLabel(text=dut1_name + ' Columns')

                self.plot1.getAxis('left').setLabel(text=dut2_name + ' Columns')
                self.plot2.getAxis('left').setLabel(text=dut2_name + ' Rows')

            elif scale_state == 2:  # um scaling
                col_size_dut_1 = self.correlator_config[self.config['correlation_planes'][dut1]['dut_type']]['column_size']
                row_size_dut_1 = self.correlator_config[self.config['correlation_planes'][dut1]['dut_type']]['row_size']
                col_size_dut_2 = self.correlator_config[self.config['correlation_planes'][dut1]['dut_type']]['column_size']
                row_size_dut_2 = self.correlator_config[self.config['correlation_planes'][dut1]['dut_type']]['row_size']
                if transpose_state == 0:  # False
                    self.plot1.getAxis('bottom').setScale(row_size_dut_1)
                    self.plot2.getAxis('bottom').setScale(col_size_dut_1)
                    self.plot1.getAxis('left').setScale(col_size_dut_2)
                    self.plot2.getAxis('left').setScale(row_size_dut_2)
                    self.plot1.getAxis('bottom').setLabel(text=dut1_name + ' Columns / ' + u'\u03BC' + 'm')
                    self.plot2.getAxis('bottom').setLabel(text=dut1_name + ' Rows / ' + u'\u03BC' + 'm')
                    self.plot1.getAxis('left').setLabel(text=dut2_name + ' Columns / ' + u'\u03BC' + 'm')
                    self.plot2.getAxis('left').setLabel(text=dut2_name + ' Rows / ' + u'\u03BC' + 'm')
                elif transpose_state == 2:  # True
                    self.plot1.getAxis('bottom').setScale(col_size_dut_1)
                    self.plot2.getAxis('bottom').setScale(row_size_dut_1)
                    self.plot1.getAxis('left').setScale(col_size_dut_2)
                    self.plot2.getAxis('left').setScale(row_size_dut_2)
                    self.plot1.getAxis('bottom').setLabel(text=dut1_name + ' Rows / ' + u'\u03BC' + 'm')
                    self.plot2.getAxis('bottom').setLabel(text=dut1_name + ' Columns / ' + u'\u03BC' + 'm')
                    self.plot1.getAxis('left').setLabel(text=dut2_name + ' Columns / ' + u'\u03BC' + 'm')
                    self.plot2.getAxis('left').setLabel(text=dut2_name + ' Rows / ' + u'\u03BC' + 'm')

        self.convert_checkbox.stateChanged.connect(lambda value: scale_and_label_axes(value, self.combobox1.currentIndex(), self.combobox2.currentIndex(), self.transpose_checkbox.checkState()))
        self.combobox1.activated.connect(lambda value: scale_and_label_axes(self.convert_checkbox.checkState(), value, self.combobox2.currentIndex(), self.transpose_checkbox.checkState()))
        self.combobox2.activated.connect(lambda value: scale_and_label_axes(self.convert_checkbox.checkState(), self.combobox1.currentIndex(), value, self.transpose_checkbox.checkState()))
        self.transpose_checkbox.stateChanged.connect(lambda value: scale_and_label_axes(self.convert_checkbox.checkState(), self.combobox1.currentIndex(), self.combobox2.currentIndex(), value))

    def deserialize_data(self, data):
        return jsonapi.loads(data, object_hook=utils.json_numpy_obj_hook)

    def handle_data(self, data):
        if 'meta_data' not in data:
            for key in data:
                if 'column' == key:
                    self.occupancy_images_columns.setImage(data[key][:, :], autoDownsample=True)
                    self.plot1.setTitle('Column Correlation, Sum: %i' % data[key][:, :].sum())
                if 'row' == key:
                    self.occupancy_images_rows.setImage(data[key][:, :], autoDownsample=True)
                    self.plot2.setTitle('Row Correlation, Sum: %i' % data[key][:, :].sum())
        else:
            self.rate_label.setText('Readout Rate: %d Hz' % data['meta_data']['fps'])
