- [eaps2000 - PS 2000B Series PSU Python Control Unit](#eaps2000---ps-2000b-series-psu-python-control-unit)
  - [Installing the package](#installing-the-package)
  - [Getting Started](#getting-started)
  - [Building the Project](#building-the-project)
  - [Documentation form the Manufacturer](#documentation-form-the-manufacturer)
    - [Object List](#object-list)


# eaps2000 - PS 2000B Series PSU Python Control Unit

The `eaps2000` is a python module for [Elektro-Automatik PS 2000B Series][_ps_2kb_url_] PSU control.

This software implements following functionality:

- Reading out device information (serial number, model etc.)
- Setting ovewr-voltage and over-current protection
- Setting voltage and current for an output
- Controlling the output stage on/off
- Acknowledging alarms

## Installing the package

Install the project from PyPi or [build](#building-the-project) it first.

```bash
pip install eaps2000
```

## Getting Started

Using CLI interface:

```bash

# Showing help
eaps2000 --help

# Show device info and current state
eaps2000 -p COM123 --info

# Set output voltage to 3.3V, current to 1.3A, output off:
eaps2000 -p COM123 -V 3.5 -I 1.3 --off

# Set output voltage to 3.3V, current to 1.3A, output on:
# CAUTION: This command will apply power to the output!
eaps2000 -p COM123 -V 3.5 -I 1.3 --on
```

**NOTE:** Instead `COM123` port a port `/tty/usbACM0` shall be used on Linux.

Using Python interface:

```python
from eaps2000 import eaps2k

port = 'COM123'  # use /tty/ACM0 for linux based system
with eaps2k(port) as ps:
    # Prepare config:
    cfg = eaps2k.get_config_template()
    cfg['ACK'] = True  # acknowledge alarms if any
    cfg['OVP'] = 5.0   # over-voltage-protection value
    cfg['OCP'] = 0.5   # over-current-protection value
    cfg['Iset'] = 0.1  # current to be set
    cfg['Vset'] = 3.3  # voltage to be set

    # Turn off the output stage:
    ps.set_output_state(False)

    # Apply configuration:
    ps.configure(cfg)

    # Turn on the output stage:
    # ATTENTION: The power will be applied to your probe here!
    # ps.set_output_state(True)

    # Show information:
    ps.print_info()
```

## Building the Project

The project is built with [`hatchling`][_hatchling_home_]

```bash
pip install hatchling && flake8 . -v && hatchling build && pytest --flake8
```

Installing freshly built project may be done by invoking:

```bash
pip install ./dist/eaps2000-*.whl --upgrade --force-reinstall
```

## Documentation form the Manufacturer

The manufacturer `EA ELEKTRO-AUTOMATIK GMBH & CO. KG` has an overview over all
available models of `PS 2000 B Series` in the shop [Serie PS 2000 B 100 bis 332 W][_ps_2kb_url_]
on German web-page.

The [Programming_Guide_PS2000B_TFT][_ps2kb_programming_guide_] gives an overview of
the protovol implemented. It also describes voltage/current conversions necessary for the
communication.

### Object List

Additional document `object_list_ps2000b_de_en.pdf` mentioned in
[Programming_Guide_PS2000B_TFT][_ps2kb_programming_guide_] gives an overview over control commands.
Each object in the list is basically a get/set command to control the PSU.

The table below lists objects in one place:

| Object | Description                | Access | Data type | Data length in Bytes | Mask for type 'char' | Data | Example or further description |
|--------|----------------------------|--------|-----------|----------------------|----------------------|------|--------------------------------|
| 0  | Device type                   | ro | string | 16 | | | PS2042-06B + EOL (EOL= End of Line 0x00) |
| 1  | Device serial no.             | ro | string | 16 | | | 1034440002 + EOL |
| 2  | Nominal voltage               | ro | float  | 4  | | | Unom = 42.0 (Floating point number IEEE754 Standard) |
| 3  | Nominal current               | ro | float  | 4  | | | Inom = 6.0 (Floating point number IEEE754 Standard)|
| 4  | Nominal power                 | ro | float  | 4  | | | Pnom = 100.0 (Floating point number IEEE754 Standard) |
| 6  | Device article no.            | ro | string | 16 | | | 39200112 + EOL |
| 8  | Manufacturer                  | ro | string | 16 | | | Manufacturer's name + EOL |
| 9  | Software version              | ro | string | 16 | | | V2.01 09.08.06 + EOL |
| 19 | Device class                  | ro | int    | 2  | | | 0x0010 = PS 2000 B Single, 0x0018 = PS 2000 B Triple |
| 38 | OVP threshold                 | rw | int    | 2  | | | Overvoltage set value 0-110% of Unom * 256 |
| 39 | OCP threshold                 | rw | int    | 2  | | | Overcurrent set value 0-110% of Inom * 256 |
| 50 | Set value U                   | rw | int    | 2  | | | Set value of voltage 0-100% of Unom * 256 |
| 51 | Set value I                   | rw | int    | 2  | | | Set value of current 0-100% of Inom * 256 |
| 54 | Power supply control          | rw | char   | 2  | 0x01<br>0x01<br>0x0A<br>0x10<br>0x10<br>0xF0<br>0xF0 | 0x01<br>0x00<br>0x0A<br>0x10<br>0x00<br>0xF0<br>0xE0 | <li>Switch power output on<br><li>Switch power output off<br><li>Acknowledge alarms<br><li>Switch to remote control<br><li>Switch to manual control<br><li>Tracking on<br><li>Tracking off |
| 71 | Status + Actual values        | ro | int    | 6  | | <li>Byte 0:<br>Bits 1+0:<br>Byte 1:<br>Bit 0:<br><li>Bits 2+1:<br>Bit 3:<br>Bit 4:<br>Bit 5:<br>Bit 6:<br>Bit 7:<br><li>Word 1:<br><li>Word 2: | <li>Query device state<br>00=free access; 01=Remote<br><br>1=Output on<br><li>Controller state: 00=CV, 10=CC<br>1=Tracking active**<br>1=OVP active<br>1=OCP active<br>1=OPP active<br>1=OTP active<br><li>Actual voltage (% of Unom * 256)<br><li>Actual current (% of Inom * 256) |
| 72 | Status + Momentary set values | ro | int    | 6  | | <li>Byte 0:<br>Bits 1+0:<br>Byte 1:<br>Bit 0:<br><li>Bits 2+1:<br>Bit 3:<br>Bit 4:<br>Bit 5:<br>Bit 6:<br>Bit 7:<br><li>Word 1:<br><li>Word 2: | <li>Query device state<br>00=free access; 01=Remote<br><br>1=Output on<br><li>Controller state: 00=CV; 10=CC<br>1=Tracking active**<br>1=OVP active<br>1=OCP active<br>1=OPP active<br>1=OTP active<br><li>Set value of voltage (% of Unom * 256)<br><li>Set value of current (% of Inom * 256) |

** PS 2000 B Triple only

[_ps_2kb_url_]: https://elektroautomatik.com/shop/de/produkte/programmierbare-dc-laborstromversorgungen/dc-laborstromversorgungen/serie-ps-2000-b-br-100-bis-332-w/
[_ps2kb_programming_guide_]: https://elektroautomatik.com/shop/media/archive/f1/49/71/Programming_Guide_PS2000B_TFT.zip
[_hatchling_home_]: https://hatch.pypa.io/1.9/
