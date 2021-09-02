import json
import os
from enum import Enum
from .gu_common import GenericConfigUpdaterError, ConfigWrapper, \
                       DryRunConfigWrapper, PatchWrapper
from .patch_sorter import PatchSorter

CHECKPOINTS_DIR = "/etc/sonic/checkpoints"
CHECKPOINT_EXT = ".cp.json"

class ConfigLock:
    def acquire_lock(self):
        # TODO: Implement ConfigLock
        pass

    def release_lock(self):
        # TODO: Implement ConfigLock
        pass

class ChangeApplier:
    def apply(self, change):
        # TODO: Implement change applier
        raise NotImplementedError("ChangeApplier.apply(change) is not implemented yet")

class ConfigFormat(Enum):
    CONFIGDB = 1
    SONICYANG = 2

class PatchApplier:
    def __init__(self,
                 patchsorter=None,
                 changeapplier=None,
                 config_wrapper=None,
                 patch_wrapper=None):
        self.patchsorter = patchsorter if patchsorter is not None else PatchSorter(config_wrapper, patch_wrapper)
        self.changeapplier = changeapplier if changeapplier is not None else ChangeApplier()
        self.config_wrapper = config_wrapper if config_wrapper is not None else ConfigWrapper()
        self.patch_wrapper = patch_wrapper if patch_wrapper is not None else PatchWrapper()

    def apply(self, patch):
        # validate patch is only updating tables with yang models
        if not(self.patch_wrapper.validate_config_db_patch_has_yang_models(patch)):
            raise ValueError(f"Given patch is not valid because it has changes to tables without YANG models")

        # Get old config
        old_config = self.config_wrapper.get_config_db_as_json()

        # Generate target config
        target_config = self.patch_wrapper.simulate_patch(patch, old_config)

        # Validate target config
        if not(self.config_wrapper.validate_config_db_config(target_config)):
            raise ValueError(f"Given patch is not valid because it will result in an invalid config")

        # Generate list of changes to apply
        changes = self.patchsorter.sort(patch)

        # Apply changes in order
        for change in changes:
            self.changeapplier.apply(change)

        # Validate config updated successfully
        new_config = self.config_wrapper.get_config_db_as_json()
        if not(self.patch_wrapper.verify_same_json(target_config, new_config)):
            raise GenericConfigUpdaterError(f"After applying patch to config, there are still some parts not updated")

class ConfigReplacer:
    def __init__(self, patch_applier=None, config_wrapper=None, patch_wrapper=None):
        self.patch_applier = patch_applier if patch_applier is not None else PatchApplier()
        self.config_wrapper = config_wrapper if config_wrapper is not None else ConfigWrapper()
        self.patch_wrapper = patch_wrapper if patch_wrapper is not None else PatchWrapper()

    def replace(self, target_config):
        if not(self.config_wrapper.validate_config_db_config(target_config)):
            raise ValueError(f"The given target config is not valid")

        old_config = self.config_wrapper.get_config_db_as_json()
        patch = self.patch_wrapper.generate_patch(old_config, target_config)

        self.patch_applier.apply(patch)

        new_config = self.config_wrapper.get_config_db_as_json()
        if not(self.patch_wrapper.verify_same_json(target_config, new_config)):
            raise GenericConfigUpdaterError(f"After replacing config, there is still some parts not updated")

class FileSystemConfigRollbacker:
    def __init__(self,
                 checkpoints_dir=CHECKPOINTS_DIR,
                 config_replacer=None,
                 config_wrapper=None):
        self.checkpoints_dir = checkpoints_dir
        self.config_replacer = config_replacer if config_replacer is not None else ConfigReplacer()
        self.config_wrapper = config_wrapper if config_wrapper is not None else ConfigWrapper()

    def rollback(self, checkpoint_name):
        if not self._check_checkpoint_exists(checkpoint_name):
            raise ValueError(f"Checkpoint '{checkpoint_name}' does not exist")

        target_config = self._get_checkpoint_content(checkpoint_name)

        self.config_replacer.replace(target_config)

    def checkpoint(self, checkpoint_name):
        json_content = self.config_wrapper.get_config_db_as_json()

        if not self.config_wrapper.validate_config_db_config(json_content):
            raise ValueError(f"Running configs on the device are not valid.")

        path = self._get_checkpoint_full_path(checkpoint_name)

        self._ensure_checkpoints_dir_exists()

        self._save_json_file(path, json_content)

    def list_checkpoints(self):
        if not self._checkpoints_dir_exist():
            return []

        return self._get_checkpoint_names()

    def delete_checkpoint(self, checkpoint_name):
        if not self._check_checkpoint_exists(checkpoint_name):
            raise ValueError(f"Checkpoint '{checkpoint_name}' does not exist")

        self._delete_checkpoint(checkpoint_name)

    def _ensure_checkpoints_dir_exists(self):
        os.makedirs(self.checkpoints_dir, exist_ok=True)

    def _save_json_file(self, path, json_content):
        with open(path, "w") as fh:
            fh.write(json.dumps(json_content))

    def _get_checkpoint_content(self, checkpoint_name):
        path = self._get_checkpoint_full_path(checkpoint_name)
        with open(path) as fh:
            text = fh.read()
            return json.loads(text)

    def _get_checkpoint_full_path(self, name):
        return os.path.join(self.checkpoints_dir, f"{name}{CHECKPOINT_EXT}")

    def _get_checkpoint_names(self):
        file_names = []
        for file_name in os.listdir(self.checkpoints_dir):
            if file_name.endswith(CHECKPOINT_EXT):
                # Remove extension from file name.
                # Example assuming ext is '.cp.json', then 'checkpoint1.cp.json' becomes 'checkpoint1'
                file_names.append(file_name[:-len(CHECKPOINT_EXT)])

        return file_names

    def _checkpoints_dir_exist(self):
        return os.path.isdir(self.checkpoints_dir)

    def _check_checkpoint_exists(self, name):
        path = self._get_checkpoint_full_path(name)
        return os.path.isfile(path)

    def _delete_checkpoint(self, name):
        path = self._get_checkpoint_full_path(name)
        return os.remove(path)

class Decorator(PatchApplier, ConfigReplacer, FileSystemConfigRollbacker):
    def __init__(self, decorated_patch_applier=None, decorated_config_replacer=None, decorated_config_rollbacker=None):
        # initing base classes to make LGTM happy
        PatchApplier.__init__(self)
        ConfigReplacer.__init__(self)
        FileSystemConfigRollbacker.__init__(self)

        self.decorated_patch_applier = decorated_patch_applier
        self.decorated_config_replacer = decorated_config_replacer
        self.decorated_config_rollbacker = decorated_config_rollbacker

    def apply(self, patch):
        self.decorated_patch_applier.apply(patch)

    def replace(self, target_config):
        self.decorated_config_replacer.replace(target_config)

    def rollback(self, checkpoint_name):
        self.decorated_config_rollbacker.rollback(checkpoint_name)

    def checkpoint(self, checkpoint_name):
        self.decorated_config_rollbacker.checkpoint(checkpoint_name)

    def list_checkpoints(self):
        return self.decorated_config_rollbacker.list_checkpoints()

    def delete_checkpoint(self, checkpoint_name):
        self.decorated_config_rollbacker.delete_checkpoint(checkpoint_name)

class SonicYangDecorator(Decorator):
    def __init__(self, patch_wrapper, config_wrapper, decorated_patch_applier=None, decorated_config_replacer=None):
        Decorator.__init__(self, decorated_patch_applier, decorated_config_replacer)

        self.patch_wrapper = patch_wrapper
        self.config_wrapper = config_wrapper

    def apply(self, patch):
        config_db_patch = self.patch_wrapper.convert_sonic_yang_patch_to_config_db_patch(patch)
        Decorator.apply(self, config_db_patch)

    def replace(self, target_config):
        config_db_target_config = self.config_wrapper.convert_sonic_yang_to_config_db(target_config)
        Decorator.replace(self, config_db_target_config)

class ConfigLockDecorator(Decorator):
    def __init__(self,
                 decorated_patch_applier=None,
                 decorated_config_replacer=None,
                 decorated_config_rollbacker=None,
                 config_lock = ConfigLock()):
        Decorator.__init__(self, decorated_patch_applier, decorated_config_replacer, decorated_config_rollbacker)

        self.config_lock = config_lock

    def apply(self, patch):
        self.execute_write_action(Decorator.apply, self, patch)

    def replace(self, target_config):
        self.execute_write_action(Decorator.replace, self, target_config)

    def rollback(self, checkpoint_name):
        self.execute_write_action(Decorator.rollback, self, checkpoint_name)

    def checkpoint(self, checkpoint_name):
        self.execute_write_action(Decorator.checkpoint, self, checkpoint_name)

    def execute_write_action(self, action, *args):
        self.config_lock.acquire_lock()
        action(*args)
        self.config_lock.release_lock()

class GenericUpdateFactory:
    def create_patch_applier(self, config_format, verbose, dry_run):
        self.init_verbose_logging(verbose)

        config_wrapper = self.get_config_wrapper(dry_run)

        patch_applier = PatchApplier(config_wrapper=config_wrapper)

        patch_wrapper = PatchWrapper(config_wrapper)

        if config_format == ConfigFormat.CONFIGDB:
            pass
        elif config_format == ConfigFormat.SONICYANG:
            patch_applier = SonicYangDecorator(
                    decorated_patch_applier = patch_applier, patch_wrapper=patch_wrapper, config_wrapper=config_wrapper)
        else:
            raise ValueError(f"config-format '{config_format}' is not supported")

        if not dry_run:
            patch_applier = ConfigLockDecorator(decorated_patch_applier = patch_applier)

        return patch_applier

    def create_config_replacer(self, config_format, verbose, dry_run):
        self.init_verbose_logging(verbose)

        config_wrapper = self.get_config_wrapper(dry_run)

        patch_applier = PatchApplier(config_wrapper=config_wrapper)

        patch_wrapper = PatchWrapper(config_wrapper)

        config_replacer = ConfigReplacer(patch_applier=patch_applier, config_wrapper=config_wrapper)
        if config_format == ConfigFormat.CONFIGDB:
            pass
        elif config_format == ConfigFormat.SONICYANG:
            config_replacer = SonicYangDecorator(
                    decorated_config_replacer = config_replacer, patch_wrapper=patch_wrapper, config_wrapper=config_wrapper)
        else:
            raise ValueError(f"config-format '{config_format}' is not supported")

        if not dry_run:
            config_replacer = ConfigLockDecorator(decorated_config_replacer = config_replacer)

        return config_replacer

    def create_config_rollbacker(self, verbose, dry_run=False):
        self.init_verbose_logging(verbose)

        config_wrapper = self.get_config_wrapper(dry_run)

        patch_applier = PatchApplier(config_wrapper=config_wrapper)
        config_replacer = ConfigReplacer(config_wrapper=config_wrapper, patch_applier=patch_applier)
        config_rollbacker = FileSystemConfigRollbacker(config_wrapper = config_wrapper, config_replacer = config_replacer)

        if not dry_run:
            config_rollbacker = ConfigLockDecorator(decorated_config_rollbacker = config_rollbacker)

        return config_rollbacker

    def init_verbose_logging(self, verbose):
        # TODO: implement verbose logging
        # Usually logs have levels such as: error, warning, info, debug.
        # By default all log levels should show up to the user, except debug.
        # By allowing verbose logging, debug msgs will also be shown to the user.
        pass

    def get_config_wrapper(self, dry_run):
        if dry_run:
            return DryRunConfigWrapper()
        else:
            return ConfigWrapper()

class GenericUpdater:
    def __init__(self, generic_update_factory=None):
        self.generic_update_factory = \
            generic_update_factory if generic_update_factory is not None else GenericUpdateFactory()

    def apply_patch(self, patch, config_format, verbose, dry_run):
        patch_applier = self.generic_update_factory.create_patch_applier(config_format, verbose, dry_run)
        patch_applier.apply(patch)

    def replace(self, target_config, config_format, verbose, dry_run):
        config_replacer = self.generic_update_factory.create_config_replacer(config_format, verbose, dry_run)
        config_replacer.replace(target_config)

    def rollback(self, checkpoint_name, verbose, dry_run):
        config_rollbacker = self.generic_update_factory.create_config_rollbacker(verbose, dry_run)
        config_rollbacker.rollback(checkpoint_name)

    def checkpoint(self, checkpoint_name, verbose):
        config_rollbacker = self.generic_update_factory.create_config_rollbacker(verbose)
        config_rollbacker.checkpoint(checkpoint_name)

    def delete_checkpoint(self, checkpoint_name, verbose):
        config_rollbacker = self.generic_update_factory.create_config_rollbacker(verbose)
        config_rollbacker.delete_checkpoint(checkpoint_name)

    def list_checkpoints(self, verbose):
        config_rollbacker = self.generic_update_factory.create_config_rollbacker(verbose)
        return config_rollbacker.list_checkpoints()
