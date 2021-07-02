#!/usr/bin/env python

import contextlib
import os
import stat
import subprocess
from collections import defaultdict
from typing import Dict

import jinja2 as jinja2
from prettyprinter import pformat
from toposort import toposort_flatten, CircularDependencyError

from sonic_package_manager.logger import log
from sonic_package_manager.package import Package
from sonic_package_manager.service_creator import ETC_SONIC_PATH
from sonic_package_manager.service_creator.feature import FeatureRegistry
from sonic_package_manager.service_creator.utils import in_chroot

SERVICE_FILE_TEMPLATE = 'sonic.service.j2'
TIMER_UNIT_TEMPLATE = 'timer.unit.j2'

SYSTEMD_LOCATION = '/usr/lib/systemd/system'

SERVICE_MGMT_SCRIPT_TEMPLATE = 'service_mgmt.sh.j2'
SERVICE_MGMT_SCRIPT_LOCATION = '/usr/local/bin'

DOCKER_CTL_SCRIPT_TEMPLATE = 'docker_image_ctl.j2'
DOCKER_CTL_SCRIPT_LOCATION = '/usr/bin'

DEBUG_DUMP_SCRIPT_TEMPLATE = 'dump.sh.j2'
DEBUG_DUMP_SCRIPT_LOCATION = '/usr/local/bin/debug-dump/'

TEMPLATES_PATH = '/usr/share/sonic/templates'


class ServiceCreatorError(Exception):
    pass


def render_template(in_template: str,
                    outfile: str,
                    render_ctx: Dict,
                    executable: bool = False):
    """ Template renderer helper routine.
    Args:
        in_template: Input file with template content
        outfile: Output file to render template to
        render_ctx: Dictionary used to generate jinja2 template
        executable: Set executable bit on rendered file
    """

    log.debug(f'Rendering {in_template} to {outfile} with {pformat(render_ctx)}')

    with open(in_template, 'r') as instream:
        template = jinja2.Template(instream.read())

    with open(outfile, 'w') as outstream:
        outstream.write(template.render(**render_ctx))

    if executable:
        set_executable_bit(outfile)


def get_tmpl_path(template_name: str) -> str:
    """ Returns a path to a template.
    Args:
        template_name: Template file name.
    """

    return os.path.join(TEMPLATES_PATH, template_name)


def set_executable_bit(filepath):
    """ Sets +x on filepath. """

    st = os.stat(filepath)
    os.chmod(filepath, st.st_mode | stat.S_IEXEC)


def run_command(command: str):
    """ Run arbitrary bash command.
    Args:
        command: String command to execute as bash script
    Raises:
        PackageManagerError: Raised when the command return code
                             is not 0.
    """

    log.debug(f'running command: {command}')

    proc = subprocess.Popen(command,
                            shell=True,
                            executable='/bin/bash',
                            stdout=subprocess.PIPE)
    (_, _) = proc.communicate()
    if proc.returncode != 0:
        raise ServiceCreatorError(f'Failed to execute "{command}"')


class ServiceCreator:
    """ Creates and registers services in SONiC based on the package
     manifest. """

    def __init__(self,
                 feature_registry: FeatureRegistry,
                 sonic_db):
        """ Initialize ServiceCreator with:
        
        Args:
            feature_registry: FeatureRegistry object.
            sonic_db: SonicDb interface.
         """

        self.feature_registry = feature_registry
        self.sonic_db = sonic_db

    def create(self,
               package: Package,
               register_feature: bool = True,
               state: str = 'enabled',
               owner: str = 'local'):
        """ Register package as SONiC service. 
        
        Args:
            package: Package object to install.
            register_feature: Wether to register this package in FEATURE table.
            state: Default feature state.
            owner: Default feature owner.

        Returns:
            None
        """

        try:
            self.generate_container_mgmt(package)
            self.generate_service_mgmt(package)
            self.update_dependent_list_file(package)
            self.generate_systemd_service(package)
            self.generate_dump_script(package)
            self.generate_service_reconciliation_file(package)

            self.set_initial_config(package)
            self._post_operation_hook()

            if register_feature:
                self.feature_registry.register(package.manifest,
                                               state, owner)
        except (Exception, KeyboardInterrupt):
            self.remove(package, register_feature)
            raise

    def remove(self,
               package: Package,
               deregister_feature: bool = True):
        """ Uninstall SONiC service provided by the package.
        
        Args:
            package: Package object to uninstall.
            deregister_feature: Wether to deregister this package from FEATURE table.

        Returns:
            None
        """

        name = package.manifest['service']['name']

        def remove_file(path):
            if os.path.exists(path):
                os.remove(path)
                log.info(f'removed {path}')

        remove_file(os.path.join(SYSTEMD_LOCATION, f'{name}.service'))
        remove_file(os.path.join(SYSTEMD_LOCATION, f'{name}@.service'))
        remove_file(os.path.join(SERVICE_MGMT_SCRIPT_LOCATION, f'{name}.sh'))
        remove_file(os.path.join(DOCKER_CTL_SCRIPT_LOCATION, f'{name}.sh'))
        remove_file(os.path.join(DEBUG_DUMP_SCRIPT_LOCATION, f'{name}'))
        remove_file(os.path.join(ETC_SONIC_PATH, f'{name}_reconcile'))

        self.update_dependent_list_file(package, remove=True)
        self._post_operation_hook()

        if deregister_feature:
            self.feature_registry.deregister(package.manifest['service']['name'])
            self.remove_config(package)

    def generate_container_mgmt(self, package: Package):
        """ Generates container management script under /usr/bin/<service>.sh for package. 
        
        Args:
            package: Package object to generate script for.
        Returns:
            None
        """

        image_id = package.image_id
        name = package.manifest['service']['name']
        container_spec = package.manifest['container']
        script_path = os.path.join(DOCKER_CTL_SCRIPT_LOCATION, f'{name}.sh')
        script_template = get_tmpl_path(DOCKER_CTL_SCRIPT_TEMPLATE)
        run_opt = []

        if container_spec['privileged']:
            run_opt.append('--privileged')

        run_opt.append('-t')

        for volume in container_spec['volumes']:
            run_opt.append(f'-v {volume}')

        for mount in container_spec['mounts']:
            mount_type, source, target = mount['type'], mount['source'], mount['target']
            run_opt.append(f'--mount type={mount_type},source={source},target={target}')

        for tmpfs_mount in container_spec['tmpfs']:
            run_opt.append(f'--tmpfs {tmpfs_mount}')

        for env_name, value in container_spec['environment'].items():
            run_opt.append(f'-e {env_name}={value}')

        run_opt = ' '.join(run_opt)
        render_ctx = {
            'docker_container_name': name,
            'docker_image_id': image_id,
            'docker_image_run_opt': run_opt,
        }
        render_template(script_template, script_path, render_ctx, executable=True)
        log.info(f'generated {script_path}')

    def generate_service_mgmt(self, package: Package):
        """ Generates service management script under /usr/local/bin/<service>.sh for package. 
        
        Args:
            package: Package object to generate script for.
        Returns:
            None
        """

        name = package.manifest['service']['name']
        multi_instance_services = self.feature_registry.get_multi_instance_features()
        script_path = os.path.join(SERVICE_MGMT_SCRIPT_LOCATION, f'{name}.sh')
        scrip_template = get_tmpl_path(SERVICE_MGMT_SCRIPT_TEMPLATE)
        render_ctx = {
            'source': get_tmpl_path(SERVICE_MGMT_SCRIPT_TEMPLATE),
            'manifest': package.manifest.unmarshal(),
            'multi_instance_services': multi_instance_services,
        }
        render_template(scrip_template, script_path, render_ctx, executable=True)
        log.info(f'generated {script_path}')

    def generate_systemd_service(self, package: Package):
        """ Generates systemd service(s) file and timer(s) (if needed) for package. 
        
        Args:
            package: Package object to generate service for.
        Returns:
            None
        """

        name = package.manifest['service']['name']
        multi_instance_services = self.feature_registry.get_multi_instance_features()

        template = get_tmpl_path(SERVICE_FILE_TEMPLATE)
        template_vars = {
            'source': get_tmpl_path(SERVICE_FILE_TEMPLATE),
            'manifest': package.manifest.unmarshal(),
            'multi_instance': False,
            'multi_instance_services': multi_instance_services,
        }
        output_file = os.path.join(SYSTEMD_LOCATION, f'{name}.service')
        render_template(template, output_file, template_vars)
        log.info(f'generated {output_file}')

        if package.manifest['service']['asic-service']:
            output_file = os.path.join(SYSTEMD_LOCATION, f'{name}@.service')
            template_vars['multi_instance'] = True
            render_template(template, output_file, template_vars)
            log.info(f'generated {output_file}')

        if package.manifest['service']['delayed']:
            template_vars = {
                'source': get_tmpl_path(TIMER_UNIT_TEMPLATE),
                'manifest': package.manifest.unmarshal(),
                'multi_instance': False,
            }
            output_file = os.path.join(SYSTEMD_LOCATION, f'{name}.timer')
            template = os.path.join(TEMPLATES_PATH, TIMER_UNIT_TEMPLATE)
            render_template(template, output_file, template_vars)
            log.info(f'generated {output_file}')

            if package.manifest['service']['asic-service']:
                output_file = os.path.join(SYSTEMD_LOCATION, f'{name}@.timer')
                template_vars['multi_instance'] = True
                render_template(template, output_file, template_vars)
                log.info(f'generated {output_file}')

    def update_dependent_list_file(self, package: Package, remove=False):
        """ This function updates dependent list file for packages listed in "dependent-of"
            (path: /etc/sonic/<service>_dependent file).
        
        Args:
            package: Package to update packages dependent of it.
        Returns:
            None.

        """
        name = package.manifest['service']['name']
        dependent_of = package.manifest['service']['dependent-of']
        host_service = package.manifest['service']['host-service']
        asic_service = package.manifest['service']['asic-service']

        def update_dependent(service, name, multi_inst):
            if multi_inst:
                filename = f'{service}_multi_inst_dependent'
            else:
                filename = f'{service}_dependent'

            filepath = os.path.join(ETC_SONIC_PATH, filename)

            dependent_services = set()
            if os.path.exists(filepath):
                with open(filepath) as fp:
                    dependent_services.update({line.strip() for line in fp.readlines()})
            if remove:
                with contextlib.suppress(KeyError):
                    dependent_services.remove(name)
            else:
                dependent_services.add(name)
            with open(filepath, 'w') as fp:
                fp.write('\n'.join(dependent_services))

        for service in dependent_of:
            if host_service:
                update_dependent(service, name, multi_inst=False)
            if asic_service:
                update_dependent(service, name, multi_inst=True)

    def generate_dump_script(self, package):
        """ Generates dump plugin script for package.
        
        Args:
            package: Package object to generate dump plugin script for.
        Returns:
            None.
        """

        name = package.manifest['service']['name']

        if not package.manifest['package']['debug-dump']:
            return

        if not os.path.exists(DEBUG_DUMP_SCRIPT_LOCATION):
            os.mkdir(DEBUG_DUMP_SCRIPT_LOCATION)

        scrip_template = os.path.join(TEMPLATES_PATH, DEBUG_DUMP_SCRIPT_TEMPLATE)
        script_path = os.path.join(DEBUG_DUMP_SCRIPT_LOCATION, f'{name}')
        render_ctx = {
            'source': get_tmpl_path(SERVICE_MGMT_SCRIPT_TEMPLATE),
            'manifest': package.manifest.unmarshal(),
        }
        render_template(scrip_template, script_path, render_ctx, executable=True)
        log.info(f'generated {script_path}')

    def get_shutdown_sequence(self, reboot_type: str, packages: Dict[str, Package]):
        """ Returns shutdown sequence file for particular reboot type.
        
        Args:
            reboot_type: Reboot type to generated service shutdown sequence for.
            packages: Dict of installed packages.
        Returns:
            Ordered list of service names.
        """

        shutdown_graph = defaultdict(set)

        def service_exists(service):
            for package in packages.values():
                if package.manifest['service']['name'] == service:
                    return True
            log.info(f'Service {service} is not installed, it is skipped...')
            return False

        def filter_not_available(services):
            return set(filter(service_exists, services))

        for package in packages.values():
            service_props = package.manifest['service']
            after = filter_not_available(service_props[f'{reboot_type}-shutdown']['after'])
            before = filter_not_available(service_props[f'{reboot_type}-shutdown']['before'])

            if not after and not before:
                continue

            name = package.manifest['service']['name']
            shutdown_graph[name].update(after)

            for service in before:
                shutdown_graph[service].update({name})

        log.debug(f'shutdown graph {pformat(shutdown_graph)}')

        try:
            order = toposort_flatten(shutdown_graph)
        except CircularDependencyError as err:
            raise ServiceCreatorError(f'Circular dependency found in {reboot_type} error: {err}')

        log.debug(f'shutdown order {pformat(order)}')
        return order

    def generate_shutdown_sequence_file(self, reboot_type: str, packages: Dict[str, Package]):
        """ Generates shutdown sequence file for particular reboot type
            (path: /etc/sonic/<reboot-type>-reboot_order).
        
        Args:
            reboot_type: Reboot type to generated service shutdown sequence for.
            packages: Dict of installed packages.
        Returns:
            None.
        """

        order = self.get_shutdown_sequence(reboot_type, packages)
        with open(os.path.join(ETC_SONIC_PATH, f'{reboot_type}-reboot_order'), 'w') as file:
            file.write(' '.join(order))
    
    def generate_shutdown_sequence_files(self, packages: Dict[str, Package]):
        """ Generates shutdown sequence file for fast and warm reboot. 
            (path: /etc/sonic/<reboot-type>-reboot_order).
        
        Args:
            packages: Dict of installed packages.
        Returns:
            None.
        """

        for reboot_type in ('fast', 'warm'):
            self.generate_shutdown_sequence_file(reboot_type, packages)

    def generate_service_reconciliation_file(self, package):
        """ Generates reconciliation file for package
            (path: /etc/sonic/<service>_reconcile).

        Args:
            package: Package object to generate service reconciliation file for.
        Returns:
            None
        """

        name = package.manifest['service']['name']
        all_processes = package.manifest['processes']
        processes = [process['name'] for process in all_processes if process['reconciles']]
        with open(os.path.join(ETC_SONIC_PATH, f'{name}_reconcile'), 'w') as file:
            file.write(' '.join(processes))

    def set_initial_config(self, package):
        """ Set initial package configuration from manifest.
        This method updates but does not override existing entries in tables.

        Args:
            package: Package object to set initial configuration for.
        Returns:
            None
        """

        init_cfg = package.manifest['package']['init-cfg']

        for tablename, content in init_cfg.items():
            if not isinstance(content, dict):
                continue

            tables = self._get_tables(tablename)

            for key in content:
                for table in tables:
                    cfg = content[key]
                    exists, old_fvs = table.get(key)
                    if exists:
                        cfg.update(old_fvs)
                    fvs = list(cfg.items())
                    table.set(key, fvs)

    def remove_config(self, package):
        """ Remove configuration based on init-cfg tables, so having
        init-cfg even with tables without keys might be a good idea.
        TODO: init-cfg should be validated with yang model
        TODO: remove config from tables known to yang model

        Args:
            package: Package object remove initial configuration for.
        Returns:
            None
        """

        init_cfg = package.manifest['package']['init-cfg']

        for tablename, content in init_cfg.items():
            if not isinstance(content, dict):
                continue

            tables = self._get_tables(tablename)

            for key in content:
                for table in tables:
                    table._del(key)

    def _get_tables(self, table_name):
        """ Return swsscommon Tables for all kinds of configuration DBs """

        tables = []

        running_table = self.sonic_db.running_table(table_name)
        if running_table is not None:
            tables.append(running_table)

        persistent_table = self.sonic_db.persistent_table(table_name)
        if persistent_table is not None:
            tables.append(persistent_table)

        initial_table = self.sonic_db.initial_table(table_name)
        if initial_table is not None:
            tables.append(initial_table)

        return tables

    def _post_operation_hook(self):
        """ Common operations executed after service is created/removed. """

        if not in_chroot():
            run_command('systemctl daemon-reload')
