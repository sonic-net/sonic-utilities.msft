import pytest
import os
import logging
import show.main as show
import config.main as config

from click.testing import CliRunner
from utilities_common.db import Db
from .mock_tables import dbconnector
from .hash_input import assert_show_output


test_path = os.path.dirname(os.path.abspath(__file__))
input_path = os.path.join(test_path, "hash_input")
mock_config_path = os.path.join(input_path, "mock_config")
mock_state_path = os.path.join(input_path, "mock_state")

logger = logging.getLogger(__name__)


HASH_FIELD_LIST = [
    "DST_MAC",
    "SRC_MAC",
    "ETHERTYPE",
    "IP_PROTOCOL",
    "DST_IP",
    "SRC_IP",
    "L4_DST_PORT",
    "L4_SRC_PORT"
]
INNER_HASH_FIELD_LIST = [
    "INNER_DST_MAC",
    "INNER_SRC_MAC",
    "INNER_ETHERTYPE",
    "INNER_IP_PROTOCOL",
    "INNER_DST_IP",
    "INNER_SRC_IP",
    "INNER_L4_DST_PORT",
    "INNER_L4_SRC_PORT"
]

SUCCESS = 0
ERROR2 = 2


class TestHash:
    @classmethod
    def setup_class(cls):
        logger.info("Setup class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        dbconnector.dedicated_dbs["STATE_DB"] = os.path.join(mock_state_path, "ecmp_and_lag")

    @classmethod
    def teardown_class(cls):
        logger.info("Teardown class: {}".format(cls.__name__))
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        dbconnector.dedicated_dbs.clear()


    ########## CONFIG SWITCH-HASH GLOBAL ##########


    @pytest.mark.parametrize(
        "hash", [
            "ecmp-hash",
            "lag-hash"
        ]
    )
    @pytest.mark.parametrize(
        "args", [
            pytest.param(
                " ".join(HASH_FIELD_LIST),
                id="outer-frame"
            ),
            pytest.param(
                " ".join(INNER_HASH_FIELD_LIST),
                id="inner-frame"
            )
        ]
    )
    def test_config_hash(self, hash, args):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].
            commands[hash], args, obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize(
        "hash", [
            "ecmp-hash",
            "lag-hash"
        ]
    )
    @pytest.mark.parametrize(
        "args,pattern", [
            pytest.param(
                "DST_MAC1 SRC_MAC ETHERTYPE",
                "invalid choice: DST_MAC1.",
                id="INVALID,SRC_MAC,ETHERTYPE"
            ),
            pytest.param(
                "DST_MAC SRC_MAC1 ETHERTYPE",
                "invalid choice: SRC_MAC1.",
                id="DST_MAC,INVALID,ETHERTYPE"
            ),
            pytest.param(
                "DST_MAC SRC_MAC ETHERTYPE1",
                "invalid choice: ETHERTYPE1.",
                id="DST_MAC,SRC_MAC,INVALID"
            ),
            pytest.param(
                "DST_MAC DST_MAC SRC_MAC ETHERTYPE",
                "duplicate hash field(s) DST_MAC",
                id="DUPLICATE,SRC_MAC,ETHERTYPE"
            ),
            pytest.param(
                "DST_MAC DST_MAC SRC_MAC SRC_MAC ETHERTYPE",
                "duplicate hash field(s) DST_MAC, SRC_MAC",
                id="DUPLICATE,DUPLICATE,ETHERTYPE"
            ),
            pytest.param(
                "DST_MAC DST_MAC SRC_MAC SRC_MAC ETHERTYPE ETHERTYPE",
                "duplicate hash field(s) DST_MAC, SRC_MAC, ETHERTYPE",
                id="DUPLICATE,DUPLICATE,DUPLICATE"
            )
        ]
    )
    def test_config_hash_neg(self, hash, args, pattern):
        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            config.config.commands["switch-hash"].commands["global"].
            commands[hash], args, obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert pattern in result.output
        assert result.exit_code == ERROR2


    ########## SHOW SWITCH-HASH GLOBAL ##########


    @pytest.mark.parametrize(
        "cfgdb,output", [
            pytest.param(
                os.path.join(mock_config_path, "empty"),
                assert_show_output.show_hash_empty,
                id="empty"
            ),
            pytest.param(
                os.path.join(mock_config_path, "ecmp"),
                assert_show_output.show_hash_ecmp,
                id="ecmp"
            ),
            pytest.param(
                os.path.join(mock_config_path, "lag"),
                assert_show_output.show_hash_lag,
                id="lag"
            ),
            pytest.param(
                os.path.join(mock_config_path, "ecmp_and_lag"),
                assert_show_output.show_hash_ecmp_and_lag,
                id="all"
            )
        ]
    )
    def test_show_hash(self, cfgdb, output):
        dbconnector.dedicated_dbs["CONFIG_DB"] = cfgdb

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"].
            commands["global"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == output
        assert result.exit_code == SUCCESS

    @pytest.mark.parametrize(
        "statedb,output", [
            pytest.param(
                os.path.join(mock_state_path, "no_capabilities"),
                assert_show_output.show_hash_capabilities_no,
                id="no"
            ),
            pytest.param(
                os.path.join(mock_state_path, "not_applicable"),
                assert_show_output.show_hash_capabilities_na,
                id="na"
            ),
            pytest.param(
                os.path.join(mock_state_path, "empty"),
                assert_show_output.show_hash_capabilities_empty,
                id="empty"
            ),
            pytest.param(
                os.path.join(mock_state_path, "ecmp"),
                assert_show_output.show_hash_capabilities_ecmp,
                id="ecmp"
            ),
            pytest.param(
                os.path.join(mock_state_path, "lag"),
                assert_show_output.show_hash_capabilities_lag,
                id="lag"
            ),
            pytest.param(
                os.path.join(mock_state_path, "ecmp_and_lag"),
                assert_show_output.show_hash_capabilities_ecmp_and_lag,
                id="all"
            )
        ]
    )
    def test_show_hash_capabilities(self, statedb, output):
        dbconnector.dedicated_dbs["STATE_DB"] = statedb

        db = Db()
        runner = CliRunner()

        result = runner.invoke(
            show.cli.commands["switch-hash"].
            commands["capabilities"], [], obj=db
        )

        logger.debug("\n" + result.output)
        logger.debug(result.exit_code)

        assert result.output == output
        assert result.exit_code == SUCCESS
