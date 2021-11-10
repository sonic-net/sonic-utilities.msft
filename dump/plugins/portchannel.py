from dump.match_infra import MatchRequest
from dump.helper import create_template_dict
from .executor import Executor


class Portchannel(Executor):
    """
    Debug Dump Plugin for PortChannel/LAG Module
    """
    ARG_NAME = "portchannel_name"

    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.ret_temp = {}
        self.ns = ''
        self.lag_members = set()

    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="PORTCHANNEL", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        all_lags = ret["keys"]
        return [key.split("|")[-1] for key in all_lags]

    def execute(self, params_dict):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        self.lag_name = params_dict[Portchannel.ARG_NAME]
        self.ns = params_dict["namespace"]
        # CONFIG_DB
        lag_found = self.init_lag_config_info()
        if lag_found:
            self.init_lag_member_config_info()
        # APPL_DB
        self.init_lag_appl_info()
        # STATE_DB
        self.init_lag_state_info()
        # ASIC_DB
        lag_type_objs_asic = self.init_lag_member_type_obj_asic_info()
        self.init_lag_asic_info(lag_type_objs_asic)
        return self.ret_temp

    def add_to_ret_template(self, table, db, keys, err):
        if not err and keys:
            self.ret_temp[db]["keys"].extend(keys)
            return True
        else:
            self.ret_temp[db]["tables_not_found"].extend([table])
            return False

    def init_lag_config_info(self):
        req = MatchRequest(db="CONFIG_DB", table="PORTCHANNEL", key_pattern=self.lag_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        return self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_lag_member_config_info(self):
        req = MatchRequest(db="CONFIG_DB", table="PORTCHANNEL_MEMBER", key_pattern=self.lag_name + "|*", ns=self.ns)
        ret = self.match_engine.fetch(req)
        for key in ret["keys"]:
            self.lag_members.add(key.split("|")[-1])

    def init_lag_appl_info(self):
        req = MatchRequest(db="APPL_DB", table="LAG_TABLE", key_pattern=self.lag_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        return self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_lag_state_info(self):
        req = MatchRequest(db="STATE_DB", table="LAG_TABLE", key_pattern=self.lag_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        return self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_lag_asic_info(self, lag_type_objs_asic):
        if len(lag_type_objs_asic) == 0:
            self.ret_temp["ASIC_DB"]["tables_not_found"].extend(["ASIC_STATE:SAI_OBJECT_TYPE_LAG"])
            return
        for lag_asic_obj in lag_type_objs_asic:
            req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_LAG", key_pattern=lag_asic_obj, ns=self.ns)
            ret = self.match_engine.fetch(req)
            self.add_to_ret_template(req.table, req.db, ret["keys"], ret["error"])

    def init_lag_member_type_obj_asic_info(self):
        """
        Finding the relevant SAI_OBJECT_TYPE_LAG key directly from the ASIC is not possible given a LAG name
        Thus, using the members to find SAI_LAG_MEMBER_ATTR_LAG_ID
        """
        lag_type_objs_asic = set()
        for port_name in self.lag_members:
            port_asic_obj = self.get_port_asic_obj(port_name)
            if port_asic_obj:
                lag_member_key, lag_oid = self.get_lag_and_member_obj(port_asic_obj)
                lag_type_objs_asic.add(lag_oid)
        return lag_type_objs_asic

    def get_port_asic_obj(self, port_name):
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_HOSTIF", key_pattern="*", field="SAI_HOSTIF_ATTR_NAME",
                           value=port_name, return_fields=["SAI_HOSTIF_ATTR_OBJ_ID"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        asic_port_obj_id = ""
        if not ret["error"] and ret["keys"]:
            sai_hostif_obj_key = ret["keys"][-1]
            if sai_hostif_obj_key in ret["return_values"] and "SAI_HOSTIF_ATTR_OBJ_ID" in ret["return_values"][sai_hostif_obj_key]:
                asic_port_obj_id = ret["return_values"][sai_hostif_obj_key]["SAI_HOSTIF_ATTR_OBJ_ID"]
        return asic_port_obj_id

    def get_lag_and_member_obj(self, port_asic_obj):
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER", key_pattern="*", field="SAI_LAG_MEMBER_ATTR_PORT_ID",
                           value=port_asic_obj, return_fields=["SAI_LAG_MEMBER_ATTR_LAG_ID"], ns=self.ns)
        ret = self.match_engine.fetch(req)
        lag_member_key = ""
        lag_oid = ""
        if not ret["error"] and ret["keys"]:
            lag_member_key = ret["keys"][-1]
            if lag_member_key in ret["return_values"] and "SAI_LAG_MEMBER_ATTR_LAG_ID" in ret["return_values"][lag_member_key]:
                lag_oid = ret["return_values"][lag_member_key]["SAI_LAG_MEMBER_ATTR_LAG_ID"]
        return lag_member_key, lag_oid
