from swsssdk import ConfigDBConnector

class Db(object):
    def __init__(self):
        self.cfgdb = ConfigDBConnector()
        self.cfgdb.connect()
