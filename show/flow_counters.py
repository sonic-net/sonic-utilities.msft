import click
import utilities_common.cli as clicommon
import utilities_common.multi_asic as multi_asic_util

#
# 'flowcnt-trap' group ###
#

@click.group(cls=clicommon.AliasedGroup)
def flowcnt_trap():
    """Show trap flow counter related information"""
    pass

@flowcnt_trap.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--namespace', '-n', 'namespace', default=None, type=click.Choice(multi_asic_util.multi_asic_ns_choices()), show_default=True, help='Namespace name or all')
def stats(verbose, namespace):
    """Show trap flow counter statistic"""
    cmd = "flow_counters_stat -t trap"
    if namespace is not None:
        cmd += " -n {}".format(namespace)
    clicommon.run_command(cmd, display_cmd=verbose)
