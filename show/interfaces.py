import json

import click
from natsort import natsorted
from tabulate import tabulate

import utilities_common.cli as clicommon

def try_convert_interfacename_from_alias(ctx, db, interfacename):
    """try to convert interface name from alias"""

    if clicommon.get_interface_naming_mode() == "alias":
        alias = interfacename
        interfacename = clicommon.InterfaceAliasConverter(db).alias_to_name(alias)
        # TODO: ideally alias_to_name should return None when it cannot find
        # the port name for the alias
        if interfacename == alias:
            ctx.fail("cannot find interface name for alias {}".format(alias))

    return interfacename

#
# 'interfaces' group ("show interfaces ...")
#
@click.group(cls=clicommon.AliasedGroup)
def interfaces():
    """Show details of the network interfaces"""
    pass

# 'alias' subcommand ("show interfaces alias")
@interfaces.command()
@click.argument('interfacename', required=False)
@clicommon.pass_db
def alias(db, interfacename):
    """Show Interface Name/Alias Mapping"""

    ctx = click.get_current_context()

    port_dict = db.cfgdb.get_table("PORT")

    header = ['Name', 'Alias']
    body = []

    if interfacename is not None:
        interfacename = try_convert_interfacename_from_alias(ctx, db, interfacename)

        # If we're given an interface name, output name and alias for that interface only
        if interfacename in port_dict.keys():
            if port_dict[interfacename].has_key('alias'):
                body.append([interfacename, port_dict[interfacename]['alias']])
            else:
                body.append([interfacename, interfacename])
        else:
            ctx.fail("Invalid interface name {}".format(interfacename))
    else:
        # Output name and alias for all interfaces
        for port_name in natsorted(port_dict.keys()):
            if 'alias' in port_dict[port_name]:
                body.append([port_name, port_dict[port_name]['alias']])
            else:
                body.append([port_name, port_name])

    click.echo(tabulate(body, header))

@interfaces.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def description(db, interfacename, verbose):
    """Show interface status, protocol and description"""

    ctx = click.get_current_context()

    cmd = "intfutil description"

    if interfacename is not None:
        interfacename = try_convert_interfacename_from_alias(ctx, db, interfacename)

        cmd += " {}".format(interfacename)

    clicommon.run_command(cmd, display_cmd=verbose)

# 'naming_mode' subcommand ("show interfaces naming_mode")
@interfaces.command('naming_mode')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def naming_mode(verbose):
    """Show interface naming_mode status"""

    click.echo(clicommon.get_interface_naming_mode())

# 'portchannel' subcommand ("show interfaces portchannel")
@interfaces.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def portchannel(verbose):
    """Show PortChannel information"""
    cmd = "sudo teamshow"
    clicommon.run_command(cmd, display_cmd=verbose)

@interfaces.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def status(db, interfacename, verbose):
    """Show Interface status information"""

    ctx = click.get_current_context()

    cmd = "intfutil status"

    if interfacename is not None:
        interfacename = try_convert_interfacename_from_alias(ctx, db, interfacename)

        cmd += " {}".format(interfacename)

    clicommon.run_command(cmd, display_cmd=verbose)

#
# 'breakout' group ###
#
@interfaces.group(invoke_without_command=True)
@click.pass_context
def breakout(ctx):
    """Show Breakout Mode information by interfaces"""
    # Reading data from Redis configDb
    config_db = ConfigDBConnector()
    config_db.connect()
    ctx.obj = {'db': config_db}

    try:
        cur_brkout_tbl = config_db.get_table('BREAKOUT_CFG')
    except Exception as e:
        click.echo("Breakout table is not present in Config DB")
        raise click.Abort()

    if ctx.invoked_subcommand is None:
        # Get port capability from platform and hwsku related files
        platform_path, hwsku_path = device_info.get_paths_to_platform_and_hwsku_dirs()
        platform_file = os.path.join(platform_path, PLATFORM_JSON)
        platform_dict = readJsonFile(platform_file)['interfaces']
        hwsku_dict = readJsonFile(os.path.join(hwsku_path, HWSKU_JSON))['interfaces']

        if not platform_dict or not hwsku_dict:
            click.echo("Can not load port config from {} or {} file".format(PLATFORM_JSON, HWSKU_JSON))
            raise click.Abort()

        for port_name in platform_dict.keys():
            cur_brkout_mode = cur_brkout_tbl[port_name]["brkout_mode"]

            # Update deafult breakout mode and current breakout mode to platform_dict
            platform_dict[port_name].update(hwsku_dict[port_name])
            platform_dict[port_name]["Current Breakout Mode"] = cur_brkout_mode

            # List all the child ports if present
            child_port_dict = get_child_ports(port_name, cur_brkout_mode, platformFile)
            if not child_port_dict:
                click.echo("Cannot find ports from {} file ".format(PLATFORM_JSON))
                raise click.Abort()

            child_ports = natsorted(child_port_dict.keys())

            children, speeds = [], []
            # Update portname and speed of child ports if present
            for port in child_ports:
                speed = config_db.get_entry('PORT', port).get('speed')
                if speed is not None:
                    speeds.append(str(int(speed)//1000)+'G')
                    children.append(port)

            platform_dict[port_name]["child ports"] = ",".join(children)
            platform_dict[port_name]["child port speeds"] = ",".join(speeds)

        # Sorted keys by name in natural sort Order for human readability
        parsed = OrderedDict((k, platform_dict[k]) for k in natsorted(platform_dict.keys()))
        click.echo(json.dumps(parsed, indent=4))

# 'breakout current-mode' subcommand ("show interfaces breakout current-mode")
@breakout.command('current-mode')
@click.argument('interface', metavar='<interface_name>', required=False, type=str)
@click.pass_context
def currrent_mode(ctx, interface):
    """Show current Breakout mode Info by interface(s)"""

    config_db = ctx.obj['db']

    header = ['Interface', 'Current Breakout Mode']
    body = []

    try:
        cur_brkout_tbl = config_db.get_table('BREAKOUT_CFG')
    except Exception as e:
        click.echo("Breakout table is not present in Config DB")
        raise click.Abort()

    # Show current Breakout Mode of user prompted interface
    if interface is not None:
        body.append([interface, str(cur_brkout_tbl[interface]['brkout_mode'])])
        click.echo(tabulate(body, header, tablefmt="grid"))
        return

    # Show current Breakout Mode for all interfaces
    for name in natsorted(cur_brkout_tbl.keys()):
        body.append([name, str(cur_brkout_tbl[name]['brkout_mode'])])
    click.echo(tabulate(body, header, tablefmt="grid"))

#
# 'neighbor' group ###
#
@interfaces.group(cls=clicommon.AliasedGroup)
def neighbor():
    """Show neighbor related information"""
    pass

# 'expected' subcommand ("show interface neighbor expected")
@neighbor.command()
@click.argument('interfacename', required=False)
@clicommon.pass_db
def expected(db, interfacename):
    """Show expected neighbor information by interfaces"""

    neighbor_dict = db.cfgdb.get_table("DEVICE_NEIGHBOR")
    if neighbor_dict is None:
        click.echo("DEVICE_NEIGHBOR information is not present.")
        return

    neighbor_metadata_dict = db.cfgdb.get_table("DEVICE_NEIGHBOR_METADATA")
    if neighbor_metadata_dict is None:
        click.echo("DEVICE_NEIGHBOR_METADATA information is not present.")
        return

    #Swap Key and Value from interface: name to name: interface
    device2interface_dict = {}
    for port in natsorted(neighbor_dict.keys()):
        temp_port = port
        if clicommon.get_interface_naming_mode() == "alias":
            port = clicommon.InterfaceAliasConverter(db).name_to_alias(port)
            neighbor_dict[port] = neighbor_dict.pop(temp_port)
        device2interface_dict[neighbor_dict[port]['name']] = {'localPort': port, 'neighborPort': neighbor_dict[port]['port']}

    header = ['LocalPort', 'Neighbor', 'NeighborPort', 'NeighborLoopback', 'NeighborMgmt', 'NeighborType']
    body = []
    if interfacename:
        for device in natsorted(neighbor_metadata_dict.keys()):
            if device2interface_dict[device]['localPort'] == interfacename:
                body.append([device2interface_dict[device]['localPort'],
                             device,
                             device2interface_dict[device]['neighborPort'],
                             neighbor_metadata_dict[device]['lo_addr'],
                             neighbor_metadata_dict[device]['mgmt_addr'],
                             neighbor_metadata_dict[device]['type']])
        if len(body) == 0:
            click.echo("No neighbor information available for interface {}".format(interfacename))
            return
    else:
        for device in natsorted(neighbor_metadata_dict.keys()):
            body.append([device2interface_dict[device]['localPort'],
                         device,
                         device2interface_dict[device]['neighborPort'],
                         neighbor_metadata_dict[device]['lo_addr'],
                         neighbor_metadata_dict[device]['mgmt_addr'],
                         neighbor_metadata_dict[device]['type']])

    click.echo(tabulate(body, header))

#
# transceiver group (show interfaces trasceiver ...)
#
@interfaces.group(cls=clicommon.AliasedGroup)
def transceiver():
    """Show SFP Transceiver information"""
    pass

@transceiver.command()
@click.argument('interfacename', required=False)
@click.option('-d', '--dom', 'dump_dom', is_flag=True, help="Also display Digital Optical Monitoring (DOM) data")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def eeprom(db, interfacename, dump_dom, verbose):
    """Show interface transceiver EEPROM information"""

    ctx = click.get_current_context()

    cmd = "sfpshow eeprom"

    if dump_dom:
        cmd += " --dom"

    if interfacename is not None:
        interfacename = try_convert_interfacename_from_alias(ctx, db, interfacename)

        cmd += " -p {}".format(interfacename)

    clicommon.run_command(cmd, display_cmd=verbose)

@transceiver.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def lpmode(db, interfacename, verbose):
    """Show interface transceiver low-power mode status"""

    ctx = click.get_current_context()

    cmd = "sudo sfputil show lpmode"

    if interfacename is not None:
        interfacename = try_convert_interfacename_from_alias(ctx, db, interfacename)

        cmd += " -p {}".format(interfacename)

    clicommon.run_command(cmd, display_cmd=verbose)

@transceiver.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@clicommon.pass_db
def presence(db, interfacename, verbose):
    """Show interface transceiver presence"""

    ctx = click.get_current_context()

    cmd = "sfpshow presence"

    if interfacename is not None:
        interfacename = try_convert_interfacename_from_alias(ctx, db, interfacename)

        cmd += " -p {}".format(interfacename)

    clicommon.run_command(cmd, display_cmd=verbose)


#
# counters group ("show interfaces counters ...")
#
@interfaces.group(invoke_without_command=True)
@click.option('-a', '--printall', is_flag=True)
@click.option('-p', '--period')
@click.option('-i', '--interface')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.pass_context
def counters(ctx, verbose, period, interface, printall):
    """Show interface counters"""

    if ctx.invoked_subcommand is None:
        cmd = "portstat"

        if printall:
            cmd += " -a"
        if period is not None:
            cmd += " -p {}".format(period)
        if interface is not None:
            cmd += " -i {}".format(interface)

        clicommon.run_command(cmd, display_cmd=verbose)

# 'errors' subcommand ("show interfaces counters errors")
@counters.command()
@click.option('-p', '--period')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def errors(verbose, period):
    """Show interface counters errors"""
    cmd = "portstat -e"
    if period is not None:
        cmd += " -p {}".format(period)
    clicommon.run_command(cmd, display_cmd=verbose)

# 'rates' subcommand ("show interfaces counters rates")
@counters.command()
@click.option('-p', '--period')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def rates(verbose, period):
    """Show interface counters rates"""
    cmd = "portstat -R"
    if period is not None:
        cmd += " -p {}".format(period)
    clicommon.run_command(cmd, display_cmd=verbose)

# 'counters' subcommand ("show interfaces counters rif")
@counters.command()
@click.argument('interface', metavar='<interface_name>', required=False, type=str)
@click.option('-p', '--period')
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def rif(interface, period, verbose):
    """Show interface counters"""

    cmd = "intfstat"
    if period is not None:
        cmd += " -p {}".format(period)
    if interface is not None:
        cmd += " -i {}".format(interface)

    clicommon.run_command(cmd, display_cmd=verbose)
