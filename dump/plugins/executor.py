from abc import ABC, abstractmethod
from dump.match_infra import MatchEngine


class Executor(ABC):
    """
    Abstract Class which should be extended from in
    order to be included in the dump state CLI
    """

    ARG_NAME = "id"  # Arg Identifier
    CONFIG_FILE = ""  # Path to config file, if any

    def __init__(self, match_engine=None):
        if not isinstance(match_engine, MatchEngine):
            self.match_engine = MatchEngine(None)
        else:
            self.match_engine = match_engine

    @abstractmethod
    def execute(self, params):
        pass

    @abstractmethod
    def get_all_args(self, ns):
        pass
