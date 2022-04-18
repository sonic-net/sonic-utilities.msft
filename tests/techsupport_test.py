import pytest
import show.main
from unittest.mock import patch, Mock
from click.testing import CliRunner

EXPECTED_BASE_COMMAND = 'sudo timeout --kill-after=300s -s SIGTERM --foreground '

@patch("show.main.run_command")
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], '30m generate_dump -v -t 5'),
            (['--since', '2 days ago'], "30m generate_dump -v -s '2 days ago' -t 5"),
            (['-g', '50'], '50m generate_dump -v -t 5'),
            (['--allow-process-stop'], '30m -a generate_dump -v -t 5'),
            (['--silent'], '30m generate_dump -t 5'),
            (['--debug-dump', '--redirect-stderr'], '30m generate_dump -v -d -t 5 -r'),
        ]
)
def test_techsupport(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.main.cli.commands['techsupport'], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)

