---
title: "Pymosa"
description: "Satellite for controlling a EUDET-type beam telescope using a MMC3 readout board"
category: "Readout Systems"
language: "Python"
parent_class: "TransmitterSatellite"
---

## Description

This satellite controls the readout of a EUDET-type beam telescope using a [MMC3 readout board](https://hdl.handle.net/20.500.11811/7265). 

## Building

Clone the repository:

```sh
git clone https://github.com/SiLab-Bonn/pymosa
```

Install via:
```sh
cd pymosa
pip install -e .[constellation]
```

## Usage

Set the correct IP address in [pymosa/m26.yaml](https://github.com/SiLab-Bonn/pymosa/blob/master/pymosa/m26.yaml) for more information.

Start the satellite with:

```sh
SatellitePymosa -g testbeam -n ANEMONE
```

## Parameters

| Configuration | Description | Type | Default Value |
|-----------|-------------|------| ------|
| `no_data_timeout` | (Required) No data timeout after which the scan will be aborted, in seconds; if 0, the timeout is disabled. | String | None |
| `send_data` | (Required) TCP address to which the telescope data is send; to allow incoming connections on all interfaces use 0.0.0.0 | String | None |
| `max_triggers` | (Required) Maximum number of triggers; if 0, there is no limit on the number of triggers. | Integer | None |
| `scan_timeout` | (Optional) Timeout after which the scan will be stopped, in seconds; if 0, the timeout is disabled. | Integer | 0 |
| `run_number` | (Optional) Base run number, will be automatically increased; if none is given, generate filename | Integer | None |
| `output_folder` | (Optional) Output folder for the telescope data; if none is given, the current working directory is used. | String | None |
| `m26_configuration_file` | (Optional) Configuration file for Mimosa26 sensors, if note stated a default one is used. | String | `m26_config/m26_threshold_8.yaml` |
| `m26_jtag_configuration` | (Optional) Send Mimosa26 configuration via JTAG. | String | True |
| `enabled_m26_channels` | (Optional) Enabled RX channels for readout of the individual planes, as example ["M26_RX1", "M26_RX2", "M26_RX6"]; default None (=all planes) | String | None |


### Configuration Example

An example Pymosa satellite configuration which could be dropped into a Constellation configuration as a starting point:

```toml
[pymosa.ANEMONE]
run_number = "None"  
output_folder = "None"  
m26_configuration_file = "None"  
m26_jtag_configuration = true  
no_data_timeout = 30 
scan_timeout = 0 
max_triggers = 0 
send_data = 'tcp://127.0.0.1:8500'
enabled_m26_channels = "None"
```

## Metrics

The following metrics are distributed by this satellite and can be subscribed to.

| Metric | Description | Value Type | Interval |
|--------|-------------|------------|----------|
| `TRIGGER_NUMBER` | Number of received triggers | Int | 1s |

## Data

Data is saved in HDF5 format in the `output_folder`.