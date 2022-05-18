from dump.match_infra import MatchEngine, MatchRequest, ConnectionPool
from dump.match_helper import get_matched_keys
from .db import Db

def get_port_acl_binding(db_wrap, port, ns):
    """
    Verify if the port is not bound to any ACL Table
    
    Args:
        db_wrap: utilities_common.Db() object
        port: Iface name
        ns: namespace

    Returns:
        list: ACL_TABLE names if found, 
                otherwise empty
    """ 
    ACL = "ACL_TABLE" # Table to look for port bindings
    if not isinstance(db_wrap, Db):
        raise Exception("db_wrap object is not of type utilities_common.Db")

    conn_pool = ConnectionPool()
    conn_pool.fill(ns, db_wrap.db_clients[ns], db_wrap.db_list)
    m_engine = MatchEngine(conn_pool)
    req = MatchRequest(db="CONFIG_DB",
                      table=ACL,
                      key_pattern="*",
                      field="ports@",
                      value=port,
                      ns=ns,
                      match_entire_list=False)
    ret = m_engine.fetch(req)
    acl_tables, _ = get_matched_keys(ret)
    return acl_tables


def get_port_pbh_binding(db_wrap, port, ns):
    """
    Verify if the port is not bound to any PBH Table
    
    Args:
        db_wrap: Db() object
        port: Iface name
        ns: namespace

    Returns:
        list: PBH_TABLE names if found, 
                otherwise empty
    """ 
    PBH = "PBH_TABLE" # Table to look for port bindings
    if not isinstance(db_wrap, Db):
        raise Exception("db_wrap object is not of type utilities_common.Db")

    conn_pool = ConnectionPool()
    conn_pool.fill(ns, db_wrap.db_clients[ns], db_wrap.db_list)
    m_engine = MatchEngine(conn_pool)
    req = MatchRequest(db="CONFIG_DB",
                      table=PBH,
                      key_pattern="*",
                      field="interface_list@",
                      value=port,
                      ns=ns,
                      match_entire_list=False)
    ret = m_engine.fetch(req)
    pbh_tables, _ = get_matched_keys(ret)
    return pbh_tables
