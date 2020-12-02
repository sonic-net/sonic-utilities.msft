import click
import utilities_common.cli as clicommon


#
# 'dropcounters' group ###
#

@click.group(cls=clicommon.AliasedGroup)
def dropcounters():
    """Show drop counter related information"""
    pass


# 'configuration' subcommand ("show dropcounters configuration")
@dropcounters.command()
@click.option('-g', '--group', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def configuration(group, verbose):
    """Show current drop counter configuration"""
    cmd = "dropconfig -c show_config"

    if group:
        cmd += " -g '{}'".format(group)

    clicommon.run_command(cmd, display_cmd=verbose)


# 'capabilities' subcommand ("show dropcounters capabilities")
@dropcounters.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def capabilities(verbose):
    """Show device drop counter capabilities"""
    cmd = "dropconfig -c show_capabilities"

    clicommon.run_command(cmd, display_cmd=verbose)


# 'counts' subcommand ("show dropcounters counts")
@dropcounters.command()
@click.option('-g', '--group', required=False)
@click.option('-t', '--counter_type', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counts(group, counter_type, verbose):
    """Show drop counts"""
    cmd = "dropstat -c show"

    if group:
        cmd += " -g '{}'".format(group)

    if counter_type:
        cmd += " -t '{}'".format(counter_type)

    clicommon.run_command(cmd, display_cmd=verbose)
