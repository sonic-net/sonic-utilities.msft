#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with platform components within SONiC
#

try:
    import click
    import os
    from lib import PlatformDataProvider, ComponentStatusProvider, ComponentUpdateProvider
    from lib import URL, SquashFs
    from log import LogHelper
except ImportError as e:
    raise ImportError("Required module not found: {}".format(str(e)))

# ========================= Constants ==========================================

VERSION = '1.0.0.0'

CHASSIS_NAME_CTX_KEY = "chassis_name"
MODULE_NAME_CTX_KEY = "module_name"
COMPONENT_CTX_KEY = "component"
COMPONENT_PATH_CTX_KEY = "component_path"
URL_CTX_KEY = "url"

TAB = "    "
PATH_SEPARATOR = "/"
IMAGE_NEXT = "next"
HELP = "?"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

ROOT_UID = 0

# ========================= Variables ==========================================

pdp = PlatformDataProvider()
log_helper = LogHelper()

# ========================= Helper functions ===================================

def cli_show_help(ctx):
    click.echo(ctx.get_help())
    ctx.exit(EXIT_SUCCESS)


def cli_abort(ctx, msg):
    click.echo("Error: " + msg + ". Aborting...")
    ctx.abort()


def cli_init(ctx):
    if os.geteuid() != ROOT_UID:
        cli_abort(ctx, "Root privileges are required")

    ctx.ensure_object(dict)

# ========================= CLI commands and groups ============================

# 'fwutil' command main entrypoint
@click.group()
@click.pass_context
def cli(ctx):
    """fwutil - Command-line utility for interacting with platform components"""

    cli_init(ctx)


# 'install' group
@cli.group()
@click.pass_context
def install(ctx):
    """Install platform firmware"""
    ctx.obj[COMPONENT_PATH_CTX_KEY] = [ ]


# 'chassis' subgroup
@click.group()
@click.pass_context
def chassis(ctx):
    """Install chassis firmware"""
    ctx.obj[CHASSIS_NAME_CTX_KEY] = pdp.chassis.get_name()
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(pdp.chassis.get_name())


def validate_module(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    if not pdp.is_modular_chassis():
        ctx.fail("Unsupported platform: non modular chassis.")

    if value not in pdp.module_component_map:
        ctx.fail("Invalid value for \"{}\": Module \"{}\" does not exist.".format(param.metavar, value))

    return value


# 'module' subgroup
@click.group()
@click.argument('module_name', metavar='<module_name>', callback=validate_module)
@click.pass_context
def module(ctx, module_name):
    """Install module firmware"""
    ctx.obj[MODULE_NAME_CTX_KEY] = module_name
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(pdp.chassis.get_name())
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(module_name)


def validate_component(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    if CHASSIS_NAME_CTX_KEY in ctx.obj:
        chassis_name = ctx.obj[CHASSIS_NAME_CTX_KEY]
        if value in pdp.chassis_component_map[chassis_name]:
            ctx.obj[COMPONENT_CTX_KEY] = pdp.chassis_component_map[chassis_name][value]
            return value

    if MODULE_NAME_CTX_KEY in ctx.obj:
        module_name = ctx.obj[MODULE_NAME_CTX_KEY]
        if value in pdp.module_component_map[module_name]:
            ctx.obj[COMPONENT_CTX_KEY] = pdp.module_component_map[module_name][value]
            return value

    ctx.fail("Invalid value for \"{}\": Component \"{}\" does not exist.".format(param.metavar, value))


# 'component' subgroup
@click.group()
@click.argument('component_name', metavar='<component_name>', callback=validate_component)
@click.pass_context
def component(ctx, component_name):
    """Install component firmware"""
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(component_name)


def install_fw(ctx, fw_path):
    component = ctx.obj[COMPONENT_CTX_KEY]
    component_path = PATH_SEPARATOR.join(ctx.obj[COMPONENT_PATH_CTX_KEY])

    status = False

    try:
        click.echo("Installing firmware:")
        click.echo(TAB + fw_path)
        log_helper.log_fw_install_start(component_path, fw_path)
        status = component.install_firmware(fw_path)
        log_helper.log_fw_install_end(component_path, fw_path, status)
    except Exception as e:
        log_helper.log_fw_install_end(component_path, fw_path, False, e)
        cli_abort(ctx, str(e))

    if not status:
        log_helper.print_error("Firmware install failed")
        ctx.exit(EXIT_FAILURE)


def download_fw(ctx, url):
    filename, headers = None, None

    component_path = PATH_SEPARATOR.join(ctx.obj[COMPONENT_PATH_CTX_KEY])

    try:
        click.echo("Downloading firmware:")
        log_helper.log_fw_download_start(component_path, str(url))
        filename, headers = url.retrieve()
        log_helper.log_fw_download_end(component_path, str(url), True)
    except Exception as e:
        log_helper.log_fw_download_end(component_path, str(url), False, e)
        cli_abort(ctx, str(e))

    return filename


def validate_fw(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    url = URL(value)

    if not url.is_url():
        path = click.Path(exists=True)
        path.convert(value, param, ctx)
    else:
        ctx.obj[URL_CTX_KEY] = url

    return value


# 'fw' subcommand
@component.command()
@click.option('-y', '--yes', 'yes', is_flag=True, show_default=True, help="Assume \"yes\" as answer to all prompts and run non-interactively")
@click.argument('fw_path', metavar='<fw_path>', callback=validate_fw)
@click.pass_context
def fw(ctx, yes, fw_path):
    """Install firmware from local binary or URL"""
    if not yes:
        click.confirm("New firmware will be installed, continue?", abort=True)

    url = None

    if URL_CTX_KEY in ctx.obj:
        url = ctx.obj[URL_CTX_KEY]
        fw_path = download_fw(ctx, url)

    try:
        install_fw(ctx, fw_path)
    finally:
        if url is not None and os.path.exists(fw_path):
            os.remove(fw_path)


# 'update' subgroup
@cli.command()
@click.option('-y', '--yes', 'yes', is_flag=True, show_default=True, help="Assume \"yes\" as answer to all prompts and run non-interactively")
@click.option('-f', '--force', 'force', is_flag=True, show_default=True, help="Install firmware regardless the current version")
@click.option('-i', '--image', 'image', type=click.Choice(["current", "next"]), default="current", show_default=True, help="Update firmware using current/next image")
@click.pass_context
def update(ctx, yes, force, image):
    """Update platform firmware"""
    aborted = False

    try:
        squashfs = None

        try:
            cup = ComponentUpdateProvider()

            if image == IMAGE_NEXT:
                squashfs = SquashFs()

                if squashfs.is_next_boot_set():
                    fs_path = squashfs.mount_next_image_fs()
                    cup = ComponentUpdateProvider(fs_path)
                else:
                    log_helper.print_warning("Next boot is set to current: fallback to defaults")

            click.echo(cup.get_status(force))

            if not yes:
                click.confirm("New firmware will be installed, continue?", abort=True)

            result = cup.update_firmware(force)

            click.echo()
            click.echo("Summary:")
            click.echo()

            click.echo(result)
        except click.Abort:
            aborted = True
        except Exception as e:
            aborted = True
            click.echo("Error: " + str(e) + ". Aborting...")

        if image == IMAGE_NEXT and squashfs is not None:
            squashfs.umount_next_image_fs()
    except Exception as e:
        cli_abort(ctx, str(e))

    if aborted:
        ctx.abort()


# 'show' subgroup
@cli.group()
def show():
    """Display platform info"""
    pass


# 'status' subcommand
@show.command()
@click.pass_context
def status(ctx):
    """Show platform components status"""
    try:
        csp = ComponentStatusProvider()
        click.echo(csp.get_status())
    except Exception as e:
        cli_abort(ctx, str(e))


# 'version' subcommand
@show.command()
def version():
    """Show utility version"""
    click.echo("fwutil version {0}".format(VERSION))

install.add_command(chassis)
install.add_command(module)

chassis.add_command(component)
module.add_command(component)

# ========================= CLI entrypoint =====================================

if __name__ == '__main__':
    cli()
