import copy
import json
import jsonpatch
from collections import deque
from enum import Enum
from .gu_common import OperationWrapper, OperationType, GenericConfigUpdaterError, JsonChange, PathAddressing

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
    A class to validate create-only fields are only added/removed but never replaced.
    Parents of create-only fields are also only added/removed but never replaced when they contain
    a modified create-only field.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

    def validate(self, move, diff):
        if move.op_type != OperationType.REPLACE:
            return True

        # The 'create-only' field needs to be common between current and simulated anyway but different.
        # This means it is enough to just get the paths from current_config, paths that are not common can be ignored.
        paths = self._get_create_only_paths(diff.current_config)
        simulated_config = move.apply(diff.current_config)

        for path in paths:
            tokens = self.path_addressing.get_path_tokens(path)
            if self._value_exist_but_different(tokens, diff.current_config, simulated_config):
                return False

        return True

    # TODO: create-only fields are hard-coded for now, it should be moved to YANG models
    def _get_create_only_paths(self, config):
        if "PORT" not in config:
            return

        ports = config["PORT"]

        for port in ports:
            attrs = ports[port]
            if "lanes" in attrs:
                yield f"/PORT/{port}/lanes"

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

        if not self._validate_paths_config(deleted_paths, diff.current_config):
            return False

        if not self._validate_paths_config(added_paths, diff.target_config):
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

    def rec(self, diff):
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
                           CreateOnlyMoveValidator(self.path_addressing) ]

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

class PatchSorter:
    def __init__(self, config_wrapper, patch_wrapper, sort_algorithm_factory=None):
        self.config_wrapper = config_wrapper
        self.patch_wrapper = patch_wrapper
        self.operation_wrapper = OperationWrapper()
        self.path_addressing = PathAddressing()
        self.sort_algorithm_factory = sort_algorithm_factory if sort_algorithm_factory else \
            SortAlgorithmFactory(self.operation_wrapper, config_wrapper, self.path_addressing)

    def sort(self, patch, algorithm=Algorithm.DFS):
        current_config = self.config_wrapper.get_config_db_as_json()
        target_config = self.patch_wrapper.simulate_patch(patch, current_config)

        diff = Diff(current_config, target_config)

        sort_algorithm = self.sort_algorithm_factory.create(algorithm)
        moves = sort_algorithm.sort(diff)

        if moves is None:
            raise GenericConfigUpdaterError("There is no possible sorting")

        changes = [JsonChange(move.patch) for move in moves]

        return changes
