# pymosa ![Build status](https://github.com/SiLab-Bonn/pymosa/actions/workflows/tests.yml/badge.svg?branch=master)

A readout software for [Mimosa26](http://www.iphc.cnrs.fr/List-of-MIMOSA-chips.html) CMOS pixel sensors in Python together with the FPGA-based MMC3 (Multi Module Card) readout hardware.

## Description

Pymosa features continuous and triggerless data taking of up to 6 Mimosa26 sensors.
Pymosa enables the operation of Mimosa26 sensors at high particle rates (at several hundred kilohertz).
The Mimosa26 sensors are also configured with pymosa via a JTAG interface.

The data of each Mimosa26 sensors is send serially to the readout board using the dual-channel outputs at 80MHz data rate.
Six of the eight RJ45 connectors are designated to interconnect with the Mimosa26 sensors.
One RJ45 connector is used for JTAG interface for the configuration of the Mimosa26 sensors.
The time information for the Mimosa26 hit data is generated in the FPGA on the MMC3 readout board to allow for precise timing of each hit (115.2us time resolution).
This time resolution is sufficient to generate telescope tracks with high efficiency even in a high-density beam.

The raw data (time information together with the Mimosa26 raw data) is collected by the MMC3 readout board and send to the host PC via TCP/IP where it is compressed and recorded in a HDF5 file.
The raw data can be analyzed with the [Mimosa26 Interpreter](https://github.com/SiLab-Bonn/pymosa_mimosa26_interpreter).
The analyzed data (hit information and time information) can be obtained from a HDF5 table.

An additional RJ45 connector provides an interface to the [EUDET Trigger Logic Unit](https://www.eudet.org/e26/e28/e42441/e57298/EUDET-MEMO-2009-04.pdf) (TLU).
A trigger from the TLU is used for the generation of additional trigger timestamps and counters in the FPGA on the MMC3 readout board.
The trigger data is used to correlate the Mimosa26 hit data with data from other detectors.

Within pymosa the configuration can be set with the following files:

 - **m26.yaml**:
   Basil configuration file containing all the necessary information about the DUT (hardware setup).
 - **m26_configuration.yaml**:
   Main configuration file in which run is set up and triggers are configured.
 - **/m26_config/m26_threshold_8.yaml**:
   Contains Mimosa26 sensor configuration. By changing the number of the configuration file, the sensor threshold can be changed (between 4 - 11, default: 8).


## Installation

Python 2.7 or Python 3 or higher must be used. There are many ways to install Python, though we recommend using [Anaconda Python](https://www.anaconda.com/distribution/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html).

Install additional required packages:
```bash
conda install bitarray matplotlib numba numpy pyqt pytables pyyaml qtpy tqdm
```

Install [Basil](https://github.com/SiLab-Bonn/basil):
```bash
pip install 'basil_daq>=3.0.0,<4.0.0'
```

Install [Mimosa26 Interpreter](https://github.com/SiLab-Bonn/pymosa_mimosa26_interpreter):
```bash
pip install 'pymosa_mimosa26_interpreter>=1.0.0'
```

Install [Online Monitor](https://github.com/SiLab-Bonn/online_monitor):
```bash
pip install 'online_monitor>=0.4.2,<0.5'
```

Finally, install pymosa via:
```bash
pip insall -e .
```

## Usage

Before running telescope readout setup run and trigger configuration in configuration file (e.g. m26_configuration.yaml).

Run telescope readout via:
```bash
pymosa
```

Get help with:
```bash
pymosa --help
```


## IP address configuration
In order to use multiple readout systems with one PC, every readout needs its own IP address (and Ethernet interface). The IP address can be changed via the PMOD connector (located between the power connector and the USB port.) using jumper settings.
The default IP address is 192.168.10.**10**, but you can set the subnet in a range between .**10**.10 and .**25**.10.

The IP address can be changed via the following steps:
- Make sure, the readout system is not powered.
- Locate PMOD Pin1 (indicated by a white dot on the PCB).
- The IP is set by putting jumpers on the PMOD connector, which short pin 1+2, 3+4, 5+6 and 7+8. Standard binary counting is used:

    | PMOD_7+8 | PMOD_5+6 | PMOD_3+4 | PMOD_1+2 | IP_ADDRESS    |
    | -------- | -------- | -------- | -------- | ------------- |
    | 0        | 0        | 0        | 0        | 192.168.10.10 |
    | 0        | 0        | 0        | 1        | 192.168.11.10 |
    | ...      | ...      | ...      | ...      | ...           |
    | 1        | 1        | 1        | 0        | 192.168.24.10 |
    | 1        | 1        | 1        | 1        | 192.168.25.10 |


- Double check, that you did not place the jumper in the wrong place!
- Turn the readout system on and verify the setting by a ping to the new IP address.


## Support

Please use GitHub's [issue tracker](https://github.com/SiLab-Bonn/pymosa/issues) for bug reports/feature requests/questions.
