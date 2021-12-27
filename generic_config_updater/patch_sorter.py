import copy
import json
import jsonpatch
from collections import deque
from enum import Enum
from .gu_common import OperationWrapper, OperationType, GenericConfigUpdaterError, \
                       JsonChange, PathAddressing, genericUpdaterLogging

class Diff:
    """
    A class that contains the diff info between current and target configs. 
    """
    def __init__(self, current_config, target_config):
        self.current_config = current_config
        self.target_config = target_config

    def __hash__(self):
        cc = json.dumps(self.current_config, sort_keys=True)
        tc = json.dumps(self.target_config, sort_keys=True)
        return hash((cc,tc))

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, Diff):
            return self.current_config == other.current_config and self.target_config == other.target_config

        return False

    # TODO: Can be optimized to apply the move in place. JsonPatch supports that using the option 'in_place=True'
    # Check: https://python-json-patch.readthedocs.io/en/latest/tutorial.html#applying-a-patch
    # NOTE: in case move is applied in place, we will need to support `undo_move` as well.
    def apply_move(self, move):
        new_current_config = move.apply(self.current_config)
        return Diff(new_current_config, self.target_config)

    def has_no_diff(self):
        return self.current_config == self.target_config

    def __str__(self):
        return f"""current_config: {self.current_config}
target_config: {self.target_config}"""

    def __repr__(self):
        return str(self)

class JsonMove:
    """
    A class similar to JsonPatch operation, but it allows the path to refer to non-existing middle elements.

    JsonPatch operation fails to update json if the path in the patch refers to element that do not exist.
    For example, assume json to be:
    {}
    The following path will be rejected:
    /elem1/key1
    The reason is 'elem1' does not exist in the json

    JsonMove on the other hand allows that given the target_config_tokens i.e. the target_config path,
    and current_config_tokens i.e. current_config path where the update needs to happen.
    """
    def __init__(self, diff, op_type, current_config_tokens, target_config_tokens=None):
        operation = JsonMove._to_jsonpatch_operation(diff, op_type, current_config_tokens, target_config_tokens)
        self.patch = jsonpatch.JsonPatch([operation])
        self.op_type = operation[OperationWrapper.OP_KEYWORD]
        self.path = operation[OperationWrapper.PATH_KEYWORD]
        self.value = operation.get(OperationWrapper.VALUE_KEYWORD, None)

        self.op_type = op_type
        self.current_config_tokens = current_config_tokens
        self.target_config_tokens = target_config_tokens

    @staticmethod
    def _to_jsonpatch_operation(diff, op_type, current_config_tokens, target_config_tokens):
        operation_wrapper = OperationWrapper()
        path_addressing = PathAddressing()

        if op_type == OperationType.REMOVE:
            path = path_addressing.create_path(current_config_tokens)
            return operation_wrapper.create(op_type, path)

        if op_type == OperationType.REPLACE:
            path = path_addressing.create_path(current_config_tokens)
            value = JsonMove._get_value(diff.target_config, target_config_tokens)
            return operation_wrapper.create(op_type, path, value)

        if op_type == OperationType.ADD:
            return JsonMove._to_jsonpatch_add_operation(diff, current_config_tokens, target_config_tokens)

        raise ValueError(f"OperationType {op_type} is not supported")

    @staticmethod
    def _get_value(config, tokens):
        for token in tokens:
            config = config[token]

        return copy.deepcopy(config)

    @staticmethod
    def _to_jsonpatch_add_operation(diff, current_config_tokens, target_config_tokens):
        """
        Check description of JsonMove class first.

        ADD operation path can refer to elements that do not exist, so to convert JsonMove to JsonPatch operation
        We need to remove the non-existing tokens from the current_config path and move them to the value.

        Example:
          Assume Target Config:
            {
                "dict1":{
                    "key11": "value11"
                }
            }
          Assume Current Config:
            {
            }
          Assume JsonMove:
            op_type=add, current_config_tokens=[dict1, key11], target_config_tokens=[dict1, key11]
  
          Converting this to operation directly would result in:
            {"op":"add", "path":"/dict1/key11", "value":"value11"}
          BUT this is not correct since 'dict1' which does not exist in Current Config.
          Instead we convert to:
            {"op":"add", "path":"/dict1", "value":{"key11": "value11"}}
        """
        operation_wrapper = OperationWrapper()
        path_addressing = PathAddressing()

        # if path refers to whole config i.e. no tokens, then just create the operation
        if not current_config_tokens:
            path = path_addressing.create_path(current_config_tokens)
            value = JsonMove._get_value(diff.target_config, target_config_tokens)
            return operation_wrapper.create(OperationType.ADD, path, value)

        # Start with getting target-config that match the path all the way to the value in json format
        # Example:
        #   Assume target-config:
        #     {
        #         "dict1":{
        #             "key11": "value11",
        #             "list12": [
        #                         "value121",
        #                         "value122"
        #                       ]
        #         },
        #         "dict2":{
        #             "key21": "value21"
        #         }
        #     }
        #   Assume target config tokens:
        #     dict1, list12, 1
        #   filtered_config will be
        #     {
        #         "dict1":{
        #             "list12": [
        #                         "value122"
        #                       ]
        #         }
        #     }
        target_ptr = diff.target_config
        filtered_config = {}
        filtered_config_ptr = filtered_config
        for token_index in range(len(target_config_tokens)):
            token = target_config_tokens[token_index]

            # Tokens are expected to be of the correct data-type i.e. string, int (list-index)
            # So not checking the type of the token before consuming it
            target_ptr = target_ptr[token]

            # if it is the last item, then just return the last target_ptr
            if token_index == len(target_config_tokens)-1:
                filtered_value = target_ptr
            elif isinstance(target_ptr, list):
                filtered_value = []
            else:
                filtered_value = {}

            if isinstance(filtered_config_ptr, list):
                filtered_config_ptr.append(filtered_value) # filtered_config list will contain only 1 value
            else: # otherwise it is a dict
                filtered_config_ptr[token] = filtered_value

            filtered_config_ptr = filtered_value

        # Then from the filtered_config get the all the tokens that exist in current_config
        # This will be the new path, and the new value will be the corresponding filtered_config
        # Example:
        #   Assume filtered_config
        #     {
        #         "dict1":{
        #             "key11": "value11"
        #         }
        #     }
        #   Assume current-config
        #     {
        #         "dict1":{
        #             "list12": [
        #                         "value122"
        #                       ]
        #         }
        #     }
        #   Then the JsonPatch path would be:
        #     /dict1/list12
        #   And JsonPatch value would be:
        #     [ "value122" ]
        current_ptr = diff.current_config
        new_tokens = []
        for token in current_config_tokens:
            new_tokens.append(token)
            was_list = isinstance(filtered_config, list)
            if was_list:
                # filtered_config list can only have 1 item
                filtered_config = filtered_config[0]
            else:
                filtered_config = filtered_config[token]

            if was_list and token >= len(current_ptr):
                break
            if not(was_list) and token not in current_ptr:
                break
            current_ptr = current_ptr[token]

        op_type = OperationType.ADD
        new_path = path_addressing.create_path(new_tokens)
        new_value = copy.deepcopy(filtered_config)

        return operation_wrapper.create(op_type, new_path, new_value)

    @staticmethod
    def from_patch(patch):
        ops = list(patch)
        if len(ops) != 1:
            raise GenericConfigUpdaterError(
                f"Only a patch of a single operation be converted to JsonMove. Patch has {len(ops)} operation/s")

        return JsonMove.from_operation(ops[0])

    @staticmethod
    def from_operation(operation):
        path_addressing = PathAddressing()
        op_type = OperationType[operation[OperationWrapper.OP_KEYWORD].upper()]
        path = operation[OperationWrapper.PATH_KEYWORD]
        if op_type in [OperationType.ADD, OperationType.REPLACE]:
            value = operation[OperationWrapper.VALUE_KEYWORD]
        else:
            value = None

        tokens = path_addressing.get_path_tokens(path)

        target_config = {}
        target_config_ptr = target_config
        current_config = {}
        current_config_ptr = current_config
        for token in tokens[:-1]:
            target_config_ptr[token] = {}
            current_config_ptr[token] = {}
            target_config_ptr = target_config_ptr[token]
            current_config_ptr = current_config_ptr[token]

        if tokens:
            target_config_ptr[tokens[-1]] = value
        else:
            # whole-config, just use value
            target_config = value

        current_config_tokens = tokens
        if op_type in [OperationType.ADD, OperationType.REPLACE]:
            target_config_tokens = tokens
        else:
            target_config_tokens = None

        diff = Diff(current_config, target_config)

        return JsonMove(diff, op_type, current_config_tokens, target_config_tokens)

    def apply(self, config):
        return self.patch.apply(config)

    def __str__(self):
        return str(self.patch)

    def __repr__(self):
        return str(self.patch)

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, JsonMove):
            return self.patch == other.patch
        return False

    def __hash__(self):
        return hash((self.op_type, self.path, json.dumps(self.value)))

class MoveWrapper:
    def __init__(self, move_generators, move_extenders, move_validators):
        self.move_generators = move_generators
        self.move_extenders = move_extenders
        self.move_validators = move_validators

    def generate(self, diff):
        processed_moves = set()
        moves = deque([])

        for move in self._generate_moves(diff):
            if move in processed_moves:
                continue
            processed_moves.add(move)
            yield move
            moves.extend(self._extend_moves(move, diff))

        while moves:
            move = moves.popleft()
            if move in processed_moves:
                continue
            processed_moves.add(move)
            yield move
            moves.extend(self._extend_moves(move, diff))

    def validate(self, move, diff):
        for validator in self.move_validators:
            if not validator.validate(move, diff):
                return False
        return True

    def simulate(self, move, diff):
        return diff.apply_move(move)

    def _generate_moves(self, diff):
        for generator in self.move_generators:
            for move in generator.generate(diff):
                yield move

    def _extend_moves(self, move, diff):
        for extender in self.move_extenders:
            for newmove in extender.extend(move, diff):
                yield newmove

class DeleteWholeConfigMoveValidator:
    """
    A class to validate not deleting whole config as it is not supported by JsonPatch lib.
    """
    def validate(self, move, diff):
        if move.op_type == OperationType.REMOVE and move.path == "":
            return False
        return True

class FullConfigMoveValidator:
    """
    A class to validate that full config is valid according to YANG models after applying the move.
    """
    def __init__(self, config_wrapper):
        self.config_wrapper = config_wrapper

    def validate(self, move, diff):
        simulated_config = move.apply(diff.current_config)
        return self.config_wrapper.validate_config_db_config(simulated_config)

# TODO: Add this validation to YANG models instead
class UniqueLanesMoveValidator:
    """
    A class to validate lanes and any port are unique between all ports.
    """
    def validate(self, move, diff):
        simulated_config = move.apply(diff.current_config)

        if "PORT" not in simulated_config:
            return True

        ports = simulated_config["PORT"]
        existing = set()
        for port in ports:
            attrs = ports[port]
            if "lanes" in attrs:
                lanes_str = attrs["lanes"]
                lanes = lanes_str.split(", ")
                for lane in lanes:
                    if lane in existing:
                        return False
                    existing.add(lane)
        return True

class CreateOnlyMoveValidator:
    """
    A class to validate create-only fields are only created, but never modified/updated. In other words:
    - Field cannot be replaced.
    - Field cannot be added, only if the parent is added.
    - Field cannot be deleted, only if the parent is deleted.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

        # TODO: create-only fields are hard-coded for now, it should be moved to YANG models
        # Each pattern consist of a list of tokens. Token matching starts from the root level of the config.
        # Each token is either a specific key or '*' to match all keys.
        self.create_only_patterns = [
            ["PORT", "*", "lanes"],
            ["LOOPBACK_INTERFACE", "*", "vrf_name"],
        ]

    def validate(self, move, diff):
        simulated_config = move.apply(diff.current_config)
        paths = set(list(self._get_create_only_paths(diff.current_config)) + list(self._get_create_only_paths(simulated_config)))

        for path in paths:
            tokens = self.path_addressing.get_path_tokens(path)
            if self._value_exist_but_different(tokens, diff.current_config, simulated_config):
                return False
            if self._value_added_but_parent_exist(tokens, diff.current_config, simulated_config):
                return False
            if self._value_removed_but_parent_remain(tokens, diff.current_config, simulated_config):
                return False

        return True

    def _get_create_only_paths(self, config):
        for pattern in self.create_only_patterns:
            for create_only_path in self._get_create_only_path_recursive(config, pattern, [], 0):
                yield create_only_path

    def _get_create_only_path_recursive(self, config, pattern_tokens, matching_tokens, idx):
        if idx == len(pattern_tokens):
            yield '/' + '/'.join(matching_tokens)
            return

        matching_keys = []
        if pattern_tokens[idx] == "*":
            matching_keys = config.keys()
        elif pattern_tokens[idx] in config:
            matching_keys = [pattern_tokens[idx]]

        for key in matching_keys:
            matching_tokens.append(key)
            for create_only_path in self._get_create_only_path_recursive(config[key], pattern_tokens, matching_tokens, idx+1):
                yield create_only_path
            matching_tokens.pop()

    def _value_exist_but_different(self, tokens, current_config_ptr, simulated_config_ptr):
        for token in tokens:
            mod_token = int(token) if isinstance(current_config_ptr, list) else token

            if mod_token not in current_config_ptr:
                return False

            if mod_token not in simulated_config_ptr:
                return False

            current_config_ptr = current_config_ptr[mod_token]
            simulated_config_ptr = simulated_config_ptr[mod_token]

        return current_config_ptr != simulated_config_ptr

    def _value_added_but_parent_exist(self, tokens, current_config_ptr, simulated_config_ptr):
        # if value is not added, return false
        if not self._exist_only_in_first(tokens, simulated_config_ptr, current_config_ptr):
            return False

        # if parent is added, return false
        if self._exist_only_in_first(tokens[:-1], simulated_config_ptr, current_config_ptr):
            return False

        # otherwise parent exist and value is added
        return True

    def _value_removed_but_parent_remain(self, tokens, current_config_ptr, simulated_config_ptr):
        # if value is not removed, return false
        if not self._exist_only_in_first(tokens, current_config_ptr, simulated_config_ptr):
            return False

        # if parent is removed, return false
        if self._exist_only_in_first(tokens[:-1], current_config_ptr, simulated_config_ptr):
            return False

        # otherwise parent remained and value is removed
        return True

    def _exist_only_in_first(self, tokens, first_config_ptr, second_config_ptr):
        for token in tokens:
            mod_token = int(token) if isinstance(first_config_ptr, list) else token

            if mod_token not in second_config_ptr:
                return True

            if mod_token not in first_config_ptr:
                return False

            first_config_ptr = first_config_ptr[mod_token]
            second_config_ptr = second_config_ptr[mod_token]

        # tokens exist in both
        return False

class NoDependencyMoveValidator:
    """
    A class to validate that the modified configs do not have dependency on each other. This should prevent
    moves that update whole config in a single step where multiple changed nodes are dependent on each. This
    way dependent configs are never updated together.
    """
    def __init__(self, path_addressing, config_wrapper):
        self.path_addressing = path_addressing
        self.config_wrapper = config_wrapper

    def validate(self, move, diff):
        operation_type = move.op_type
        path = move.path

        if operation_type == OperationType.ADD:
            simulated_config = move.apply(diff.current_config)
            # For add operation, we check the simulated config has no dependencies between nodes under the added path
            if not self._validate_paths_config([path], simulated_config):
                return False
        elif operation_type == OperationType.REMOVE:
            # For remove operation, we check the current config has no dependencies between nodes under the removed path
            if not self._validate_paths_config([path], diff.current_config):
                return False
        elif operation_type == OperationType.REPLACE:
            if not self._validate_replace(move, diff):
                return False

        return True

    # NOTE: this function can be used for validating JsonChange as well which might have more than one move.
    def _validate_replace(self, move, diff):
        """
        The table below shows how mixed deletion/addition within replace affect this validation.

        The table is answring the question whether the change is valid:
          Y = Yes
          N = No
          n/a = not applicable as the change itself is not valid

        symbols meaning;
          +A, -A: adding, removing config A
          +refA, -refA: adding, removing a reference to A config


           +refA|-refA|refA
        --|-----|-----|----
        +A| N   | n/a | n/a
        -A| n/a | N   | n/a
         A| Y   | Y   | Y

        The conclusion is that:
        +A, +refA is invalid because there is a dependency and a single move should not have dependency
        -A, -refA is invalid because there is a dependency and a single move should not have dependency
        A kept unchanged can be ignored, as it is always OK regardless of what happens to its reference
        Other states are all non applicable since they are invalid to begin with

        So verification would be:
        if A is deleted and refA is deleted: return False
        if A is added and refA is added: return False
        return True
        """
        simulated_config = move.apply(diff.current_config)
        deleted_paths, added_paths = self._get_paths(diff.current_config, simulated_config, [])

        # For deleted paths, we check the current config has no dependencies between nodes under the removed path
        if not self._validate_paths_config(deleted_paths, diff.current_config):
            return False

        # For added paths, we check the simulated config has no dependencies between nodes under the added path
        if not self._validate_paths_config(added_paths, simulated_config):
            return False

        return True

    def _get_paths(self, current_ptr, target_ptr, tokens):
        deleted_paths = []
        added_paths = []

        if isinstance(current_ptr, list) or isinstance(target_ptr, list):
            tmp_deleted_paths, tmp_added_paths = self._get_list_paths(current_ptr, target_ptr, tokens)
            deleted_paths.extend(tmp_deleted_paths)
            added_paths.extend(tmp_added_paths)
            return deleted_paths, added_paths

        if isinstance(current_ptr, dict):
            for token in current_ptr:
                tokens.append(token)
                if token not in target_ptr:
                    deleted_paths.append(self.path_addressing.create_path(tokens))
                else:
                    tmp_deleted_paths, tmp_added_paths = self._get_paths(current_ptr[token], target_ptr[token], tokens)
                    deleted_paths.extend(tmp_deleted_paths)
                    added_paths.extend(tmp_added_paths)
                tokens.pop()

            for token in target_ptr:
                tokens.append(token)
                if token not in current_ptr:
                    added_paths.append(self.path_addressing.create_path(tokens))
                tokens.pop()

            return deleted_paths, added_paths
        
        # current/target configs are not dict nor list, so handle them as string, int, bool, float
        if current_ptr != target_ptr:
            # tokens.append(token)
            deleted_paths.append(self.path_addressing.create_path(tokens))
            added_paths.append(self.path_addressing.create_path(tokens))
            # tokens.pop()

        return deleted_paths, added_paths

    def _get_list_paths(self, current_list, target_list, tokens):
        """
        Gets all paths within the given list, assume list items are unique
        """
        deleted_paths = []
        added_paths = []

        hashed_target = set(target_list)
        for index, value in enumerate(current_list):
            if value not in hashed_target:
                tokens.append(index)
                deleted_paths.append(self.path_addressing.create_path(tokens))
                tokens.pop()

        hashed_current = set(current_list)
        for index, value in enumerate(target_list):
            if value not in hashed_current:
                tokens.append(index)
                # added_paths refer to paths in the target config and not necessarily the current config
                added_paths.append(self.path_addressing.create_path(tokens))
                tokens.pop()

        return deleted_paths, added_paths

    def _validate_paths_config(self, paths, config):
        """
        validates all config under paths do not have config and its references
        """
        refs = self._find_ref_paths(paths, config)
        for ref in refs:
            for path in paths:
                if ref.startswith(path):
                    return False

        return True

    def _find_ref_paths(self, paths, config):
        refs = []
        for path in paths:
            refs.extend(self.path_addressing.find_ref_paths(path, config))
        return refs

class NoEmptyTableMoveValidator:
    """
    A class to validate that a move will not result in an empty table, because empty table do not show up in ConfigDB.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

    def validate(self, move, diff):
        simulated_config = move.apply(diff.current_config)
        op_path = move.path

        if op_path == "": # If updating whole file
            tables_to_check = simulated_config.keys()
        else:
            tokens = self.path_addressing.get_path_tokens(op_path)
            tables_to_check = [tokens[0]]

        return self._validate_tables(tables_to_check, simulated_config)

    def _validate_tables(self, tables, config):
        for table in tables:
            if not(self._validate_table(table, config)):
                return False
        return True

    def _validate_table(self, table, config):
        # the only invalid case is if table exists and is empty
        return table not in config or config[table]

class LowLevelMoveGenerator:
    """
    A class to generate the low level moves i.e. moves corresponding to differences between current/target config
    where the path of the move does not have children.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing
    def generate(self, diff):
        single_run_generator = SingleRunLowLevelMoveGenerator(diff, self.path_addressing)
        for move in single_run_generator.generate():
            yield move

class SingleRunLowLevelMoveGenerator:
    """
    A class that can only run once to assist LowLevelMoveGenerator with generating the moves.
    """
    def __init__(self, diff, path_addressing):
        self.diff = diff
        self.path_addressing = path_addressing

    def generate(self):
        current_ptr = self.diff.current_config
        target_ptr = self.diff.target_config
        current_tokens = []
        target_tokens = []

        for move in self._traverse(current_ptr, target_ptr, current_tokens, target_tokens):
            yield move

    def _traverse(self, current_ptr, target_ptr, current_tokens, target_tokens):
        """
        Traverses the current/target config trees.
        The given ptrs can be:
          dict
          list of string, number, boolean, int
          string, number, boolean, int

        list of dict is not allowed
        """
        if isinstance(current_ptr, list) or isinstance(target_ptr, list):
            for move in self._traverse_list(current_ptr, target_ptr, current_tokens, target_tokens):
                yield move
            return

        if isinstance(current_ptr, dict) or isinstance(target_ptr, dict):
            for key in current_ptr:
                current_tokens.append(key)
                if key in target_ptr:
                    target_tokens.append(key)
                    for move in self._traverse(current_ptr[key], target_ptr[key], current_tokens, target_tokens):
                        yield move
                    target_tokens.pop()
                else:
                    for move in self._traverse_current(current_ptr[key], current_tokens):
                        yield move

                current_tokens.pop()

            for key in target_ptr:
                if key in current_ptr:
                    continue # Already tried in the previous loop

                target_tokens.append(key)
                current_tokens.append(key)
                for move in self._traverse_target(target_ptr[key], current_tokens, target_tokens):
                    yield move
                current_tokens.pop()
                target_tokens.pop()
            
            return

        # The current/target ptr are neither dict nor list, so they might be string, int, float, bool
        for move in self._traverse_value(current_ptr, target_ptr, current_tokens, target_tokens):
            yield move

    def _traverse_list(self, current_ptr, target_ptr, current_tokens, target_tokens):
        # if same elements different order, just sort by replacing whole list
        # Example:
        #   current: [1, 2, 3, 4]
        #   target: [4, 3, 2, 1]
        #   returned move: REPLACE, current, target
        current_dict_cnts = self._list_to_dict_with_count(current_ptr)
        target_dict_cnts = self._list_to_dict_with_count(target_ptr)
        if current_dict_cnts == target_dict_cnts:
            for move in self._traverse_value(current_ptr, target_ptr, current_tokens, target_tokens):
                yield move
            return

        # Otherwise try add missing and remove additional elements
        # Try remove
        if current_ptr is not None:
            for current_index, current_item in enumerate(current_ptr):
                if current_dict_cnts[current_item] > target_dict_cnts.get(current_item, 0):
                    current_tokens.append(current_index)
                    for move in self._traverse_current_value(current_item, current_tokens):
                        yield move
                    current_tokens.pop()
        # Try add
        if target_ptr is not None:
            current_cnt = len(current_ptr) if current_ptr is not None else 0
            for target_index, target_item in enumerate(target_ptr):
                if target_dict_cnts[target_item] > current_dict_cnts.get(target_item, 0):
                    index = min(current_cnt, target_index)
                    current_tokens.append(index)
                    target_tokens.append(target_index)
                    for move in self._traverse_target_value(target_item, current_tokens, target_tokens):
                        yield move
                    target_tokens.pop()
                    current_tokens.pop()

        # Try replace
        if current_ptr is not None and target_ptr is not None:
            for current_index, current_item in enumerate(current_ptr):
                for target_index, target_item in enumerate(target_ptr):
                    if current_dict_cnts[current_item] > target_dict_cnts.get(current_item, 0) and \
                    target_dict_cnts[target_item] > current_dict_cnts.get(target_item, 0):
                        current_tokens.append(current_index)
                        target_tokens.append(target_index)
                        for move in self._traverse_value(current_item, target_item, current_tokens, target_tokens):
                            yield move
                        target_tokens.pop()
                        current_tokens.pop()

    def _traverse_value(self, current_value, target_value, current_tokens, target_tokens):
        if current_value == target_value:
            return

        yield JsonMove(self.diff, OperationType.REPLACE, current_tokens, target_tokens)

    def _traverse_current(self, ptr, current_tokens):
        if isinstance(ptr, list):
            for move in self._traverse_current_list(ptr, current_tokens):
                yield move
            return

        if isinstance(ptr, dict):
            if len(ptr) == 0:
                yield JsonMove(self.diff, OperationType.REMOVE, current_tokens)
                return

            for key in ptr:
                current_tokens.append(key)
                for move in self._traverse_current(ptr[key], current_tokens):
                    yield move
                current_tokens.pop()

            return

        # ptr is not a dict nor a list, it can be string, int, float, bool
        for move in self._traverse_current_value(ptr, current_tokens):
            yield move

    def _traverse_current_list(self, ptr, current_tokens):
        if len(ptr) == 0:
            yield JsonMove(self.diff, OperationType.REMOVE, current_tokens)
            return

        for index, val in enumerate(ptr):
            current_tokens.append(index)
            for move in self._traverse_current_value(val, current_tokens):
                yield move
            current_tokens.pop()

    def _traverse_current_value(self, val, current_tokens):
        yield JsonMove(self.diff, OperationType.REMOVE, current_tokens)

    def _traverse_target(self, ptr, current_tokens, target_tokens):
        if isinstance(ptr, list):
            for move in self._traverse_target_list(ptr, current_tokens, target_tokens):
                yield move
            return

        if isinstance(ptr, dict):
            if len(ptr) == 0:
                yield JsonMove(self.diff, OperationType.ADD, current_tokens, target_tokens)
                return

            for key in ptr:
                current_tokens.append(key)
                target_tokens.append(key)
                for move in self._traverse_target(ptr[key], current_tokens, target_tokens):
                    yield move
                target_tokens.pop()
                current_tokens.pop()

            return

        # target configs are not dict nor list, so handle them as string, int, bool, float
        for move in self._traverse_target_value(ptr, current_tokens, target_tokens):
            yield move

    def _traverse_target_list(self, ptr, current_tokens, target_tokens):
        if len(ptr) == 0:
            yield JsonMove(self.diff, OperationType.ADD, current_tokens, target_tokens)
            return

        for index, val in enumerate(ptr):
            # _traverse_target_list is called when the whole list is missing
            # in such case any item should be added at first location i.e. 0
            current_tokens.append(0)
            target_tokens.append(index)
            for move in self._traverse_target_value(val, current_tokens, target_tokens):
                yield move
            target_tokens.pop()
            current_tokens.pop()

    def _traverse_target_value(self, val, current_tokens, target_tokens):
        yield JsonMove(self.diff, OperationType.ADD, current_tokens, target_tokens)

    def _list_to_dict_with_count(self, items):
        counts = dict()

        if items is None:
            return counts

        for item in items:
            counts[item] = counts.get(item, 0) + 1

        return counts

class UpperLevelMoveExtender:
    """
    A class to extend the given move by including its parent. It has 3 cases:
      1) If parent was in current and target, then replace the parent
      2) If parent was in current but not target, then delete the parent
      3) If parent was in target but not current, then add the parent
    """
    def extend(self, move, diff):
        # if no tokens i.e. whole config
        if not move.current_config_tokens:
            return

        upper_current_tokens = move.current_config_tokens[:-1]
        operation_type = self._get_upper_operation(upper_current_tokens, diff)

        upper_target_tokens = None
        if operation_type in [OperationType.ADD, OperationType.REPLACE]:
            upper_target_tokens = upper_current_tokens

        yield JsonMove(diff, operation_type, upper_current_tokens, upper_target_tokens)

    # get upper operation assumes ConfigDb to not have list-of-objects, only list-of-values
    def _get_upper_operation(self, tokens, diff):
        current_ptr = diff.current_config
        target_ptr = diff.target_config

        for token in tokens:
            if token not in current_ptr:
                return OperationType.ADD
            current_ptr = current_ptr[token]
            if token not in target_ptr:
                return OperationType.REMOVE
            target_ptr = target_ptr[token]

        return OperationType.REPLACE

class DeleteInsteadOfReplaceMoveExtender:
    """
    A class to extend the given REPLACE move by adding a REMOVE move.
    """
    def extend(self, move, diff):
        operation_type = move.op_type

        if operation_type != OperationType.REPLACE:
            return

        new_move = JsonMove(diff, OperationType.REMOVE, move.current_config_tokens)

        yield new_move

class DeleteRefsMoveExtender:
    """
    A class to extend the given DELETE move by adding DELETE moves to configs referring to the path in the move.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

    def extend(self, move, diff):
        operation_type = move.op_type

        if operation_type != OperationType.REMOVE:
            return

        for ref_path in self.path_addressing.find_ref_paths(move.path, diff.current_config):
            yield JsonMove(diff, OperationType.REMOVE, self.path_addressing.get_path_tokens(ref_path))

class DfsSorter:
    def __init__(self, move_wrapper):
        self.visited = {}
        self.move_wrapper = move_wrapper

    def sort(self, diff):
        if diff.has_no_diff():
            return []

        diff_hash = hash(diff)
        if diff_hash in self.visited:
            return None
        self.visited[diff_hash] = True

        moves = self.move_wrapper.generate(diff)

        for move in moves:
            if self.move_wrapper.validate(move, diff):
                new_diff = self.move_wrapper.simulate(move, diff)
                new_moves = self.sort(new_diff)
                if new_moves is not None:
                    return [move] + new_moves

        return None

class BfsSorter:
    def __init__(self, move_wrapper):
        self.visited = {}
        self.move_wrapper = move_wrapper

    def sort(self, diff):
        diff_queue = deque([])
        prv_moves_queue = deque([])

        diff_queue.append(diff)
        prv_moves_queue.append([])

        while len(diff_queue):
            diff = diff_queue.popleft()
            prv_moves = prv_moves_queue.popleft()

            diff_hash = hash(diff)
            if diff_hash in self.visited:
                continue
            self.visited[diff_hash] = True

            if diff.has_no_diff():
                return prv_moves

            moves = self.move_wrapper.generate(diff)
            for move in moves:
                if self.move_wrapper.validate(move, diff):
                    new_diff = self.move_wrapper.simulate(move, diff)
                    new_prv_moves = prv_moves + [move]

                    diff_queue.append(new_diff)
                    prv_moves_queue.append(new_prv_moves)

        return None

class MemoizationSorter:
    def __init__(self, move_wrapper):
        self.visited = {}
        self.move_wrapper = move_wrapper
        self.mem = {}

    def sort(self, diff):
        if diff.has_no_diff():
            return []

        diff_hash = hash(diff)
        if diff_hash in self.mem:
            return self.mem[diff_hash]
        if diff_hash in self.visited:
            return None
        self.visited[diff_hash] = True

        moves = self.move_wrapper.generate(diff)

        bst_moves = None
        for move in moves:
            if self.move_wrapper.validate(move, diff):
                new_diff = self.move_wrapper.simulate(move, diff)
                new_moves = self.sort(new_diff)
                if new_moves != None and (bst_moves is None or len(bst_moves) > len(new_moves)+1):
                    bst_moves = [move] + new_moves

        self.mem[diff_hash] = bst_moves
        return bst_moves

class Algorithm(Enum):
    DFS = 1
    BFS = 2
    MEMOIZATION = 3

class SortAlgorithmFactory:
    def __init__(self, operation_wrapper, config_wrapper, path_addressing):
        self.operation_wrapper = operation_wrapper
        self.config_wrapper = config_wrapper
        self.path_addressing = path_addressing

    def create(self, algorithm=Algorithm.DFS):
        move_generators = [LowLevelMoveGenerator(self.path_addressing)]
        move_extenders = [UpperLevelMoveExtender(),
                          DeleteInsteadOfReplaceMoveExtender(),
                          DeleteRefsMoveExtender(self.path_addressing)]
        move_validators = [DeleteWholeConfigMoveValidator(),
                           FullConfigMoveValidator(self.config_wrapper),
                           NoDependencyMoveValidator(self.path_addressing, self.config_wrapper),
                           UniqueLanesMoveValidator(),
                           CreateOnlyMoveValidator(self.path_addressing),
                           NoEmptyTableMoveValidator(self.path_addressing)]

        move_wrapper = MoveWrapper(move_generators, move_extenders, move_validators)

        if algorithm == Algorithm.DFS:
            sorter = DfsSorter(move_wrapper)
        elif algorithm == Algorithm.BFS:
            sorter = BfsSorter(move_wrapper)
        elif algorithm == Algorithm.MEMOIZATION:
            sorter = MemoizationSorter(move_wrapper)
        else:
            raise ValueError(f"Algorithm {algorithm} is not supported")

        return sorter

class StrictPatchSorter:
    def __init__(self, config_wrapper, patch_wrapper, inner_patch_sorter=None):
        self.logger = genericUpdaterLogging.get_logger(title="Patch Sorter - Strict", print_all_to_console=True)
        self.config_wrapper = config_wrapper
        self.patch_wrapper = patch_wrapper
        self.inner_patch_sorter = inner_patch_sorter if inner_patch_sorter else PatchSorter(config_wrapper, patch_wrapper)

    def sort(self, patch, algorithm=Algorithm.DFS):
        current_config = self.config_wrapper.get_config_db_as_json()

        # Validate patch is only updating tables with yang models
        self.logger.log_info("Validating patch is not making changes to tables without YANG models.")
        if not(self.patch_wrapper.validate_config_db_patch_has_yang_models(patch)):
            raise ValueError(f"Given patch is not valid because it has changes to tables without YANG models")

        target_config = self.patch_wrapper.simulate_patch(patch, current_config)

        # Validate target config
        self.logger.log_info("Validating target config according to YANG models.")
        if not(self.config_wrapper.validate_config_db_config(target_config)):
            raise ValueError(f"Given patch is not valid because it will result in an invalid config")

        # Generate list of changes to apply
        self.logger.log_info("Sorting patch updates.")
        changes = self.inner_patch_sorter.sort(patch, algorithm)

        return changes

class TablesWithoutYangConfigSplitter:
    def __init__(self, config_wrapper):
        self.config_wrapper = config_wrapper

    def split_yang_non_yang_distinct_field_path(self, config):
        config_with_yang = self.config_wrapper.crop_tables_without_yang(config)
        config_without_yang = {}

        for key in config:
            if key not in config_with_yang:
                config_without_yang[key] = copy.deepcopy(config[key])

        return config_with_yang, config_without_yang

class IgnorePathsFromYangConfigSplitter:
    def __init__(self, ignore_paths_from_yang_list, config_wrapper):
        self.ignore_paths_from_yang_list = ignore_paths_from_yang_list
        self.config_wrapper = config_wrapper
        self.path_addressing = PathAddressing(config_wrapper)

    def split_yang_non_yang_distinct_field_path(self, config):
        config_with_yang = copy.deepcopy(config)
        config_without_yang = {}

        # ignore more config from config_with_yang
        for path in self.ignore_paths_from_yang_list:
            if not self.path_addressing.has_path(config_with_yang, path):
                continue
            if path == '': # whole config to be ignored
                return {}, copy.deepcopy(config)

            # Add to config_without_yang from config_with_yang
            tokens = self.path_addressing.get_path_tokens(path)
            add_move = JsonMove(Diff(config_without_yang, config_with_yang), OperationType.ADD, tokens, tokens)
            config_without_yang = add_move.apply(config_without_yang)

            # Remove from config_with_yang
            remove_move = JsonMove(Diff(config_with_yang, {}), OperationType.REMOVE, tokens)
            config_with_yang = remove_move.apply(config_with_yang)

        # Splitting the config based on 'ignore_paths_from_yang_list' can result in empty tables.
        # Remove empty tables because they are not allowed in ConfigDb
        config_with_yang_without_empty_tables = self.config_wrapper.remove_empty_tables(config_with_yang)
        config_without_yang_without_empty_tables = self.config_wrapper.remove_empty_tables(config_without_yang)
        return config_with_yang_without_empty_tables, config_without_yang_without_empty_tables

class ConfigSplitter:
    def __init__(self, config_wrapper, inner_config_splitters):
        self.config_wrapper = config_wrapper
        self.inner_config_splitters = inner_config_splitters

    def split_yang_non_yang_distinct_field_path(self, config):
        empty_tables = self.config_wrapper.get_empty_tables(config)
        empty_tables_txt = ", ".join(empty_tables)
        if empty_tables:
            raise ValueError(f"Given config has empty tables. Table{'s' if len(empty_tables) != 1 else ''}: {empty_tables_txt}")

        # Start by assuming all config should be YANG covered
        config_with_yang = copy.deepcopy(config)
        config_without_yang = {}

        for config_splitter in self.inner_config_splitters:
            config_with_yang, additional_config_without_yang = config_splitter.split_yang_non_yang_distinct_field_path(config_with_yang)
            config_without_yang = self.merge_configs_with_distinct_field_path(config_without_yang, additional_config_without_yang)

        return config_with_yang, config_without_yang

    def merge_configs_with_distinct_field_path(self, config1, config2):
        merged_config = copy.deepcopy(config1)
        self.__recursive_append(merged_config, config2)
        return merged_config

    def __recursive_append(self, target, additional, path=""):
        if not isinstance(target, dict):
            raise ValueError(f"Found a field that exist in both config1 and config2. Path: {path}")
        for key in additional:
            if key not in target:
                target[key] = copy.deepcopy(additional[key])
            else:
                self.__recursive_append(target[key], additional[key], f"{path}/{key}")

class ChangeWrapper:
    def __init__(self, patch_wrapper, config_splitter):
        self.patch_wrapper = patch_wrapper
        self.config_splitter = config_splitter

    def adjust_changes(self, assumed_changes, assumed_curr_config, remaining_distinct_curr_config):
        """
        The merging of 'assumed_curr_config' and 'remaining_distinct_curr_config' will generate the full config.
        The list of 'assumed_changes' are applicable to 'assumed_curr_config' but they cannot be applied directly to the full config.
        'assumed_changes' can blindly alter existing config in 'remaining_distinct_curr_config' but they should not. Check example below.

        Example:
          assumed_curr_config:
          {
            "ACL_TABLE":
            {
              "Everflow": { "type": "L3" }
            }
          }

          remaining_distinct_curr_config:
          {
            "ACL_TABLE":
            {
              "Everflow": { "policy_desc": "some-description" }
            }
          }

          assumed_changes (these are only applicable to assumed_curr_config):
          {
            [{"op":"replace", "path":"/ACL_TABLE/EVERFLOW", "value":{"type":"MIRROR"}}]
          }

          The merging of assumed_curr_config and remaining_distinct_curr_config to get the full config is:
          {
            "ACL_TABLE":
            {
              "Everflow": { "type": "L3", "policy_desc": "some-description" }
            }
          }

          Applying changes to the merging i.e. full config will result in:
          {
            "ACL_TABLE":
            {
              "Everflow": { "type": "MIRROR" }
            }
          }

          This is not correct, as we have deleted /ACL_TABLE/EVERFLOW/policy_desc
          This problem happend because we used 'assumed_changes' for 'assumed_curr_config' on the full config.

          The solution is to adjust the 'assumed_changes' list to be:
          {
            [{"op":"replace", "path":"/ACL_TABLE/EVERFLOW/type", "value":"MIRROR"}]
          }

          This method adjust the given 'assumed_changes' to be applicable to the full config.

          Check unit-test for more examples.
       """
        adjusted_changes = []
        assumed_curr_config = copy.deepcopy(assumed_curr_config)
        for change in assumed_changes:
            assumed_target_config = change.apply(assumed_curr_config)

            adjusted_curr_config = self.config_splitter.merge_configs_with_distinct_field_path(assumed_curr_config, remaining_distinct_curr_config)
            adjusted_target_config = self.config_splitter.merge_configs_with_distinct_field_path(assumed_target_config, remaining_distinct_curr_config)

            adjusted_patch = self.patch_wrapper.generate_patch(adjusted_curr_config, adjusted_target_config)

            adjusted_change = JsonChange(adjusted_patch)
            adjusted_changes.append(adjusted_change)

            assumed_curr_config = assumed_target_config

        return adjusted_changes

class NonStrictPatchSorter:
    def __init__(self, config_wrapper, patch_wrapper, config_splitter, change_wrapper=None, patch_sorter=None):
        self.logger = genericUpdaterLogging.get_logger(title="Patch Sorter - Non-Strict", print_all_to_console=True)
        self.config_wrapper = config_wrapper
        self.patch_wrapper = patch_wrapper
        self.config_splitter = config_splitter
        self.change_wrapper = change_wrapper if change_wrapper else ChangeWrapper(patch_wrapper, config_splitter)
        self.inner_patch_sorter = patch_sorter if patch_sorter else PatchSorter(config_wrapper, patch_wrapper)

    def sort(self, patch, algorithm=Algorithm.DFS):
        current_config = self.config_wrapper.get_config_db_as_json()
        target_config = self.patch_wrapper.simulate_patch(patch, current_config)

        # Splitting current/target config based on YANG covered vs non-YANG covered configs
        self.logger.log_info("Splitting current/target config based on YANG covered vs non-YANG covered configs.")
        current_config_yang, current_config_non_yang = self.config_splitter.split_yang_non_yang_distinct_field_path(current_config)
        target_config_yang, target_config_non_yang = self.config_splitter.split_yang_non_yang_distinct_field_path(target_config)

        # Validate YANG covered target config
        self.logger.log_info("Validating YANG covered target config according to YANG models.")
        if not(self.config_wrapper.validate_config_db_config(target_config_yang)):
            raise ValueError(f"Given patch is not valid because it will result in an invalid config")

        # Generating changes associated with non-YANG covered configs
        self.logger.log_info("Sorting non-YANG covered configs patch updates.")
        non_yang_patch = self.patch_wrapper.generate_patch(current_config_non_yang, target_config_non_yang)
        non_yang_changes = [JsonChange(non_yang_patch)] if non_yang_patch else []
        changes_len = len(non_yang_changes)
        self.logger.log_debug(f"The Non-YANG covered config update was sorted into {changes_len} " \
                             f"change{'s' if changes_len != 1 else ''}{':' if changes_len > 0 else '.'}")
        for change in non_yang_changes:
            self.logger.log_debug(f"  * {change}")

        # Regenerating patch for YANG covered configs
        self.logger.log_info("Regenerating patch for YANG covered configs only.")
        yang_patch = self.patch_wrapper.generate_patch(current_config_yang, target_config_yang)
        self.logger.log_info(f"Generated patch {yang_patch}")

        # Validate YANG covered config patch is only updating tables with yang models
        self.logger.log_info("Validating YANG covered config patch is not making changes to tables without YANG models.")
        if not(self.patch_wrapper.validate_config_db_patch_has_yang_models(yang_patch)):
            raise ValueError(f"Given YANG covered config patch is not valid because it has changes to tables without YANG models")

        # Generating changes associated with YANG covered configs
        self.logger.log_info("Sorting YANG-covered configs patch updates.")
        yang_changes = self.inner_patch_sorter.sort(yang_patch, algorithm, current_config_yang)
        changes_len = len(yang_changes)
        self.logger.log_debug(f"The YANG covered config update was sorted into {changes_len} " \
                             f"change{'s' if changes_len != 1 else ''}{':' if changes_len > 0 else '.'}")
        for change in yang_changes:
            self.logger.log_debug(f"  * {change}")

        # Merging non-YANG and YANG covered changes.
        self.logger.log_info("Merging non-YANG and YANG covered changes.")
        adjusted_non_yang_changes = self.change_wrapper.adjust_changes(non_yang_changes, current_config_non_yang, current_config_yang)
        adjusted_yang_changes = self.change_wrapper.adjust_changes(yang_changes, current_config_yang, target_config_non_yang)
        changes = adjusted_non_yang_changes + adjusted_yang_changes

        return changes

class PatchSorter:
    def __init__(self, config_wrapper, patch_wrapper, sort_algorithm_factory=None):
        self.config_wrapper = config_wrapper
        self.patch_wrapper = patch_wrapper
        self.operation_wrapper = OperationWrapper()
        self.path_addressing = PathAddressing(self.config_wrapper)
        self.sort_algorithm_factory = sort_algorithm_factory if sort_algorithm_factory else \
            SortAlgorithmFactory(self.operation_wrapper, config_wrapper, self.path_addressing)

    def sort(self, patch, algorithm=Algorithm.DFS, preloaded_current_config=None):
        current_config = preloaded_current_config if preloaded_current_config else self.config_wrapper.get_config_db_as_json()
        target_config = self.patch_wrapper.simulate_patch(patch, current_config)

        diff = Diff(current_config, target_config)

        sort_algorithm = self.sort_algorithm_factory.create(algorithm)
        moves = sort_algorithm.sort(diff)

        if moves is None:
            raise GenericConfigUpdaterError("There is no possible sorting")

        changes = [JsonChange(move.patch) for move in moves]

        return changes
