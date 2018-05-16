# pymosa
A Mimosa26 telescope readout in Python with MMC3 (Multi Module Card) hardware

## Description

Pymosa features continuous and triggerless data taking of up to 6 Mimosa26 sensors, enabling operation at particle rates of up to 20 kHz.
The configuration of the Mimosa26 sensors can also be done with pymosa (via JTAG).

Readout and configuration are based on a single FPGA-readout board, the MMC3 readout board.

The data of the Mimosa26 sensors is streamed continuously to the readout board using RJ45 connectors. An additional RJ45 connection is used for the
configuration (JTAG) of the Mimosa26 sensors. An extra RJ45 connection provides the interface with the TLU.
Trigger words from TLU are needed in order to correlate Mimosa26 frame data with a time reference plane in order to obtain a time information for Mimosa26 data.
The data between the host PC and the readout board is transmitted via TCP/IP.
For powering the MMC3 readout board a 5 V DC power supply is needed.

Within pymosa the configuration can be set with the following files:

 - **m26.yaml**:
   Basil configuration file containing all the necessary information about the DUT (hardware setup).
 - **m26_configuration.yaml**:
   Main configuration file in which run is set up and triggers are configured.
 - **/m26_config/m26_threshold_8.yaml**:
   Contains Mimosa26 sensor configuration. By changing the number of the configuration file, the sensor threshold can be changed (between 4 - 11, default: 8).


## Installation
Install [Anacoda](http://conda.pydata.org).

Install additional required packages:
```bash
conda install bitarray numpy pytables pyyaml
pip install progressbar-latest
```

Install [Basil](https://github.com/SiLab-Bonn/basil) (>=2.4.12,<3.0.0):
```bash
pip install 'basil_daq>=2.4.12,<3.0.0'
```

Finally, install pymosa via:
```bash
python setup.py develop
```

## Usage
Before running telescope readout setup run and trigger configuration in configuration file (e.g. m26_configuration.yaml).

Run telescope readout via:
```bash
python m26.py
```
