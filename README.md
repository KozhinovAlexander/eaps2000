- [eaps2000 - PS 2000B Series PSU Python Control Unit](#eaps2000---ps-2000b-series-psu-python-control-unit)
  - [Installing the package](#installing-the-package)
  - [Getting Started](#getting-started)
  - [Building the Project](#building-the-project)


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
eaps2000 --help
```

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
    cfg['Vset'] = 3.3  # coltage to be set

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

[_ps_2kb_url_]: https://elektroautomatik.com/shop/de/produkte/programmierbare-dc-laborstromversorgungen/dc-laborstromversorgungen/serie-ps-2000-b-br-100-bis-332-w/
[_hatchling_home_]: https://hatch.pypa.io/1.9/
