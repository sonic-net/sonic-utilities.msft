import pytest
import config.main as config
from unittest import mock
from click.testing import CliRunner

ERR_MSG_IP_FAILURE = "does not appear to be an IPv4 or IPv6 network"
ERR_MSG_IP_VERSION_FAILURE = "not a valid IPv4 address"
ERR_MSG_VALUE_FAILURE = "Invalid value for"

def test_mirror_session_add():
    runner = CliRunner()

    # Verify invalid src_ip
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "400.1.1.1", "2.2.2.2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_FAILURE in result.stdout

    # Verify invalid dst_ip
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "256.2.2.2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_FAILURE in result.stdout

    # Verify invalid ip version
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1::1", "2::2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_VERSION_FAILURE in result.stdout

    # Verify invalid dscp
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "65536", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid ttl
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "256", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid gre
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "65536", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid queue
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "65", "65536"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Positive case
    with mock.patch('config.main.add_erspan') as mocked:
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, 10, 100, None)



def test_mirror_session_erspan_add():
    runner = CliRunner()

    # Verify invalid src_ip
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "400.1.1.1", "2.2.2.2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_FAILURE in result.stdout

    # Verify invalid dst_ip
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "256.2.2.2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_FAILURE in result.stdout

    # Verify invalid ip version
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1::1", "2::2", "8", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_IP_VERSION_FAILURE in result.stdout

    # Verify invalid dscp
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "65536", "63", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid ttl
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "256", "10", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid gre
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "65536", "100"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Verify invalid queue
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["erspan"].commands["add"],
            ["test_session", "1.1.1.1", "2.2.2.2", "6", "63", "65", "65536"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Positive case
    with mock.patch('config.main.add_erspan') as mocked:
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["erspan"].commands["add"],
                ["test_session", "100.1.1.1", "2.2.2.2", "8", "63", "10", "100"])

        mocked.assert_called_with("test_session", "100.1.1.1", "2.2.2.2", 8, 63, 10, 100, None, None, None)


def test_mirror_session_span_add():
    runner = CliRunner()

    # Verify invalid queue
    result = runner.invoke(
            config.config.commands["mirror_session"].commands["span"].commands["add"],
            ["test_session", "Ethernet0", "Ethernet4", "rx", "65536"])
    assert result.exit_code != 0
    assert ERR_MSG_VALUE_FAILURE in result.stdout

    # Positive case
    with mock.patch('config.main.add_span') as mocked:
        result = runner.invoke(
                config.config.commands["mirror_session"].commands["span"].commands["add"],
                ["test_session", "Ethernet0", "Ethernet4", "rx", "100"])

        mocked.assert_called_with("test_session", "Ethernet0", "Ethernet4", "rx", 100, None)

