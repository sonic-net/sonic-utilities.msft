import os
import sys
from click.testing import CliRunner
from utilities_common.db import Db

show_server_output_0="""\
Kubernetes server is not configured
"""

show_server_output_1="""\
KUBERNETES_MASTER SERVER IP 10.10.10.11
KUBERNETES_MASTER SERVER insecure False
KUBERNETES_MASTER SERVER disable False
"""

show_server_output_2="""\
KUBERNETES_MASTER SERVER IP 10.10.10.11
KUBERNETES_MASTER SERVER insecure True
KUBERNETES_MASTER SERVER disable False
"""

show_server_output_3="""\
KUBERNETES_MASTER SERVER IP 10.10.10.11
KUBERNETES_MASTER SERVER insecure True
KUBERNETES_MASTER SERVER disable True
"""


class kube(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")


    def __check_res(self, result, info, op):
        print("Running test: {}".format(info))
        print result.exit_code
        print result.output
        assert result.exit_code == 0
        assert "\n".join([ l.rstrip() for l in result.output.split('\n')]) == op



    def test_kube_server(self, get_cmd_module):
        (config, show) = get_cmd_module
        db = Db()
        runner = CliRunner()

        # Check server not configured
        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"])
        self.__check_res(result, "empty server test", show_server_output_0)

        # Add IP & test show
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["ip", "10.10.10.11"], obj=db)
        self.__check_res(result, "set server IP", "")
        
        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"])
        self.__check_res(result, "check server IP", show_server_output_1)


        # set insecure as True & test show
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["insecure", "on"], obj=db)
        self.__check_res(result, "set server insecure", "")
        
        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"])
        self.__check_res(result, "check server IP", show_server_output_2)
        
        # set disable as True & test show
        result = runner.invoke(config.config.commands["kubernetes"].commands["server"], ["disable", "on"], obj=db)
        self.__check_res(result, "set server disable", "")
        
        result = runner.invoke(show.cli.commands["kubernetes"].commands["server"])
        self.__check_res(result, "check server IP", show_server_output_3)

    

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")


