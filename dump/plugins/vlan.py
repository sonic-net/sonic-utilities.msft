from .executor import Executor
from dump.match_infra import MatchRequest
from dump.helper import create_template_dict

class Vlan(Executor):
    
    ARG_NAME = "vlan_name"
    
    def __init__(self, match_engine=None):
        super().__init__(match_engine)
        self.ret_temp = {}
        self.ns = ''
          
    def get_all_args(self, ns=""):
        req = MatchRequest(db="CONFIG_DB", table="VLAN", key_pattern="*", ns=ns)
        ret = self.match_engine.fetch(req)
        all_vlans = ret["keys"]
        return [key.split("|")[-1] for key in all_vlans]
            
    def execute(self, params_dict):
        self.ret_temp = create_template_dict(dbs=["CONFIG_DB", "APPL_DB", "ASIC_DB", "STATE_DB"])
        vlan_name = params_dict[Vlan.ARG_NAME]
        self.ns = params_dict["namespace"]
        self.init_vlan_config_info(vlan_name)
        self.init_vlan_appl_info(vlan_name)
        self.init_state_vlan_info(vlan_name)
        self.init_asic_vlan_info(vlan_name)
        return self.ret_temp
    
    def init_vlan_config_info(self, vlan_name):
        req = MatchRequest(db="CONFIG_DB", table="VLAN", key_pattern=vlan_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) != 0:
            self.ret_temp[req.db]["keys"] = ret["keys"]
        else:
            self.ret_temp[req.db]["tables_not_found"] = [req.table]
    
    def init_vlan_appl_info(self, vlan_name):
        req = MatchRequest(db="APPL_DB", table="VLAN_TABLE", key_pattern=vlan_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) != 0:
            self.ret_temp[req.db]["keys"] = ret["keys"]
        else:
            self.ret_temp[req.db]["tables_not_found"] = [req.table]
        
    def init_state_vlan_info(self, vlan_name):
        req = MatchRequest(db="STATE_DB", table="VLAN_TABLE", key_pattern=vlan_name, ns=self.ns)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) != 0:
            self.ret_temp[req.db]["keys"] = ret["keys"]
        else:
            self.ret_temp[req.db]["tables_not_found"] = [req.table]
    
    def init_asic_vlan_info(self, vlan_name):
        # Convert 'Vlanxxx' to 'xxx'
        if vlan_name[0:4] != "Vlan" or not vlan_name[4:].isnumeric():
            self.ret_temp["ASIC_DB"]["tables_not_found"] =["ASIC_STATE:SAI_OBJECT_TYPE_VLAN"]
            return {}, {}
        vlan_num = int(vlan_name[4:])
        
        # Find the table named "ASIC_STATE:SAI_OBJECT_TYPE_VLAN:*" in which SAI_VLAN_ATTR_VLAN_ID = vlan_num
        req = MatchRequest(db="ASIC_DB", table="ASIC_STATE:SAI_OBJECT_TYPE_VLAN", key_pattern="*", field="SAI_VLAN_ATTR_VLAN_ID", 
                           value=str(vlan_num), ns=self.ns)
        ret = self.match_engine.fetch(req)
        if not ret["error"] and len(ret["keys"]) != 0:
            self.ret_temp[req.db]["keys"] = ret["keys"]
        else:
            self.ret_temp[req.db]["tables_not_found"] = [req.table]
    
