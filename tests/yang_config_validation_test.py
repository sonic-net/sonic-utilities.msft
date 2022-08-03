from click.testing import CliRunner
import config.main as config

class TestYangConfigValidation(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")

    def __check_result(self, result_msg, mode):
        if mode == "enable" or mode == "disable":
            expected_msg = """Wrote %s yang config validation into CONFIG_DB""" % mode
        else:
            expected_msg = "Error: Invalid argument %s, expect either enable or disable" % mode

        return expected_msg in result_msg

    def test_yang_config_validation(self):
        runner = CliRunner()

        result = runner.invoke(config.config.commands["yang_config_validation"], ["enable"])
        print(result.output)
        assert result.exit_code == 0
        assert self.__check_result(result.output, "enable")

        result = runner.invoke(config.config.commands["yang_config_validation"], ["disable"])
        print(result.output)
        assert result.exit_code == 0
        assert self.__check_result(result.output, "disable")

        result = runner.invoke(config.config.commands["yang_config_validation"], ["invalid-input"])
        print(result.output)
        assert result.exit_code != 0
        assert self.__check_result(result.output, "invalid-input")
