import os
import sys

import click
from tabulate import tabulate
import utilities_common.cli as clicommon

#
# 'system-health' command ("show system-health")
#
@click.group(name='system-health', cls=clicommon.AliasedGroup)
def system_health():
    """Show system-health information"""
    return

@system_health.command()
def summary():
    """Show system-health summary information"""
    # Mock the redis for unit test purposes #
    try:
        if os.environ["UTILITIES_UNIT_TESTING"] == "1":
            modules_path = os.path.join(os.path.dirname(__file__), "..")
            sys.path.insert(0, modules_path)
            from tests.system_health_test import MockerManager
            from tests.system_health_test import MockerChassis
            HealthCheckerManager = MockerManager
            Chassis = MockerChassis
    except Exception:
        # Normal run... #
        if os.geteuid():
            click.echo("Root privileges are required for this operation")
            return
        from health_checker.manager import HealthCheckerManager
        from sonic_platform.chassis import Chassis

    manager = HealthCheckerManager()
    if not manager.config.config_file_exists():
        click.echo("System health configuration file not found, exit...")
        return
    chassis = Chassis()
    stat = manager.check(chassis)
    chassis.initizalize_system_led()
    led = chassis.get_status_led()
    click.echo("System status summary\n\n  System status LED  " + led)
    services_list = []
    fs_list = []
    device_list =[]
    for category, elements in stat.items():
        for element in elements:
            if elements[element]['status'] != "OK":
                if 'Running' in elements[element]['message']:
                    services_list.append(element)
                elif 'Accessible' in elements[element]['message']:
                    fs_list.append(element)
                else:
                    device_list.append(elements[element]['message'])
    if len(services_list) or len(fs_list):
        click.echo("  Services:\n    Status: Not OK")
    else:
        click.echo("  Services:\n    Status: OK")
    if len(services_list):
        services_list_string = str(services_list)
        click.echo("    Not Running: " + services_list_string.replace("[", "").replace(']', ""))
    if len(fs_list):
        fs_list_string = str(fs_list)
        click.echo("    Not Accessible: " + fs_list_string.replace("[", "").replace(']', ""))
    if len(device_list):
        click.echo("  Hardware:\n    Status: Not OK")
        click.echo("    Reasons: " + device_list.pop())
        while len(device_list):
            click.echo("\t     " + device_list.pop())
    else:
        click.echo("  Hardware:\n    Status: OK")

@system_health.command()
def detail():
    """Show system-health detail information"""
    # Mock the redis for unit test purposes #
    try:
        if os.environ["UTILITIES_UNIT_TESTING"] == "1":
            modules_path = os.path.join(os.path.dirname(__file__), "..")
            sys.path.insert(0, modules_path)
            from tests.system_health_test import MockerManager
            from tests.system_health_test import MockerChassis
            HealthCheckerManager = MockerManager
            Chassis = MockerChassis
    except Exception:
        # Normal run... #
        if os.geteuid():
            click.echo("Root privileges are required for this operation")
            return
        from health_checker.manager import HealthCheckerManager
        from sonic_platform.chassis import Chassis

    manager = HealthCheckerManager()
    if not manager.config.config_file_exists():
        click.echo("System health configuration file not found, exit...")
        return
    chassis = Chassis()
    stat = manager.check(chassis)
    #summary output
    chassis.initizalize_system_led()
    led = chassis.get_status_led()
    click.echo("System status summary\n\n  System status LED  " + led)
    services_list = []
    fs_list = []
    device_list =[]
    for category, elements in stat.items():
        for element in elements:
            if elements[element]['status'] != "OK":
                if 'Running' in elements[element]['message']:
                    services_list.append(element)
                elif 'Accessible' in elements[element]['message']:
                    fs_list.append(element)
                else:
                    device_list.append(elements[element]['message'])
    if len(services_list) or len(fs_list):
        click.echo("  Services:\n    Status: Not OK")
    else:
        click.echo("  Services:\n    Status: OK")
    if len(services_list):
        services_list_string = str(services_list)
        click.echo("    Not Running: " + services_list_string.replace("[", "").replace(']', ""))
    if len(fs_list):
        fs_list_string = str(fs_list)
        click.echo("    Not Accessible: " + fs_list_string.replace("[", "").replace(']', ""))
    if len(device_list):
        click.echo("  Hardware:\n    Status: Not OK")
        click.echo("    Reasons: " + device_list.pop())
        while len(device_list):
            click.echo("\t     " + device_list.pop())
    else:
        click.echo("  Hardware:\n    Status: OK")

    click.echo('\nSystem services and devices monitor list\n')
    header = ['Name', 'Status', 'Type']
    table = []
    for category, elements in stat.items():
        for element in sorted(elements.items(), key=lambda x: x[1]['status']):
            entry = []
            entry.append(element[0])
            entry.append(element[1]['status'])
            entry.append(element[1]['type'])
            table.append(entry)
    click.echo(tabulate(table, header))
    click.echo('\nSystem services and devices ignore list\n')
    table = []
    if manager.config.ignore_services:
        for element in manager.config.ignore_services:
            entry = []
            entry.append(element)
            entry.append("Ignored")
            entry.append("Service")
            table.append(entry)
    if manager.config.ignore_devices:
        for element in manager.config.ignore_devices:
            entry = []
            entry.append(element)
            entry.append("Ignored")
            entry.append("Device")
            table.append(entry)
    click.echo(tabulate(table, header))

@system_health.command()
def monitor_list():
    """Show system-health monitored services and devices name list"""
    # Mock the redis for unit test purposes #
    try:
        if os.environ["UTILITIES_UNIT_TESTING"] == "1":
            modules_path = os.path.join(os.path.dirname(__file__), "..")
            sys.path.insert(0, modules_path)
            from tests.system_health_test import MockerManager
            from tests.system_health_test import MockerChassis
            HealthCheckerManager = MockerManager
            Chassis = MockerChassis
    except Exception:
        # Normal run... #
        if os.geteuid():
            click.echo("Root privileges are required for this operation")
            return
        from health_checker.manager import HealthCheckerManager
        from sonic_platform.chassis import Chassis

    manager = HealthCheckerManager()
    if not manager.config.config_file_exists():
        click.echo("System health configuration file not found, exit...")
        return
    chassis = Chassis()
    stat = manager.check(chassis)
    click.echo('\nSystem services and devices monitor list\n')
    header = ['Name', 'Status', 'Type']
    table = []
    for category, elements in stat.items():
        for element in sorted(elements.items(), key=lambda x: x[1]['status']):
            entry = []
            entry.append(element[0])
            entry.append(element[1]['status'])
            entry.append(element[1]['type'])
            table.append(entry)
    click.echo(tabulate(table, header))
