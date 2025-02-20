#!/usr/bin/env python

'''
Elektro-Automatik Series PS 2000 Python Controller

License: Apache 2.0

Disclaimer: This is NOT an official software made by the manufacturer.

Description: The Elektro-Automatik Series PS 2000 Python Controller
is a versatile software designed to interface with the Elektro-Automatik
PS 2000 series power supplies.
Developed with Python, this controller allows users to automate and
manage their power supply operations efficiently.

IMPORTANT NOTICE: This software is provided as-is. There is NO WARRANTY,
NO GUARANTEE of performance, and it is NOT officially endorsed by the manufacturer.
Use at your own risk.

Author: Alexander Kozhinov <ak.alexander.kozhinov@gmail.com>
'''

import argparse
import serial
import struct
import sys
from importlib.metadata import version


class eaps2k(object):
    PS_QUERY = 0x40
    PS_SEND = 0xc0

    def __init__(self, port: str, timeout: float = 0.06, baudrate: int = 115200,
                 parity: str = serial.PARITY_ODD, verbosity_level=0):
        '''
        Initialize the PS2000 device with the specified serial port settings.
        Args:
            port (str): The serial port to which the PS2000 device is connected.
            timeout (float, optional): The timeout for serial communication in seconds. Default is 0.06.
            baudrate (int, optional): The baud rate for serial communication. Default is 115200.
            parity (str, optional): The parity bit setting for serial communication. Default is serial.PARITY_ODD.
            verbosity_level (int, optional): The verbosity level for logging. Use 3 to see more information. Default is 0.
        Attributes:
            _verbose (int): Stores the verbosity level for logging.
            ser_dev (serial.Serial): The serial device object for communication with the PS2000.
            _u_nom (float): The nominal voltage of the PS2000 device.
            _i_nom (float): The nominal current of the PS2000 device.
        '''
        self._verbosity_lvl = verbosity_level
        # set timeout to 0.06s to guarantee minimum interval time of 50ms
        self.ser_dev = serial.Serial(port, timeout=timeout, baudrate=baudrate,
                                     parity=parity)
        self._translation_factor = 25600.0
        self._u_nom = self.get_nominal_voltage()
        self._i_nom = self.get_nominal_current()

    @staticmethod
    def pkg_version() -> str:
        '''
        Returns this packgae version
        '''
        ver = '0.0.0'
        try:
            ver = version(__name__)
        except Exception:
            pass
        return ver

    @staticmethod
    def description():
        '''
        Returns description of this module.
        '''
        descr = \
            f'{__name__} {eaps2k.pkg_version()}. ' \
            '\nElektro-Automatik Series PS 2000 Python Controller. ' \
            '\nLicense: Apache 2.0 ' \
            '\nDisclaimer: This is NOT an official software made by the manufacturer. ' \
            '\nIMPORTANT NOTICE: This software is provided as-is. There is NO WARRANTY,' \
            '\nNO GUARANTEE of performance, and it is NOT officially endorsed by the manufacturer. ' \
            '\nUse at your own risk. ' \
            '\nAuthor: Alexander Kozhinov <ak.alexander.kozhinov@gmail.com>'
        return descr

    def __enter__(self):
        self.set_remote(True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.set_remote(False)
        self.ser_dev.close()
        if exc_type is not None:
            print(f'An exception occurred: {exc_value}\nTraceback: {traceback}')

    @staticmethod
    def _construct_telegram(telegram_type, node, obj, data) -> bytearray:
        '''
        Constructs a telegram message for communication.
        Args:
            telegram_type (int): The type of the telegram.
            node (int): The device node.
            obj (int): The object identifier.
            data (bytes): The data to be included in the telegram.
        Returns:
            bytearray: The constructed telegram message.
        The telegram message format is as follows:
            - Start delimiter (SD): 0x30 + telegram_type
            - Device node (DN): node
            - Object (OBJ): obj
            - Data (DATA): data (if any)
            - Checksum (CS): sum of all previous bytes, split into two bytes (CS0 and CS1)
        '''
        telegram = bytearray()
        telegram.append(0x30 + telegram_type)  # SD (start delimiter)
        telegram.append(node)                  # DN (device node)
        telegram.append(obj)                   # OBJ (object)
        if len(data) > 0:                      # DATA
            telegram.extend(data)
            telegram[0] += len(data) - 1  # update length

        cs = sum(telegram)
        telegram.append(cs >> 8)    # CS0
        telegram.append(cs & 0xff)  # CS1 (checksum)

        return telegram

    @staticmethod
    def _checksum_verify(ans):
        '''
        Compare checksum with header and data in response from device.
        This function calculates the checksum of the given response data and
        compares it with the checksum provided in the last two bytes of the response.
        If the calculated checksum does not match the provided checksum, an assertion
        error is raised indicating a checksum mismatch.
        Args:
            ans (list or bytearray): The response data from the device, including the
                                     checksum in the last two bytes.
        Raises:
            AssertionError: If the calculated checksum does not match the provided checksum.
        '''
        cs = sum(ans[0:-2])
        assert ans[-2] == (cs >> 8) and ans[-1] == (cs & 0xff), \
            'ERROR: Checksum mismatch'

    @staticmethod
    def _check_error(ans):
        '''
        Checks for errors in the given answer and raises an assertion error with
        a detailed message if an error is found.
        Args:
            ans (list of int): The answer to check, represented as a list of integers.
        Raises:
            AssertionError: If an error is found, with a message detailing the
                            error type and the answer in hexadecimal format.
        '''
        if ans[2] != 0xff:
            return

        response_state_table = {
            0x00: 'OK: Acknowledge',  # got acknowledge - not an error
            0x03: 'ERROR: Com: Checksum incorrect',
            0x04: 'ERROR: Com: Start delimiter incorrect',
            0x05: 'ERROR: Com: Wrong address for output',
            0x07: 'ERROR: Com: Object not defined',
            0x08: 'ERROR: Usr: Object length incorrect',
            0x09: 'ERROR: Usr: Access denied',
            0x0f: 'ERROR: Usr: Device is locked',
            0x30: 'ERROR: Usr: Upper limit exceeded',
            0x31: 'ERROR: Usr: Lower limit exceeded',
        }

        resp_str = 'unknown error'
        if ans[3] in response_state_table.keys():
            resp_str = response_state_table[ans[3]]
        assert ans[3] == 0x00, f'{resp_str}\n-- answer:\t\t{eaps2k.bytes2hex(ans)}'

    @staticmethod
    def bytes2hex(bytes_arr):
        '''
        Converts a byte array to a string of hexadecimal values.
        Args:
            bytes_arr (bytes): The byte array to convert.
        Returns:
            str: A string of hexadecimal values separated by spaces.
        '''
        return ' '.join(hex(b) for b in bytes_arr)

    def _transfer(self, telegram_type, node, obj, data,
                  read_buff_len: int = 100) -> bytes:
        '''
        Transfers data to and from a serial device.
        This method constructs a telegram based on the provided telegram_type, node, object, and data,
        sends it to the serial device, and reads the response. It also performs verbosity-based
        logging, checks the response length, and validates the checksum and error status.
        Args:
            telegram_type (int): The type of telegram to construct.
            node (int): The node identifier.
            obj (int): The object identifier.
            data (bytes): The data to be included in the telegram.
            read_buff_len(int): Bytes read buffer length.
        Returns:
            bytes: The response received from the serial device.
        Raises:
            SystemExit: If the response received is shorter than expected.
        '''
        telegram = eaps2k._construct_telegram(telegram_type, node, obj, data)

        if self._verbosity_lvl >= 3:
            print(f'-- telegram:\t\t{eaps2k.bytes2hex(telegram)}')

        self.ser_dev.write(telegram)  # send telegram
        ans = self.ser_dev.read(read_buff_len)

        if self._verbosity_lvl >= 3:
            print(f'-- answer:\t\t{eaps2k.bytes2hex(telegram)}')

        min_len = 5  # 5 bytes is the minimum length of a valid answer
        assert len(ans) >= min_len, \
            f'Short answer {len(ans)} bytes received, expected at least {min_len} bytes)'

        # check the answer
        eaps2k._checksum_verify(ans)
        eaps2k._check_error(ans)

        return ans

    def _read_obj(self, obj, obj_type: type = bytes):
        allowed_obj_types = [bytes, str, float, int]
        assert obj_type in allowed_obj_types, \
            f'ERROR: Object type shall be one of {allowed_obj_types} ' \
            f'but it is {obj_type if obj_type is not type else type(obj_type)}'

        msg = self._transfer(self.PS_QUERY, 0, obj, '')[3:-2]
        if obj_type is bytes:
            return msg
        elif obj_type is str:
            return msg.decode('ascii')
        elif obj_type is float:
            return struct.unpack('>f', msg)[0]
        elif obj_type is int:
            return struct.unpack('>H', msg)[0]
        else:
            assert False, 'ERROR: Unknown!'

    def _write_obj(self, obj, data, obj_type: type = bytes, mask=None):
        allowed_obj_types = [bytes, int]
        assert obj_type in allowed_obj_types, \
            f'ERROR: Object type shall be one of {allowed_obj_types} ' \
            f'but it is {obj_type if obj_type is not type else type(obj_type)}'

        if obj_type is bytes:
            assert mask is not None, f'ERROR: The mask argument value {mask} is not allowed!'
            ans = self._transfer(self.PS_SEND, 0, obj, [mask, data])
            return ans[3:-2]
        elif obj_type is int:
            ans = self._transfer(self.PS_SEND, 0, obj, [int(data) >> 8, int(data) & 0xff])
            return (ans[3] << 8) + ans[4]
        else:
            assert False, 'ERROR: Unknown!'

    def get_type(self):
        '''
        object 0
        see: object_list_ps2000b_de_en.pdf
        '''
        return self._read_obj(0, str)

    def get_serial(self):
        '''
        object 1
        see: object_list_ps2000b_de_en.pdf
        '''
        return self._read_obj(1, str)

    def get_nominal_voltage(self):
        '''
        object 2
        see: object_list_ps2000b_de_en.pdf
        '''
        return float(self._read_obj(2, float))

    def get_nominal_current(self):
        '''
        object 3
        see: object_list_ps2000b_de_en.pdf
        '''
        return float(self._read_obj(3, float))

    def get_nominal_power(self):
        '''
        object 4
        see: object_list_ps2000b_de_en.pdf
        '''
        return self._read_obj(4, float)

    def get_article(self):
        '''
        object 6
        see: object_list_ps2000b_de_en.pdf
        '''
        return self._read_obj(6, str)

    def get_manufacturer(self):
        '''
        object 8
        see: object_list_ps2000b_de_en.pdf
        '''
        return self._read_obj(8, str)

    def get_version(self):
        '''
        object 9
        see: object_list_ps2000b_de_en.pdf
        '''
        return self._read_obj(9, str)

    def get_device_class(self):
        '''
        object 19
        see: object_list_ps2000b_de_en.pdf

        avialable classes:
            0x0010 = PS 2000 B Single, 0x0018 = PS 2000 B Triple
        '''
        ans = int(self._read_obj(19, int))
        dev_class_str = 'unknown'
        if ans == 0x0010:
            dev_class_str = 'PS 2000 B Single'
        elif ans == 0x0018:
            dev_class_str = 'PS 2000 B Triple'
        return (ans, dev_class_str)

    def get_ovp(self):
        '''
        object 38
        see: object_list_ps2000b_de_en.pdf
        '''
        return self.percent2real(self._u_nom, float(self._read_obj(38, int)))

    def set_ovp(self, u):
        '''
        object 38
        see: object_list_ps2000b_de_en.pdf
        '''
        if self._verbosity_lvl >= 1:
            print(f'Set Over-Voltage-Protection: {u}')
        return self._write_obj(38, int(round(self.real2percent(self._u_nom, u))), int)

    def get_ocp(self):
        '''
        object 39
        see: object_list_ps2000b_de_en.pdf
        '''
        return self.percent2real(self._i_nom, float(self._read_obj(39, int)))

    def set_ocp(self, i):
        '''
        object 39
        see: object_list_ps2000b_de_en.pdf
        '''
        if self._verbosity_lvl >= 1:
            print(f'Set Over-Current-Protection: {i}')
        return self._write_obj(39, int(round(self.real2percent(self._i_nom, i))), int)

    def get_voltage_setpoint(self):
        '''
        object 50
        see: object_list_ps2000b_de_en.pdf
        '''
        return self.percent2real(self._u_nom, float(self._read_obj(50, int)))

    def set_voltage(self, u):
        '''
        object 50
        see: object_list_ps2000b_de_en.pdf
        '''
        if self._verbosity_lvl >= 1:
            print(f'Set Voltage: {u}')
        return self._write_obj(50, int(round(self.real2percent(self._u_nom, u))), int)

    def get_current_setpoint(self):
        '''
        object 51
        see: object_list_ps2000b_de_en.pdf
        '''
        return self.percent2real(self._i_nom, float(self._read_obj(51, int)))

    def set_current(self, i):
        '''
        object 51
        see: object_list_ps2000b_de_en.pdf
        '''
        if self._verbosity_lvl >= 1:
            print(f'Set Current: {i}')
        return self._write_obj(51, int(round(self.real2percent(self._i_nom, i))), int)

    def get_control(self):
        '''
        object 54
        see: object_list_ps2000b_de_en.pdf
        '''
        ans = bytes(self._read_obj(54))
        control = {
            'output_on': True if ans[1] & 0x01 else False,
            'remote': True if ans[0] & 0x01 else False
        }
        return control

    def _set_control(self, mask, data):
        '''
        object 54
        see: object_list_ps2000b_de_en.pdf
        '''
        ans = bytes(self._write_obj(54, data, bytes, mask))
        # return True if command was acknowledged ("error 0")
        return ans[0] == 0xff and ans[1] == 0x00

    def ack_alarm(self):
        if self._verbosity_lvl >= 2:
            print('ACK Alarm')
        return self._set_control(0x0a, 0x0a)

    def get_remote(self):
        return self.get_control()['remote']

    def set_remote(self, remote=True):
        if remote:
            return self._set_control(0x10, 0x10)
        else:
            return self._set_control(0x10, 0x00)

    def set_local(self, local=True):
        return self.set_remote(not local)

    def get_output_state(self):
        return self.get_control()['output_on']

    def set_output_state(self, on=True):
        data = 0x01 if on else 0x00
        if self._verbosity_lvl >= 2:
            print(f"Set Output: {'on' if on else 'off'}")
        return self._set_control(0x01, data)

    def percent2real(self, nominal_value: float, percent_value: float) -> float:
        '''
        Convert percent value to real one by utilizing following equation:
            (nominal_value * percent_value) / translation_factor
        see: PS2000B_TFT_Programming_English.pdf, page 4
        '''
        return (nominal_value * percent_value) / self._translation_factor

    def real2percent(self, nominal_value: float, value: float) -> float:
        '''
        Convert real value to percent one by utilizing following equation:
            (translation_factor * value) / nominal_value
        see: PS2000B_TFT_Programming_English.pdf, page 4
        '''
        return (self._translation_factor * value) / nominal_value

    def get_actual(self):
        '''
        object 71
        see: object_list_ps2000b_de_en.pdf
        '''
        ans = bytes(self._read_obj(71))
        state = {
            'remote': True if ans[0] & 0x03 else False,
            'on': True if ans[1] & 0x01 else False,
            'CC': True if ans[1] & 0x06 else False,
            'CV': False if ans[1] & 0x06 else True,  # not CC
            'tracking': True if ans[1] & 0x08 else False,
            'OVP': True if ans[1] & 0x10 else False,
            'OCP': True if ans[1] & 0x20 else False,
            'OPP': True if ans[1] & 0x40 else False,
            'OTP': True if ans[1] & 0x80 else False,
            'V': self.percent2real(self._u_nom, float((int(ans[2]) << 8) + int(ans[3]))),
            'I': self.percent2real(self._i_nom, float((int(ans[4]) << 8) + int(ans[5]))),
        }
        return state

    def get_setpoints(self):
        '''
        object 72
        see: object_list_ps2000b_de_en.pdf
        '''
        ans = bytes(self._read_obj(72))
        state = {
            'remote': True if ans[0] & 0x03 else False,
            'on': True if ans[1] & 0x01 else False,
            'CC': True if ans[1] & 0x06 else False,
            'OVP': True if ans[1] & 0x10 else False,
            'OCP': True if ans[1] & 0x20 else False,
            'OPP': True if ans[1] & 0x40 else False,
            'OTP': True if ans[1] & 0x80 else False,
            'V': self.percent2real(self._u_nom, float((int(ans[2]) << 8) + int(ans[3]))),
            'I': self.percent2real(self._i_nom, float((int(ans[4]) << 8) + int(ans[5]))),
        }
        return state

    @staticmethod
    def get_config_template() -> dict:
        '''
        Returns a dictionary with the configuration template for the system.
        The dictionary contains the following keys:
            - 'ACK': Acknowledge alarms, initialized to False (bool)
            - 'OVP': Over Voltage Protection, initialized to 0.0 (float)
            - 'OCP': Over Current Protection, initialized to 0.0 (float)
            - 'Iset': Current setpoint, initialized to 0.0 (float)
            - 'Vset': Voltage setpoint, initialized to 0.0 (float)
        Returns:
            dict: A dictionary with the configuration template.
        '''
        return {'ACK': bool(False), 'OVP': int(0), 'OCP': int(0),
                'Iset': float(0.0), 'Vset': float(0.0)}

    def configure(self, cfg: dict):
        '''
        Configures the device with the provided settings.
        Parameters:
        cfg (dict): A dictionary containing configuration settings.
        The dictionary should have the following keys:
            - 'ACK' (bool): Acknowledge alarms.
            - 'OCP' (float): Over-Current-Protection threshold.
            - 'OVP' (float): Over-Voltage-Protection threshold.
            - 'Vset' (float): Voltage setting.
            - 'Iset' (float): Current setting.
        The method sets the corresponding thresholds and settings for the
        device based on the provided configuration.
        '''
        if cfg['ACK'] is True:
            self.ack_alarm()

        if isinstance(cfg['OCP'], float):
            self.set_ocp(cfg['OCP'])

        if isinstance(cfg['OVP'], float):
            self.set_ovp(cfg['OVP'])

        if isinstance(cfg['Vset'], float):
            self.set_voltage(cfg['Vset'])

        if isinstance(cfg['Iset'], float):
            self.set_current(cfg['Iset'])

    def print_info(self):
        '''
        Get info from device and print it.
        '''
        dev_class_nr, dev_class_str = self.get_device_class()
        dev_state = self.get_actual()
        print(
            f'type    {self.get_type()}\n'
            f'serial  {self.get_serial()}\n'
            f'article {self.get_article()}\n'
            f'manuf   {self.get_manufacturer()}\n'
            f'version {self.get_version()}\n'
            f'nom. voltage {self.get_nominal_voltage()}\n'
            f'nom. current {self.get_nominal_current()}\n'
            f'nom. power   {self.get_nominal_power()}\n'
            f'class        {hex(dev_class_nr)} ({dev_class_str})\n'
            f'OVP          {self.get_ovp()}\n'
            f'OCP          {self.get_ocp()}\n'
            f'control      {self.get_control()}\n'
            f'state        {dev_state}'
        )


def main():
    parser = argparse.ArgumentParser(description=eaps2k.description())
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {eaps2k.pkg_version()}')
    parser.add_argument(
        '-p', '--port', type=str, help='serial port to use', required=True)

    default_voltage = None
    default_current = None
    parser.add_argument('-V', '--voltage', type=float, default=default_voltage,
                        required=False,
                        help=f'Voltage to be set. Nothing will be changed if None.'
                             f'(default: {default_voltage})')
    parser.add_argument('--ovp', type=float, default=default_voltage,
                        required=False,
                        help=f'OVP - Over-Voltage-Protection. '
                             f'Nothing will be changed if None.'
                             f'(default: {default_voltage})')
    parser.add_argument('-I', '--current', type=float, default=default_current,
                        required=False,
                        help=f'Current to be set. Nothing will be changed if None.'
                             f'(default: {default_current})')
    parser.add_argument('--ocp', type=float, default=default_current,
                        required=False,
                        help=f'OCP - Over-Current-Protection. '
                             f'Nothing will be changed if None.'
                             f'(default: {default_current})')

    group_verb = parser.add_mutually_exclusive_group(required=False)
    group_verb.add_argument('-v', dest='verbose', action='count', default=0,
                            help='increase verbosity level')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--on', help='turn on', action='store_true')
    group.add_argument('--off', help='turn off', action='store_true')
    group.add_argument('--toggle', help='toggle output on/off', action='store_true')
    group.add_argument('--info', help='print info and exit', action='store_true')
    group.add_argument('--ack', help='Acknowledge alarms', action='store_true')
    args = parser.parse_args()

    cfg = eaps2k.get_config_template()
    cfg['ACK'] = args.ack
    cfg['OVP'] = args.ovp
    cfg['OCP'] = args.ocp
    cfg['Iset'] = args.current
    cfg['Vset'] = args.voltage

    with eaps2k(args.port, verbosity_level=args.verbose) as ps:
        ps.configure(cfg)  # set configuration do nothing if value(s) is/are None
        if args.on:
            ps.set_output_state(True)
        elif args.off:
            ps.set_output_state(False)
        elif args.toggle:
            state = ps.get_output_state()
            ps.set_output_state(not state)
        elif args.info:
            ps.print_info()


if __name__ == '__main__':
    sys.exit(main())
