import os

import click
from sonic_py_common import device_info
from utilities_common.db import Db
import utilities_common.cli as clicommon

KUBE_ADMIN_CONF = "/etc/sonic/kube_admin.conf"
KUBECTL_CMD = "kubectl --kubeconfig /etc/sonic/kube_admin.conf {}"
REDIS_KUBE_TABLE = 'KUBERNETES_MASTER'
REDIS_KUBE_KEY = 'SERVER'


def _print_entry(d, prefix):
    if prefix:
        prefix += " "

    if isinstance(d, dict):
        for k in d:
            _print_entry(d[k], prefix + k)
    else:
        print(prefix + str(d))


def run_kube_command(cmd):
    if os.path.exists(KUBE_ADMIN_CONF):
        clicommon.run_command(KUBECTL_CMD.format(cmd))
    else:
        print("System not connected to cluster yet")


#
# kubernetes group ("show kubernetes ...")
#
@click.group()
def kubernetes():
    pass


@kubernetes.command()
def nodes():
    """List all nodes in this kubernetes cluster"""
    run_kube_command("get nodes")


@kubernetes.command()
def pods():
    """List all pods in this kubernetes cluster"""
    run_kube_command("get pods  --field-selector spec.nodeName={}".format(device_info.get_hostname()))


@kubernetes.command()
def status():
    """Descibe this node"""
    run_kube_command("describe node {}".format(device_info.get_hostname()))


@kubernetes.command()
def server():
    """Show kube configuration"""
    kube_fvs = Db().get_data(REDIS_KUBE_TABLE, REDIS_KUBE_KEY)
    if kube_fvs:
        _print_entry(kube_fvs, "{} {}".format(
            REDIS_KUBE_TABLE, REDIS_KUBE_KEY))
    else:
        print("Kubernetes server is not configured")

