import os
import sys

import show.main as show
import clear.main as clear
import config.main as config

from click.testing import CliRunner

test_path = os.path.dirname(os.path.abspath(__file__))
modules_path = os.path.dirname(test_path)
scripts_path = os.path.join(modules_path, "scripts")
sys.path.insert(0, test_path)
sys.path.insert(0, modules_path)


show_pg_dropped_packet_stat="""\
Ingress PG dropped packets:
     Port    PG0    PG1    PG2    PG3    PG4    PG5    PG6    PG7
---------  -----  -----  -----  -----  -----  -----  -----  -----
Ethernet0    800    801    802    803    804    805    806    807
Ethernet4    400    401    402    403    404    405    406    407
Ethernet8    100    101    102    103    104    105    106    107
"""

show_cleared_pg_dropped_packet_stat="""\
Ingress PG dropped packets:
     Port    PG0    PG1    PG2    PG3    PG4    PG5    PG6    PG7
---------  -----  -----  -----  -----  -----  -----  -----  -----
Ethernet0      0      0      0      0      0      0      0      0
Ethernet4      0      0      0      0      0      0      0      0
Ethernet8      0      0      0      0      0      0      0      0
"""

class TestPgDropstat(object):
    @classmethod
    def setup_class(cls):
        os.environ["PATH"] += os.pathsep + scripts_path
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        print("SETUP")

    def test_show_pg_drop_show(self):
        self.executor(clear_before_show = False)

    def test_show_pg_drop_clear(self):
        self.executor(clear_before_show = True)

    def executor(self, clear_before_show):
        runner = CliRunner()
        show_output = show_pg_dropped_packet_stat

        # Clear stats
        if clear_before_show:
            result = runner.invoke(clear.cli.commands["priority-group"].commands["drop"].commands["counters"], [])
            assert result.exit_code == 0
            show_output = show_cleared_pg_dropped_packet_stat

        result = runner.invoke(show.cli.commands["priority-group"].commands["drop"].commands["counters"], [])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0
        assert result.output == show_output

    def test_show_pg_drop_config_reload(self):
        runner = CliRunner()
        self.test_show_pg_drop_clear()

        # simulate 'config reload' to provoke counters recalculation (remove  backup from /tmp folder)
        result = runner.invoke(config.config.commands["reload"], [ "--no_service_restart",  "-y"])

        print(result.exit_code)
        print(result.output)

        assert result.exit_code == 0

        self.test_show_pg_drop_show()

    @classmethod
    def teardown_class(cls):
        os.environ["PATH"] = os.pathsep.join(os.environ["PATH"].split(os.pathsep)[:-1])
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        dropstat_dir_prefix = '/tmp/dropstat'
        dir_path = "{}-{}/".format(dropstat_dir_prefix, os.getuid())
        os.system("rm -rf {}".format(dir_path))
        print("TEARDOWN")
