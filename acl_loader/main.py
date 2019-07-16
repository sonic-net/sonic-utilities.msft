#!/usr/bin/env python

import click
import ipaddr
import json
import syslog
import tabulate
from natsort import natsorted

import openconfig_acl
import pyangbind.lib.pybindJSON as pybindJSON
from swsssdk import ConfigDBConnector
from swsssdk import SonicV2Connector


def info(msg):
    click.echo(click.style("Info: ", fg='cyan') + click.style(str(msg), fg='green'))
    syslog.syslog(syslog.LOG_INFO, msg)


def warning(msg):
    click.echo(click.style("Warning: ", fg='cyan') + click.style(str(msg), fg='yellow'))
    syslog.syslog(syslog.LOG_WARNING, msg)


def error(msg):
    click.echo(click.style("Error: ", fg='cyan') + click.style(str(msg), fg='red'))
    syslog.syslog(syslog.LOG_ERR, msg)


def deep_update(dst, src):
    for key, value in src.iteritems():
        if isinstance(value, dict):
            node = dst.setdefault(key, {})
            deep_update(node, value)
        else:
            dst[key] = value
    return dst


class AclLoaderException(Exception):
    pass


class AclLoader(object):

    ACL_TABLE = "ACL_TABLE"
    ACL_RULE = "ACL_RULE"
    ACL_TABLE_TYPE_MIRROR = "MIRROR"
    ACL_TABLE_TYPE_CTRLPLANE = "CTRLPLANE"
    CFG_MIRROR_SESSION_TABLE = "MIRROR_SESSION"
    STATE_MIRROR_SESSION_TABLE = "MIRROR_SESSION_TABLE"
    POLICER = "POLICER"
    SESSION_PREFIX = "everflow"

    min_priority = 1
    max_priority = 10000

    ethertype_map = {
        "ETHERTYPE_LLDP": 0x88CC,
        "ETHERTYPE_VLAN": 0x8100,
        "ETHERTYPE_ROCE": 0x8915,
        "ETHERTYPE_ARP": 0x0806,
        "ETHERTYPE_IPV4": 0x0800,
        "ETHERTYPE_IPV6": 0x86DD,
        "ETHERTYPE_MPLS": 0x8847
    }

    ip_protocol_map = {
        "IP_TCP": 6,
        "IP_ICMP": 1,
        "IP_UDP": 17,
        "IP_IGMP": 2,
        "IP_PIM": 103,
        "IP_RSVP": 46,
        "IP_GRE": 47,
        "IP_AUTH": 51,
        "IP_L2TP": 115
    }

    def __init__(self):
        self.yang_acl = None
        self.requested_session = None
        self.current_table = None
        self.tables_db_info = {}
        self.rules_db_info = {}
        self.rules_info = {}
        self.sessions_db_info = {}
        self.configdb = ConfigDBConnector()
        self.configdb.connect()
        self.statedb = SonicV2Connector(host="127.0.0.1")
        self.statedb.connect(self.statedb.STATE_DB)

        self.read_tables_info()
        self.read_rules_info()
        self.read_sessions_info()
        self.read_policers_info()

    def read_tables_info(self):
        """
        Read ACL_TABLE table from configuration database
        :return:
        """
        self.tables_db_info = self.configdb.get_table(self.ACL_TABLE)

    def get_tables_db_info(self):
        return self.tables_db_info

    def read_rules_info(self):
        """
        Read ACL_RULE table from configuration database
        :return:
        """
        self.rules_db_info = self.configdb.get_table(self.ACL_RULE)

    def get_rules_db_info(self):
        return self.rules_db_info

    def read_policers_info(self):
        """
        Read POLICER table from configuration database
        :return:
        """
        self.policers_db_info = self.configdb.get_table(self.POLICER)

    def get_policers_db_info(self):
        return self.policers_db_info

    def read_sessions_info(self):
        """
        Read MIRROR_SESSION table from configuration database
        :return:
        """
        self.sessions_db_info = self.configdb.get_table(self.CFG_MIRROR_SESSION_TABLE)
        for key in self.sessions_db_info.keys():
            state_db_info = self.statedb.get_all(self.statedb.STATE_DB, "{}|{}".format(self.STATE_MIRROR_SESSION_TABLE, key))
            if state_db_info:
                status = state_db_info.get("status", "inactive")
            else:
                status = "error"
            self.sessions_db_info[key]["status"] = status

    def get_sessions_db_info(self):
        return self.sessions_db_info

    def get_session_name(self):
        """
        Get requested mirror session name or default session
        :return: Mirror session name
        """
        if self.requested_session:
            return self.requested_session

        for key in self.get_sessions_db_info():
            if key.startswith(self.SESSION_PREFIX):
                return key

        return None

    def set_table_name(self, table_name):
        """
        Set table name to restrict the table to be modified
        :param table_name: Table name
        :return:
        """
        self.current_table = table_name

    def set_session_name(self, session_name):
        """
        Set session name to be used in ACL rule action
        :param session_name: Mirror session name
        :return:
        """
        if session_name not in self.get_sessions_db_info():
            raise AclLoaderException("Session %s does not exist" % session_name)

        self.requested_session = session_name

    def set_max_priority(self, priority):
        """
        Set rules max priority
        :param priority: Rules max priority
        :return:
        """
        self.max_priority = int(priority)

    def is_table_valid(self, tname):
        return self.tables_db_info.get(tname)

    def is_table_mirror(self, tname):
        """
        Check if ACL table type is ACL_TABLE_TYPE_MIRROR or ACL_TABLE_TYPE_MIRRORV6
        :param tname: ACL table name
        :return: True if table type is MIRROR or MIRRORV6 else False
        """
        return self.tables_db_info[tname]['type'].upper().startswith(self.ACL_TABLE_TYPE_MIRROR)

    def is_table_control_plane(self, tname):
        """
        Check if ACL table type is ACL_TABLE_TYPE_CTRLPLANE
        :param tname: ACL table name
        :return: True if table type is ACL_TABLE_TYPE_CTRLPLANE else False
        """
        return self.tables_db_info[tname]['type'].upper() == self.ACL_TABLE_TYPE_CTRLPLANE

    @staticmethod
    def parse_acl_json(filename):
        yang_acl = pybindJSON.load(filename, openconfig_acl, "openconfig_acl")
        # Check pybindJSON parsing
        # pybindJSON.load will silently return an empty json object if input invalid
        with open(filename, 'r') as f:
            plain_json = json.load(f)
            if len(plain_json['acl']['acl-sets']['acl-set']) != len(yang_acl.acl.acl_sets.acl_set):
                raise AclLoaderException("Invalid input file %s" % filename)
        return yang_acl

    def load_rules_from_file(self, filename):
        """
        Load file with ACL rules configuration in openconfig ACL format. Convert rules
        to Config DB schema.
        :param filename: File in openconfig ACL format
        :return:
        """
        self.yang_acl = AclLoader.parse_acl_json(filename)
        self.convert_rules()

    def convert_action(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.actions.config.forwarding_action == "ACCEPT":
            if self.is_table_control_plane(table_name):
                rule_props["PACKET_ACTION"] = "ACCEPT"
            elif self.is_table_mirror(table_name):
                session_name = self.get_session_name()
                if not session_name:
                    raise AclLoaderException("Mirroring session does not exist")

                rule_props["MIRROR_ACTION"] = session_name
            else:
                rule_props["PACKET_ACTION"] = "FORWARD"
        elif rule.actions.config.forwarding_action == "DROP":
            rule_props["PACKET_ACTION"] = "DROP"
        elif rule.actions.config.forwarding_action == "REJECT":
            rule_props["PACKET_ACTION"] = "DROP"
        else:
            raise AclLoaderException("Unknown rule action %s in table %s, rule %d" % (
                rule.actions.config.forwarding_action, table_name, rule_idx))

        return rule_props

    def convert_l2(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.l2.config.ethertype:
            if rule.l2.config.ethertype in self.ethertype_map:
                rule_props["ETHER_TYPE"] = self.ethertype_map[rule.l2.config.ethertype]
            else:
                try:
                    rule_props["ETHER_TYPE"] = int(rule.l2.config.ethertype)
                except:
                    raise AclLoaderException("Failed to convert ethertype %s table %s rule %s" % (
                        rule.l2.config.ethertype, table_name, rule_idx))

        return rule_props

    def convert_ip(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.ip.config.protocol:
            if self.ip_protocol_map.has_key(rule.ip.config.protocol):
                rule_props["IP_PROTOCOL"] = self.ip_protocol_map[rule.ip.config.protocol]
            else:
                try:
                    int(rule.ip.config.protocol)
                except:
                    raise AclLoaderException("Unknown rule protocol %s in table %s, rule %d!" % (
                        rule.ip.config.protocol, table_name, rule_idx))

                rule_props["IP_PROTOCOL"] = rule.ip.config.protocol

        if rule.ip.config.source_ip_address:
            source_ip_address = rule.ip.config.source_ip_address.encode("ascii")
            if ipaddr.IPNetwork(source_ip_address).version == 4:
                rule_props["SRC_IP"] = source_ip_address
            else:
                rule_props["SRC_IPV6"] = source_ip_address

        if rule.ip.config.destination_ip_address:
            destination_ip_address = rule.ip.config.destination_ip_address.encode("ascii")
            if ipaddr.IPNetwork(destination_ip_address).version == 4:
                rule_props["DST_IP"] = destination_ip_address
            else:
                rule_props["DST_IPV6"] = destination_ip_address

        # NOTE: DSCP is available only for MIRROR table
        if self.is_table_mirror(table_name):
            if rule.ip.config.dscp:
                rule_props["DSCP"] = rule.ip.config.dscp

        return rule_props

    def convert_port(self, port):
        """
        Convert port field format from openconfig ACL to Config DB schema
        :param port: String, ACL port number or range in openconfig format
        :return: Tuple, first value is converted port string,
            second value is boolean, True if value is a port range, False
            if it is a single port value
        """
        # OpenConfig port range is of the format "####..####", whereas
        # Config DB format is "####-####"
        if ".." in port:
            return  port.replace("..", "-"), True
        else:
            return port, False

    def convert_transport(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.transport.config.source_port:
            port, is_range = self.convert_port(str(rule.transport.config.source_port))
            rule_props["L4_SRC_PORT_RANGE" if is_range else "L4_SRC_PORT"] = port
        if rule.transport.config.destination_port:
            port, is_range = self.convert_port(str(rule.transport.config.destination_port))
            rule_props["L4_DST_PORT_RANGE" if is_range else "L4_DST_PORT"] = port

        tcp_flags = 0x00

        for flag in rule.transport.config.tcp_flags:
            if flag == "TCP_FIN":
                tcp_flags |= 0x01
            if flag == "TCP_SYN":
                tcp_flags |= 0x02
            if flag == "TCP_RST":
                tcp_flags |= 0x04
            if flag == "TCP_PSH":
                tcp_flags |= 0x08
            if flag == "TCP_ACK":
                tcp_flags |= 0x10
            if flag == "TCP_URG":
                tcp_flags |= 0x20
            if flag == "TCP_ECE":
                tcp_flags |= 0x40
            if flag == "TCP_CWR":
                tcp_flags |= 0x80

        if tcp_flags:
            rule_props["TCP_FLAGS"] = '0x{:02x}/0x{:02x}'.format(tcp_flags, tcp_flags)

        return rule_props

    def convert_input_interface(self, table_name, rule_idx, rule):
        rule_props = {}

        if rule.input_interface.interface_ref.config.interface:
            rule_props["IN_PORTS"] = rule.input_interface.interface_ref.config.interface

        return rule_props

    def convert_rule_to_db_schema(self, table_name, rule):
        """
        Convert rules format from openconfig ACL to Config DB schema
        :param table_name: ACL table name to which rule belong
        :param rule: ACL rule in openconfig format
        :return: dict with Config DB schema
        """
        rule_idx = int(rule.config.sequence_id)
        rule_props = {}
        rule_data = {(table_name, "RULE_" + str(rule_idx)): rule_props}

        rule_props["PRIORITY"] = str(self.max_priority - rule_idx)

        deep_update(rule_props, self.convert_action(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_l2(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_ip(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_transport(table_name, rule_idx, rule))
        deep_update(rule_props, self.convert_input_interface(table_name, rule_idx, rule))

        return rule_data

    def deny_rule(self, table_name):
        """
        Create default deny rule in Config DB format
        :param table_name: ACL table name to which rule belong
        :return: dict with Config DB schema
        """
        rule_props = {}
        rule_data = {(table_name, "DEFAULT_RULE"): rule_props}
        rule_props["PRIORITY"] = str(self.min_priority)
        rule_props["ETHER_TYPE"] = str(self.ethertype_map["ETHERTYPE_IPV4"])
        rule_props["PACKET_ACTION"] = "DROP"
        return rule_data

    def convert_rules(self):
        """
        Convert rules in openconfig ACL format to Config DB schema
        :return:
        """
        for acl_set_name in self.yang_acl.acl.acl_sets.acl_set:
            table_name = acl_set_name.replace(" ", "_").replace("-", "_").upper().encode('ascii')
            acl_set = self.yang_acl.acl.acl_sets.acl_set[acl_set_name]

            if not self.is_table_valid(table_name):
                warning("%s table does not exist" % (table_name))
                continue

            if self.current_table is not None and self.current_table != table_name:
                continue

            for acl_entry_name in acl_set.acl_entries.acl_entry:
                acl_entry = acl_set.acl_entries.acl_entry[acl_entry_name]
                try:
                    rule = self.convert_rule_to_db_schema(table_name, acl_entry)
                    deep_update(self.rules_info, rule)
                except AclLoaderException as ex:
                    error("Error processing rule %s: %s. Skipped." % (acl_entry_name, ex))

            if not self.is_table_mirror(table_name):
                deep_update(self.rules_info, self.deny_rule(table_name))

    def full_update(self):
        """
        Perform full update of ACL rules configuration. All existing rules
        will be removed. New rules loaded from file will be installed. If
        the current_table is not empty, only rules within that table will
        be removed and new rules in that table will be installed.
        :return:
        """
        for key in self.rules_db_info.keys():
            if self.current_table is None or self.current_table == key[0]:
               self.configdb.mod_entry(self.ACL_RULE, key, None)

        self.configdb.mod_config({self.ACL_RULE: self.rules_info})

    def incremental_update(self):
        """
        Perform incremental ACL rules configuration update. Get existing rules from
        Config DB. Compare with rules specified in file and perform corresponding
        modifications.
        :return:
        """

        # TODO: Until we test ASIC behavior, we cannot assume that we can insert
        # dataplane ACLs and shift existing ACLs. Therefore, we perform a full
        # update on dataplane ACLs, and only perform an incremental update on
        # control plane ACLs.

        new_rules = set(self.rules_info.iterkeys())
        new_dataplane_rules = set()
        new_controlplane_rules = set()
        current_rules = set(self.rules_db_info.iterkeys())
        current_dataplane_rules = set()
        current_controlplane_rules = set()

        for key in new_rules:
            table_name = key[0]
            if self.tables_db_info[table_name]['type'].upper() == self.ACL_TABLE_TYPE_CTRLPLANE:
                new_controlplane_rules.add(key)
            else:
                new_dataplane_rules.add(key)

        for key in current_rules:
            table_name = key[0]
            if self.tables_db_info[table_name]['type'].upper() == self.ACL_TABLE_TYPE_CTRLPLANE:
                current_controlplane_rules.add(key)
            else:
                current_dataplane_rules.add(key)

        # Remove all existing dataplane rules
        for key in current_dataplane_rules:
            self.configdb.mod_entry(self.ACL_RULE, key, None)

        # Add all new dataplane rules
        for key in new_dataplane_rules:
            self.configdb.mod_entry(self.ACL_RULE, key, self.rules_info[key])

        added_controlplane_rules = new_controlplane_rules.difference(current_controlplane_rules)
        removed_controlplane_rules = current_controlplane_rules.difference(new_controlplane_rules)
        existing_controlplane_rules = new_rules.intersection(current_controlplane_rules)

        for key in added_controlplane_rules:
            self.configdb.mod_entry(self.ACL_RULE, key, self.rules_info[key])

        for key in removed_controlplane_rules:
            self.configdb.mod_entry(self.ACL_RULE, key, None)

        for key in existing_controlplane_rules:
            if cmp(self.rules_info[key], self.rules_db_info[key]) != 0:
                self.configdb.set_entry(self.ACL_RULE, key, self.rules_info[key])


    def delete(self, table=None, rule=None):
        """
        :param table:
        :param rule:
        :return:
        """
        for key in self.rules_db_info.iterkeys():
            if not table or table == key[0]:
                if not rule or rule == key[1]:
                    self.configdb.set_entry(self.ACL_RULE, key, None)


    def show_table(self, table_name):
        """
        Show ACL table configuration.
        :param table_name: Optional. ACL table name. Filter tables by specified name.
        :return:
        """
        header = ("Name", "Type", "Binding", "Description")

        data = []
        for key, val in self.get_tables_db_info().iteritems():
            if table_name and key != table_name:
                continue

            if val["type"] == AclLoader.ACL_TABLE_TYPE_CTRLPLANE:
                services = natsorted(val["services"])
                data.append([key, val["type"], services[0], val["policy_desc"]])

                if len(services) > 1:
                    for service in services[1:]:
                        data.append(["", "", service, ""])
            else:
                if not val["ports"]:
                    data.append([key, val["type"], "", val["policy_desc"]])
                else:
                    ports = natsorted(val["ports"])
                    data.append([key, val["type"], ports[0], val["policy_desc"]])

                    if len(ports) > 1:
                        for port in ports[1:]:
                            data.append(["", "", port, ""])

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))


    def show_session(self, session_name):
        """
        Show mirror session configuration.
        :param session_name: Optional. Mirror session name. Filter sessions by specified name.
        :return:
        """
        header = ("Name", "Status", "SRC IP", "DST IP", "GRE", "DSCP", "TTL", "Queue", "Policer")

        data = []
        for key, val in self.get_sessions_db_info().iteritems():
            if session_name and key != session_name:
                continue

            data.append([key, val["status"], val["src_ip"], val["dst_ip"],
                         val.get("gre_type", ""), val.get("dscp", ""),
                         val.get("ttl", ""), val.get("queue", ""), val.get("policer", "")])

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))


    def show_policer(self, policer_name):
        """
        Show policer configuration.
        :param policer_name: Optional. Policer name. Filter policers by specified name.
        :return:
        """
        header = ("Name", "Type", "Mode", "CIR", "CBS")

        data = []
        for key, val in self.get_policers_db_info().iteritems():
            if policer_name and key != policer_name:
                continue

            data.append([key, val["meter_type"], val["mode"], val.get("cir", ""), val.get("cbs", "")])

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))


    def show_rule(self, table_name, rule_id):
        """
        Show ACL rules configuration.
        :param table_name: Optional. ACL table name. Filter rules by specified table name.
        :param rule_id: Optional. ACL rule name. Filter rule by specified rule name.
        :return:
        """
        header = ("Table", "Rule", "Priority", "Action", "Match")

        ignore_list = ["PRIORITY", "PACKET_ACTION", "MIRROR_ACTION"]

        raw_data = []
        for (tname, rid), val in self.get_rules_db_info().iteritems():

            if table_name and table_name != tname:
                continue

            if rule_id and rule_id != rid:
                continue

            priority = val["PRIORITY"]

            action = ""
            if "PACKET_ACTION" in val:
                action = val["PACKET_ACTION"]
            elif "MIRROR_ACTION" in val:
                action = "MIRROR: %s" % val["MIRROR_ACTION"]
            else:
                continue

            matches = ["%s: %s" % (k, v) for k, v in val.iteritems() if k not in ignore_list]

            matches.sort()

            if len(matches) == 0:
                matches.append("N/A")

            rule_data = [[tname, rid, priority, action, matches[0]]]
            if len(matches) > 1:
                for m in matches[1:]:
                    rule_data.append(["", "", "", "", m])

            raw_data.append([priority, rule_data])

        def cmp_rules(a, b):
            return cmp(a[0], b[0])

        raw_data.sort(cmp_rules)
        raw_data.reverse()

        data = []
        for _, d in raw_data:
            data += d

        print(tabulate.tabulate(data, headers=header, tablefmt="simple", missingval=""))


@click.group()
@click.pass_context
def cli(ctx):
    """
    Utility entry point.
    """
    context = {
        "acl_loader": AclLoader()
    }

    ctx.obj = context


@cli.group()
@click.pass_context
def show(ctx):
    """
    Show ACL configuration.
    """
    pass


@show.command()
@click.argument('table_name', type=click.STRING, required=False)
@click.pass_context
def table(ctx, table_name):
    """
    Show ACL tables configuration.
    :return:
    """
    acl_loader = ctx.obj["acl_loader"]
    acl_loader.show_table(table_name)


@show.command()
@click.argument('session_name', type=click.STRING, required=False)
@click.pass_context
def session(ctx, session_name):
    """
    Show mirror session configuration.
    :return:
    """
    acl_loader = ctx.obj["acl_loader"]
    acl_loader.show_session(session_name)


@show.command()
@click.argument('policer_name', type=click.STRING, required=False)
@click.pass_context
def policer(ctx, policer_name):
    """
    Show policer configuration.
    :return:
    """
    acl_loader = ctx.obj["acl_loader"]
    acl_loader.show_policer(policer_name)


@show.command()
@click.argument('table_name', type=click.STRING, required=False)
@click.argument('rule_id', type=click.STRING, required=False)
@click.pass_context
def rule(ctx, table_name, rule_id):
    """
    Show ACL rule configuration.
    :return:
    """
    acl_loader = ctx.obj["acl_loader"]
    acl_loader.show_rule(table_name, rule_id)


@cli.group()
@click.pass_context
def update(ctx):
    """
    Update ACL rules configuration.
    """
    pass


@update.command()
@click.argument('filename', type=click.Path(exists=True))
@click.option('--table_name', type=click.STRING, required=False)
@click.option('--session_name', type=click.STRING, required=False)
@click.option('--max_priority', type=click.INT, required=False)
@click.pass_context
def full(ctx, filename, table_name, session_name, max_priority):
    """
    Full update of ACL rules configuration.
    If a table_name is provided, the operation will be restricted in the specified table.
    """
    acl_loader = ctx.obj["acl_loader"]

    if table_name:
        acl_loader.set_table_name(table_name)

    if session_name:
        acl_loader.set_session_name(session_name)

    if max_priority:
        acl_loader.set_max_priority(max_priority)

    acl_loader.load_rules_from_file(filename)
    acl_loader.full_update()


@update.command()
@click.argument('filename', type=click.Path(exists=True))
@click.option('--session_name', type=click.STRING, required=False)
@click.option('--max_priority', type=click.INT, required=False)
@click.pass_context
def incremental(ctx, filename, session_name, max_priority):
    """
    Incremental update of ACL rule configuration.
    """
    acl_loader = ctx.obj["acl_loader"]

    if session_name:
        acl_loader.set_session_name(session_name)

    if max_priority:
        acl_loader.set_max_priority(max_priority)

    acl_loader.load_rules_from_file(filename)
    acl_loader.incremental_update()


@cli.command()
@click.argument('table', required=False)
@click.argument('rule', required=False)
@click.pass_context
def delete(ctx, table, rule):
    """
    Delete ACL rules.
    """
    acl_loader = ctx.obj["acl_loader"]

    acl_loader.delete(table, rule)


if __name__ == "__main__":
    try:
        cli()
    except AclLoaderException as e:
        error(e)
    except Exception as e:
        error("Unknown error: %s" % repr(e))
