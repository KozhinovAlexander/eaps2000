'''
Unit tests for eaps2000 module.

These tests avoid real serial hardware by patching low-level methods.

@NOTE: Thie section is mostly vibe-coded.
'''

import os
import pytest
import eaps2000 as eaps2k_module
from eaps2000 import eaps2k


@pytest.fixture(scope='session')
def hw_port():
    run_hw = os.getenv('EAPS2000_RUN_HW_TESTS', '').lower()
    if run_hw not in {'1', 'true', 'yes'}:
        pytest.skip('Hardware tests disabled. Set EAPS2000_RUN_HW_TESTS=1 to enable.')

    port = os.getenv('EAPS2000_TEST_PORT')
    if not port:
        pytest.skip('Set EAPS2000_TEST_PORT to the serial port, e.g. /dev/ttyACM0.')
    return port


@pytest.fixture()
def hw_psu(hw_port):
    try:
        with eaps2k(hw_port) as ps:
            yield ps
    except Exception as exc:
        pytest.skip(f'Hardware not reachable on {hw_port}: {exc}')


@pytest.fixture(scope='session')
def hw_interactive_enabled():
    enabled = os.getenv('EAPS2000_HW_INTERACTIVE_CONFIRM', '').lower()
    if enabled not in {'1', 'true', 'yes'}:
        pytest.skip(
            'Interactive hardware confirmations disabled. '
            'Set EAPS2000_HW_INTERACTIVE_CONFIRM=1 and run with -s.'
        )
    return True


def _confirm_expected(prompt):
    try:
        answer = input(f'{prompt} [y/N]: ').strip().lower()
    except EOFError:
        pytest.fail('No interactive input available. Re-run with pytest -s.')

    assert answer in {'y', 'yes'}, f'User did not confirm expected state: {prompt}'


def _new_psu(u_nom=42.0, i_nom=6.0):
    ps = eaps2k.__new__(eaps2k)
    ps._translation_factor = 25600.0
    ps._u_nom = u_nom
    ps._i_nom = i_nom
    ps._verbosity_lvl = 0
    return ps


def test_description_contains_license():
    descr = eaps2k.description()
    assert 'License: Apache 2.0' in descr


def test_bytes2hex_uses_two_digit_hex():
    assert eaps2k.bytes2hex(bytes([0, 1, 15, 255])) == '00 01 0f ff'


def test_construct_telegram_without_data():
    telegram = eaps2k._construct_telegram(eaps2k.PS_QUERY, 0, 19, [])
    assert telegram == bytearray([0x70, 0x00, 0x13, 0x00, 0x83])


def test_construct_telegram_with_data_updates_length_and_checksum():
    telegram = eaps2k._construct_telegram(eaps2k.PS_SEND, 0, 54, [0x01, 0x00])
    # SD starts at 0x30 + 0xc0 = 0xf0 and increments by len(data)-1 => 0xf1
    assert telegram == bytearray([0xF1, 0x00, 0x36, 0x01, 0x00, 0x01, 0x28])


def test_checksum_verify_ok_and_fail():
    ok = bytes([0x70, 0x00, 0x13, 0x00, 0x83])
    eaps2k._checksum_verify(ok)

    bad = bytes([0x70, 0x00, 0x13, 0x00, 0x84])
    with pytest.raises(AssertionError, match='Checksum mismatch'):
        eaps2k._checksum_verify(bad)


def test_check_error_non_error_and_acknowledge_are_ok():
    # Non-error because ans[2] != 0xff
    eaps2k._check_error(bytes([0x71, 0x00, 0x13, 0x00, 0x84]))
    # Acknowledge response (0xff, 0x00) is also allowed
    eaps2k._check_error(bytes([0xF1, 0x00, 0xFF, 0x00, 0x00]))


def test_check_error_raises_known_message():
    ans = bytes([0xF1, 0x00, 0xFF, 0x30, 0x00])
    with pytest.raises(AssertionError, match='Upper limit exceeded'):
        eaps2k._check_error(ans)


def test_conversion_helpers_roundtrip():
    ps = _new_psu(u_nom=42.0)
    percent = ps.real2percent(42.0, 3.3)
    assert percent == pytest.approx(2011.4285714286)
    assert ps.percent2real(42.0, percent) == pytest.approx(3.3)


def test_get_device_class_known_and_unknown(monkeypatch):
    ps = _new_psu()
    monkeypatch.setattr(ps, '_read_obj', lambda obj, typ=int: 0x0010)
    assert ps.get_device_class() == (0x0010, 'PS 2000 B Single')

    monkeypatch.setattr(ps, '_read_obj', lambda obj, typ=int: 0x1234)
    assert ps.get_device_class() == (0x1234, 'unknown')


def test_get_control_decodes_output_and_remote(monkeypatch):
    ps = _new_psu()
    monkeypatch.setattr(ps, '_read_obj', lambda obj: b'\x01\x01')
    control = ps.get_control()
    assert control == {'output_on': True, 'remote': True}


def test_set_remote_and_output_masks(monkeypatch):
    ps = _new_psu()
    calls = []

    def fake_set_control(mask, data):
        calls.append((mask, data))
        return True

    monkeypatch.setattr(ps, '_set_control', fake_set_control)

    assert ps.set_remote(True) is True
    assert ps.set_remote(False) is True
    assert ps.set_output_state(True) is True
    assert ps.set_output_state(False) is True
    assert ps.ack_alarm() is True

    assert calls == [
        (0x10, 0x10),
        (0x10, 0x00),
        (0x01, 0x01),
        (0x01, 0x00),
        (0x0A, 0x0A),
    ]


def test_get_actual_decodes_flags_and_values(monkeypatch):
    ps = _new_psu(u_nom=42.0, i_nom=6.0)
    # Byte0 remote set; Byte1: on + CC + OVP
    # Voltage word = 256, Current word = 128
    monkeypatch.setattr(ps, '_read_obj', lambda obj: b'\x01\x13\x01\x00\x00\x80')
    actual = ps.get_actual()

    assert actual['remote'] is True
    assert actual['on'] is True
    assert actual['CC'] is True
    assert actual['CV'] is False
    assert actual['OVP'] is True
    assert actual['OCP'] is False
    assert actual['V'] == pytest.approx(0.42)
    assert actual['I'] == pytest.approx(0.03)


def test_configure_calls_only_expected_setters(monkeypatch):
    ps = _new_psu()
    called = []

    monkeypatch.setattr(ps, 'ack_alarm', lambda: called.append(('ACK', None)))
    monkeypatch.setattr(ps, 'set_ocp', lambda v: called.append(('OCP', v)))
    monkeypatch.setattr(ps, 'set_ovp', lambda v: called.append(('OVP', v)))
    monkeypatch.setattr(ps, 'set_voltage', lambda v: called.append(('Vset', v)))
    monkeypatch.setattr(ps, 'set_current', lambda v: called.append(('Iset', v)))

    cfg = {
        'ACK': True,
        'OCP': 0.5,
        'OVP': 5.0,
        'Vset': 3.3,
        'Iset': 0.1,
    }
    ps.configure(cfg)

    assert called == [
        ('ACK', None),
        ('OCP', 0.5),
        ('OVP', 5.0),
        ('Vset', 3.3),
        ('Iset', 0.1),
    ]


def test_config_template_structure():
    cfg = eaps2k.get_config_template()
    assert set(cfg.keys()) == {'ACK', 'OVP', 'OCP', 'Iset', 'Vset'}
    assert isinstance(cfg['ACK'], bool)


def test_main_toggle_flow(monkeypatch):
    class FakePS:
        last_instance = None

        @staticmethod
        def description():
            return 'fake'

        @staticmethod
        def pkg_version():
            return '0.0.0-test'

        @staticmethod
        def get_config_template():
            return {'ACK': False, 'OVP': 0, 'OCP': 0, 'Iset': 0.0, 'Vset': 0.0}

        def __init__(self, port, channel=0, verbosity_level=0):
            self.port = port
            self.channel = channel
            self.verbosity_level = verbosity_level
            self.configured = None
            self.output_state = True
            self.toggled_to = None
            FakePS.last_instance = self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def configure(self, cfg):
            self.configured = cfg

        def get_output_state(self):
            return self.output_state

        def set_output_state(self, state):
            self.toggled_to = state

        def print_info(self):
            raise AssertionError('print_info should not be called for --toggle')

    monkeypatch.setattr(eaps2k_module, 'eaps2k', FakePS)
    monkeypatch.setattr(
        eaps2k_module.sys,
        'argv',
        ['eaps2000', '-p', 'COM123', '--toggle', '-V', '3.3', '-I', '0.2'],
    )

    eaps2k_module.main()

    ps = FakePS.last_instance
    assert ps is not None
    assert ps.configured['Vset'] == 3.3
    assert ps.configured['Iset'] == 0.2
    # Initial state True should toggle to False.
    assert ps.toggled_to is False


@pytest.mark.hardware
def test_hw_identity_fields_non_empty(hw_psu):
    assert isinstance(hw_psu.get_type(), str) and hw_psu.get_type().strip()
    assert isinstance(hw_psu.get_serial(), str) and hw_psu.get_serial().strip()
    assert isinstance(hw_psu.get_article(), str) and hw_psu.get_article().strip()
    assert isinstance(hw_psu.get_manufacturer(), str) and hw_psu.get_manufacturer().strip()
    assert isinstance(hw_psu.get_version(), str) and hw_psu.get_version().strip()


@pytest.mark.hardware
def test_hw_nominal_values_are_positive(hw_psu):
    assert hw_psu.get_nominal_voltage() > 0.0
    assert hw_psu.get_nominal_current() > 0.0
    assert hw_psu.get_nominal_power() > 0.0


@pytest.mark.hardware
def test_hw_control_and_status_have_expected_shape(hw_psu):
    control = hw_psu.get_control()
    assert set(control.keys()) == {'output_on', 'remote'}
    assert isinstance(control['output_on'], bool)
    assert isinstance(control['remote'], bool)

    actual = hw_psu.get_actual()
    assert {'remote', 'on', 'CC', 'CV', 'tracking', 'OVP', 'OCP', 'OPP', 'OTP', 'V', 'I'} <= set(actual.keys())
    assert isinstance(actual['V'], float)
    assert isinstance(actual['I'], float)


@pytest.mark.hardware
def test_hw_set_remote_roundtrip(hw_psu):
    initial_remote = hw_psu.get_remote()
    try:
        ret_true = hw_psu.set_remote(True)
        assert isinstance(ret_true, bool)
        assert hw_psu.get_remote() is True

        ret_false = hw_psu.set_remote(False)
        assert isinstance(ret_false, bool)
        assert hw_psu.get_remote() is False
    finally:
        hw_psu.set_remote(initial_remote)


@pytest.mark.hardware
def test_hw_ack_alarm_returns_bool(hw_psu):
    assert isinstance(hw_psu.ack_alarm(), bool)


@pytest.mark.hardware
@pytest.mark.hardware_interactive
def test_hw_interactive_set_voltage_current_and_output(hw_psu, hw_interactive_enabled):
    initial_output = hw_psu.get_output_state()
    initial_setpoints = hw_psu.get_setpoints()

    # Conservative targets for manual checks on most lab setups.
    target_v = round(max(0.1, min(hw_psu._u_nom * 0.2, 5.0)), 2)
    target_i = round(max(0.05, min(hw_psu._i_nom * 0.1, 1.0)), 2)

    try:
        hw_psu.set_output_state(False)
        assert hw_psu.get_output_state() is False
        _confirm_expected('Confirm PSU output is OFF on the front panel')

        hw_psu.set_voltage(target_v)
        setpoints = hw_psu.get_setpoints()
        assert setpoints['V'] == pytest.approx(target_v, abs=0.05)
        _confirm_expected(
            f'Confirm PSU voltage setpoint is about {target_v:.2f} V on the front panel'
        )

        hw_psu.set_current(target_i)
        setpoints = hw_psu.get_setpoints()
        assert setpoints['I'] == pytest.approx(target_i, abs=0.05)
        _confirm_expected(
            f'Confirm PSU current setpoint is about {target_i:.2f} A on the front panel'
        )

        _confirm_expected('Confirm it is safe to energize the output now')
        hw_psu.set_output_state(True)
        assert hw_psu.get_output_state() is True
        _confirm_expected('Confirm PSU output is ON on the front panel')

        hw_psu.set_output_state(False)
        assert hw_psu.get_output_state() is False
        _confirm_expected('Confirm PSU output is OFF again on the front panel')
    finally:
        hw_psu.set_voltage(float(initial_setpoints['V']))
        hw_psu.set_current(float(initial_setpoints['I']))
        hw_psu.set_output_state(initial_output)
