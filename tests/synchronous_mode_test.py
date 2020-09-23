from click.testing import CliRunner
import config.main as config

class TestSynchronousMode(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def __check_result(self, result_msg, mode):
        if mode == "enable" or mode == "disable":
            expected_msg = """Wrote %s synchronous mode into CONFIG_DB, swss restart required to apply the configuration: \n
    Option 1. config save -y \n
              config reload -y \n
    Option 2. systemctl restart swss""" % mode
        else:
            expected_msg = "Error: Invalid argument %s, expect either enable or disable" % mode

        return expected_msg in result_msg


    def test_synchronous_mode(self):
        runner = CliRunner()

        result = runner.invoke(config.config.commands["synchronous_mode"], ["enable"])
        print(result.output)
        assert result.exit_code == 0
        assert self.__check_result(result.output, "enable")

        result = runner.invoke(config.config.commands["synchronous_mode"], ["disable"])
        print(result.output)
        assert result.exit_code == 0
        assert self.__check_result(result.output, "disable")

        result = runner.invoke(config.config.commands["synchronous_mode"], ["invalid-input"])
        print(result.output)
        assert result.exit_code != 0
        assert self.__check_result(result.output, "invalid-input")
