import logging
import os
import subprocess
import time

import yaml

_DEF_VAL = 'n/a'
_HP_SSA_CMD = '/usr/sbin/ssacli'
_INDENT = '   '
_STATUSES = ['OK', 'Warning', 'Critical', 'Unknown']


logger = logging.getLogger(__name__)


class SSAException(Exception):
    def __init__(self, **kwargs):
        super().__init__(self.message % kwargs)


class SSACmdError(SSAException):
    message = "Error exacuting ssacli command: %(error)s"


def _ssa_cmd(*args):
    cmd = [_HP_SSA_CMD] + list(args)

    _PIPE = subprocess.PIPE
    _DEVNULL = subprocess.DEVNULL

    new_environ = os.environ.copy()
    new_environ['LC_ALL'] = "C"

    try:
        logger.debug(f'SSACmd: {cmd}')
        obj = subprocess.Popen(
            cmd,
            stdin=_DEVNULL,
            stdout=_PIPE,
            stderr=_PIPE,
            env=new_environ)
    except Exception as exc:
        raise SSACmdError(error=exc)

    try:
        obj.wait()
    except Exception as exc:
        obj.stdout.close()
        raise SSACmdError(error=exc)

    out, err = obj.communicate()
    out = out.decode('utf-8').rstrip().lstrip()
    err = err.decode('utf-8').rstrip().lstrip()

    if obj.returncode != 0:
        error = f'stdout: {out}' if out else ''
        error += f'stderr: {err}' if err else ''
        raise SSACmdError(error=error)

    return out, err


def _indent(indents):
    depth = ""
    for _ in range(indents):
        depth += _INDENT
    return depth


def get_status_str(status):
    return _STATUSES[status]


class Controllers():
    PART_INFO_STR = 'Disk Partition Information'
    SEP_STR = 'SEP'

    def __init__(self, configFile=None):
        self._config_time = None
        self._controllers = []
        self.status = _STATUSES.index('OK')
        self._configFile = configFile

        self.update_controllers()

    def _update_configs_dict(self, configs_dict, master_key, line):
        key, value = self._get_key_and_value(line)
        if key in ('Port Name', 'Array', 'Unassigned'):
            master_key = (
                key.split(' ')[0]+'s'
                if key in ('Port Name', 'Array') else key)
            if master_key not in configs_dict:
                configs_dict[master_key] = []
            configs_dict[master_key].append({})
        elif key in ('Physical Drive', 'Logical Drive'):
            master_key = key+'s'
            if master_key not in configs_dict['Arrays'][-1]:
                configs_dict['Arrays'][-1][master_key] = []
            configs_dict['Arrays'][-1][master_key].append({})
        elif key == self.SEP_STR:
            configs_dict[key] = {}
            return key

        if master_key in ('Ports', 'Arrays', 'Unassigned'):
            configs_dict[master_key][-1][key] = value
        elif master_key in ('Logical Drives', 'Physical Drives'):
            if key == self.PART_INFO_STR:
                configs_dict['Arrays'][-1][master_key][-1][key] = {}
            elif key.startswith('Partition'):
                configs_dict['Arrays'][-1][master_key][-1][
                    self.PART_INFO_STR][key] = value
            else:
                configs_dict['Arrays'][-1][master_key][-1][key] = value
        elif master_key == self.SEP_STR:
            configs_dict[master_key][key] = value
        elif master_key == self.__class__.__name__:
            configs_dict[key] = value
        return master_key

    def _get_key_and_value(self, raw_config_line):
        line = raw_config_line.lstrip().rstrip()
        if line.startswith('physicaldrive'):
            line = line.replace('physicaldrive', 'Physical Drive:')
        elif line.startswith(self.SEP_STR):
            return self.SEP_STR, None
        elif line == self.PART_INFO_STR:
            return line, None
        data = line.split(':', 1)
        return data[0].rstrip(), data[1].lstrip()

    def _raw_configs_to_dict(self, raw_configs):
        lines = list(filter(None, raw_configs.split('\n')))
        master_key = self.__class__.__name__
        configs_dict = {master_key: []}

        for line in lines:
            # New controller found.
            if not line.startswith(' '):
                configs_dict[master_key].append(
                    {'Smart Array Type': line.split(' in')[0]})
                continue
            # New or updating section.
            master_key = self._update_configs_dict(
              configs_dict[self.__class__.__name__][-1],
              master_key,
              line)
        return configs_dict

    def _get_controllers_configs(self):
        raw, stderr = _ssa_cmd('ctrl', 'all', 'show', 'config', 'detail')
        configs_dict = self._raw_configs_to_dict(raw)
        if stderr:
            logger.warning(f'_ssc_cmd stderr: {stderr}')
            self.status = _STATUSES.index('Warning')
        return configs_dict

    def _load_ext_details(self, filename=None):
        try:
            with open(filename, 'r') as stream:
                return yaml.safe_load(stream)
        except (yaml.YAMLError, FileNotFoundError) as exc:
            logger.warning(exc)
        except TypeError:
            logger.warning('No Smart Array external config defined')
        return {}

    def update_controllers(self):
        ext_values = None
        self._config_time = time.time()
        configs_dict = self._get_controllers_configs()
        if self._configFile:
            ext_values = self._load_ext_details(self._configFile)
        for config_dict in configs_dict.pop(self.__class__.__name__, []):
            values = {}
            if ext_values:
                try:
                    type = config_dict.get('Smart Array Type', _DEF_VAL)
                    values = ext_values[type]
                except KeyError as exc:
                    logger.warning(
                        'Controller eternal config not '
                        f'found or invalid key: {exc}')
            self._controllers.append(Controller(config_dict, values))

    def _format_config_time(self):
        return (time.strftime('Updated At: %H:%M:%S %d-%m-%Y',
                time.localtime(self._config_time)))

    def is_ok(self, indent=0):
        description = ''
        status = self.status
        for controller in self._controllers:
            cont_status, cont_details = controller.is_ok()
            status = max(cont_status, status)
            description += f'{cont_details}\n\n'
        description += self._format_config_time()
        return status, description

    def simple_description(self, indent=0):
        description = ''
        for controller in self._controllers:
            description += f'{controller.simple_description(indent)}\n\n'
        description += self._format_config_time()
        return description


class Controller():
    def __init__(self, controller, values):
        self._arrays = [Array(array) for array in controller.pop('Arrays', [])]
        self._unassinged_physical_drives = [
            PhysicalDrive(drive) for drive in controller.pop('Unassigned', [])]
        self._details = controller
        self._ext_values = values

    def check_cache(self):
        if self._details.get(
                'Cache Board Present', 'false').lower() == 'false':
            return _STATUSES.index('OK')
        status = self._details.get('Cache Status', _DEF_VAL).lower()
        if status.startswith('ok'):
            return _STATUSES.index('OK')
        if status.startswith('failed'):
            return _STATUSES.index('Critical')
        if status.startswith('temporarily disabled'):
            return _STATUSES.index('Warning')
        return _STATUSES.index('Unknown')

    def check_cache_temperature(self):
        if self._details.get(
                'Cache Board Present', 'false').lower() == 'false':
            return _STATUSES.index('OK')
        try:
            current_temp = int(self._details.get(
                'Cache Module Temperature (C)',
                _DEF_VAL))
            max_temp = int(self._ext_values.get(
                'Cache Module Maximum Temperature (C)',
                _DEF_VAL))
        except ValueError as exc:
            logger.warning(exc)
            return _STATUSES.index('Unknown')
        if current_temp >= max_temp:
            return _STATUSES.index('Critical')
        if current_temp == (max_temp - 1):
            return _STATUSES.index('Warning')
        return _STATUSES.index('OK')

    def is_cache_ok(self, indent=0):
        if self._details.get(
                'Cache Board Present', 'false').lower() == 'false':
            return _STATUSES.index('OK'), ''
        temp = self.check_cache_temperature()
        status = max(self.check_cache(), temp)
        return status, (
            f'{_indent(indent)}'
            f'{_STATUSES[status]} - '
            f'{self.simple_cache_description(temperature=temp)}')

    def simple_cache_description(self, indent=0, temperature=None):
        if self._details.get(
                'Cache Board Present', 'false').lower() == 'false':
            return ''
        temp = (temperature if temperature is not None
                else self.check_cache_temperature())
        return (
            f'{_indent(indent)}Cache Status: '
            f"(SN: {self._details.get('Cache Serial Number', _DEF_VAL)}, "
            f'Temp: {_STATUSES[temp]}, '
            f"{self._details.get('Total Cache Size', _DEF_VAL)} GB, "
            f"{self._details.get('Cache Status', _DEF_VAL)})")

    def check_controller(self):
        status = self._details.get('Controller Status', _DEF_VAL).lower()
        if status.startswith('ok'):
            return _STATUSES.index('OK')
        if status.startswith('failed'):
            return _STATUSES.index('Critical')
        return _STATUSES.index('Unknown')

    def check_controller_temperature(self):
        try:
            current_temp = int(self._details.get(
                'Controller Temperature (C)',
                _DEF_VAL))
            max_temp = int(self._ext_values.get(
                'Controller Maximum Temperature (C)',
                _DEF_VAL))
        except ValueError as exc:
            logger.warning(exc)
            return _STATUSES.index('Unknown')
        if current_temp >= max_temp:
            return _STATUSES.index('Critical')
        if current_temp == (max_temp - 1):
            return _STATUSES.index('Warning')
        return _STATUSES.index('OK')

    def is_controller_ok(self, indent=0):
        temp = self.check_controller_temperature()
        status = max(self.check_controller(), temp)
        return status, (
            f'{_indent(indent)}'
            f'{_STATUSES[status]} - '
            f'{self.simple_controller_description(temperature=temp)}')

    def simple_controller_description(self, indent=0, temperature=None):
        temp = (temperature if temperature is not None
                else self.check_controller_temperature())
        return (
            f'{_indent(indent)}Controller Status: '
            f"(SN: {self._details.get('Serial Number', _DEF_VAL)}, "
            f'Temp: {_STATUSES[temp]}, '
            f"{self._details.get('Controller Status', _DEF_VAL)})")

    def check_battery_capacitor(self):
        status = self._details.get(
            'Battery/Capacitor Status', _DEF_VAL).lower()
        if status.startswith('ok'):
            return _STATUSES.index('OK')
        if status.startswith('failed'):
            return _STATUSES.index('Critical')
        if status.startswith('recharging'):
            return _STATUSES.index('Warning')
        return _STATUSES.index('Unknown')

    def check_battery_capacitor_temperature(self):
        if self._details.get(
                'Cache Board Present', 'false').lower() == 'false':
            return _STATUSES.index('OK')
        power_source = self._details.get(
            'Cache Backup Power Source',
            _DEF_VAL+' ')[:-1]
        try:
            power_source = self._details.get(
                'Cache Backup Power Source',
                _DEF_VAL+' ')[:-1]
            current_temp = int(self._details.get(
                power_source+' Temperature  (C)',
                _DEF_VAL))
            max_temp = int(self._ext_values.get(
                power_source+' Maximum Temperature (C)',
                _DEF_VAL))
        except ValueError as exc:
            logger.warning(exc)
            return _STATUSES.index('Unknown')
        if current_temp >= max_temp:
            return _STATUSES.index('Critical')
        if current_temp == (max_temp - 1):
            return _STATUSES.index('Warning')
        return _STATUSES.index('OK')

    def is_battery_capacitor_ok(self, indent=0):
        if self._details.get(
                'Cache Board Present', 'false').lower() == 'false':
            return ''
        temp = self.check_battery_capacitor_temperature()
        status = max(self.check_battery_capacitor(), temp)
        return status, (
            f'{_indent(indent)}'
            f'{_STATUSES[status]} - '
            f'{self.simple_battery_capacitor_description(temperature=temp)}')

    def simple_battery_capacitor_description(self, indent=0, temperature=None):
        if self._details.get(
                'Cache Board Present', 'false').lower() == 'false':
            return ''
        temp = (temperature if temperature is not None
                else self.check_battery_capacitor_temperature())
        source = self._details.get(
            'Cache Backup Power Source',
            _DEF_VAL+" ")[:-1]
        return (
            f'{_indent(indent)}Battery/Capacitor Status: '
            f'(Temp: {_STATUSES[temp]}, '
            f'Source: {source}, '
            f"{self._details.get('Battery/Capacitor Status', _DEF_VAL)})")

    def is_ok(self, indent=0):
        description = self._simple_description(indent)
        status, con_details = self.is_controller_ok(indent+1)
        description += f'\n{con_details}'
        cache_status, cache_details = self.is_cache_ok(indent+1)
        if cache_details:
            status = max(cache_status, status)
            description += f'\n{cache_details}'
        bc_status, bc_details = self.is_battery_capacitor_ok(indent+1)
        if bc_details:
            status = max(bc_status, status)
            description += f'\n{bc_details}'
        for unassinged_drive in self._unassinged_physical_drives:
            upd_status, upd_details = unassinged_drive.is_ok(indent+1)
            status = max(upd_status, status)
            description += f'\nUnassinged:\n{upd_details}'
        for array in self._arrays:
            a_status, a_details = array.is_ok(indent+1)
            status = max(a_status, status)
            description += f'\n{a_details}'
        return status, description

    def _simple_description(self, indent=0):
        return (
            f'{_indent(indent)}'
            f"{self._details.get('Smart Array Type', _DEF_VAL)} in "
            f"Slot {self._details.get('Slot', _DEF_VAL)}: "
            f"(Host SN: {self._details.get('Host Serial Number', _DEF_VAL)})")

    def simple_description(self, indent=0):
        description = (
            f'{self._simple_description(indent)}'
            f'\n{self.simple_controller_description(indent+1)}')
        c_details = self.simple_cache_description(indent+1)
        if c_details:
            description += f'\n{c_details}'
        bc_details = self.simple_battery_capacitor_description(indent+1)
        if bc_details:
            description += f'\n{bc_details}'
        for unassinged_drive in self._unassinged_physical_drives:
            description += (
                f'\nUnassinged:'
                f'\n{unassinged_drive.simple_description(indent+1)}')
        for array in self._arrays:
            description += f'\n{array.simple_description(indent+1)}'
        return description


class Array():
    def __init__(self, array):
        self._physical_drives = [
            PhysicalDrive(pd) for pd in array.pop('Physical Drives', [])]
        self._logical_drives = [
            LogicalDrive(ld) for ld in array.pop('Logical Drives', [])]
        self._details = array

    def check_status(self):
        status = self._details.get('Status', _DEF_VAL).lower()
        if status.startswith('ok'):
            return _STATUSES.index('OK')
        if status.startswith('failed'):
            return _STATUSES.index('Critical')
        return _STATUSES.index('Unknown')

    def is_ok(self, indent=0):
        status = self.check_status()
        description = (
            f'{_indent(indent)}'
            f'{_STATUSES[status]} - {self._simple_description()}')
        for logical_drive in self._logical_drives:
            ld_status, ld_details = logical_drive.is_ok(indent+1)
            status = max(ld_status, status)
            description += f'\n{ld_details}'
        for physical_drive in self._physical_drives:
            pd_status, pd_details = physical_drive.is_ok(indent+1)
            status = max(pd_status, status)
            description += f'\n{pd_details}'
        return status, description

    def _simple_description(self, indent=0):
        return (
            f"{_indent(indent)}"
            f"Array {self._details.get('Array', _DEF_VAL)} "
            f"({self._details.get('Interface Type', _DEF_VAL)}, "
            'Unused Space: '
            f"{self._details.get('Unused Space', _DEF_VAL).split(' (')[0]}, "
            f"{self._details.get('Status', _DEF_VAL)})")

    def simple_description(self, indent=0):
        description = self._simple_description(indent)
        for logical_drive in self._logical_drives:
            description += f'\n{logical_drive.simple_description(indent+1)}'
        for physical_drive in self._physical_drives:
            description += f'\n{physical_drive.simple_description(indent+1)}'
        return description


class LogicalDrive():
    def __init__(self, ld):
        self._details = ld

    def check_status(self):
        status = self._details.get('Status', _DEF_VAL).lower()
        if status.startswith('ok'):
            return _STATUSES.index('OK')
        if status.startswith('failed'):
            return _STATUSES.index('Critical')
        if (status.startswith('recovering') or
            status.startswith('transforming') or
                status.startswith('waiting')):
            return _STATUSES.index('Warning')
        return _STATUSES.index('Unknown')

    def is_ok(self, indent=0):
        status = self.check_status()
        return status, (
            f'{_indent(indent)}'
            f'{_STATUSES[status]} - {self.simple_description()}')

    def simple_description(self, indent=0):
        return (
            f'{_indent(indent)}Logical Drive: '
            f"{self._details.get('Logical Drive', _DEF_VAL)} "
            f"({self._details.get('Disk Name', _DEF_VAL)}, "
            f"{self._details.get('Size', _DEF_VAL)}, "
            f"RAID {self._details.get('Fault Tolerance', _DEF_VAL)}, "
            f"{self._details.get('Status', _DEF_VAL)})")


class PhysicalDrive():
    def __init__(self, pd):
        self._details = pd

    def check_status(self):
        status = self._details.get('Status', _DEF_VAL).lower()
        if status.startswith('ok'):
            return _STATUSES.index('OK')
        if status.startswith('failed'):
            return _STATUSES.index('Critical')
        if (status.startswith('rebuilding') or
                status.startwit('predictive failure')):
            return _STATUSES.index('Warning')
        return _STATUSES.index('Unknown')

    def check_temperature(self):
        try:
            current_temp = int(self._details.get(
                'Current Temperature (C)',
                _DEF_VAL))
            max_temp = int(self._details.get(
                'Maximum Temperature (C)',
                _DEF_VAL))
        except ValueError as exc:
            logger.warning(exc)
            return _STATUSES.index('Unknown')
        if current_temp >= max_temp:
            return _STATUSES.index('Critical')
        if current_temp == (max_temp - 1):
            return _STATUSES.index('Warning')
        return _STATUSES.index('OK')

    def is_ok(self, indent=0):
        temp = self.check_temperature()
        status = max(self.check_status(), temp)
        return status, (
            f'{_indent(indent)}'
            f'{_STATUSES[status]} - '
            f'{self.simple_description(temperature=temp)}')

    def simple_description(self, indent=0, temperature=None):
        temp = (temperature if temperature is not None
                else self.check_temperature())
        drive_type = self._details.get('Interface Type', _DEF_VAL)
        if drive_type.lower().startswith('solid state '):
            drive_type = f'{drive_type[12:]} SSD'
        elif drive_type.lower().startswith('ssd'):
            drive_type = f'{drive_type[:-3]} SSD'
        elif drive_type != _DEF_VAL:
            drive_type += ' HDD'
        return (
            f'{_indent(indent)}Physical Drive: '
            f"{self._details.get('Physical Drive', _DEF_VAL)} "
            f"(SN: {self._details.get('Serial Number', _DEF_VAL)}, "
            f'Temp: {_STATUSES[temp]}, '
            f"port {self._details.get('Port', _DEF_VAL)}:"
            f"box {self._details.get('Box', _DEF_VAL)}:"
            f"bay {self._details.get('Bay', _DEF_VAL)}, "
            f'{drive_type}, '
            f"{self._details.get('Size', _DEF_VAL)}, "
            f"{self._details.get('Status', _DEF_VAL)})")
