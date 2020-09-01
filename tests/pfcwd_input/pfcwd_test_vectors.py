pfcwd_show_config_output="""\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME
---------  --------  ----------------  ------------------
Ethernet0      drop               600                 600
Ethernet4      drop               600                 600
Ethernet8      drop               600                 600
"""

pfcwd_show_config_single_port_output="""\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME
---------  --------  ----------------  ------------------
Ethernet0      drop               600                 600
"""

pfcwd_show_config_multi_port_output="""\
Changed polling interval to 600ms
     PORT    ACTION    DETECTION TIME    RESTORATION TIME
---------  --------  ----------------  ------------------
Ethernet0      drop               600                 600
Ethernet4      drop               600                 600
"""

pfcwd_show_config_invalid_port_output="""\
Changed polling interval to 600ms
  PORT    ACTION    DETECTION TIME    RESTORATION TIME
------  --------  ----------------  ------------------
"""

pfcwd_show_stats_output="""\
      QUEUE       STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-----------  -----------  -------------------------  ------------  ------------  -----------------  -----------------
Ethernet0:3      stormed                        1/0       100/300       100/300              0/200              0/200
Ethernet4:3  operational                        2/2       100/100       100/100                0/0                0/0
Ethernet8:4      stormed                        3/2       100/300       100/300              0/200              0/200
"""

pfcwd_show_stats_single_queue_output="""\
      QUEUE    STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-----------  --------  -------------------------  ------------  ------------  -----------------  -----------------
Ethernet0:3   stormed                        1/0       100/300       100/300              0/200              0/200
"""

pfcwd_show_stats_multi_queue_output="""\
      QUEUE       STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-----------  -----------  -------------------------  ------------  ------------  -----------------  -----------------
Ethernet0:3      stormed                        1/0       100/300       100/300              0/200              0/200
Ethernet4:3  operational                        2/2       100/100       100/100                0/0                0/0
"""

pfcwd_show_stats_invalid_queue_output="""\
  QUEUE    STATUS    STORM DETECTED/RESTORED    TX OK/DROP    RX OK/DROP    TX LAST OK/DROP    RX LAST OK/DROP
-------  --------  -------------------------  ------------  ------------  -----------------  -----------------
"""

testData = {
             'pfcwd_show_config' :  [ {'cmd' : ['show', 'config'],
                                       'args': [],
                                       'rc': 0,
                                       'rc_output': pfcwd_show_config_output
                                      }
                                    ],
             'pfcwd_show_config_single_port' :  [ {'cmd' : ['show', 'config'],
                                       'args': ['Ethernet0'],
                                       'rc': 0,
                                       'rc_output': pfcwd_show_config_single_port_output
                                      }
                                    ],
             'pfcwd_show_config_multi_port' :  [ {'cmd' : ['show', 'config'],
                                       'args': ['Ethernet0', 'Ethernet4'],
                                       'rc': 0,
                                       'rc_output': pfcwd_show_config_multi_port_output
                                      }
                                    ],
             'pfcwd_show_config_invalid_port' :  [ {'cmd' : ['show', 'config'],
                                       'args': ['Ethernet400'],
                                       'rc': 0,
                                       'rc_output': pfcwd_show_config_invalid_port_output
                                      }
                                    ],
             'pfcwd_show_stats' :  [ {'cmd' : ['show', 'stats'],
                                      'args': [],
                                      'rc': 0,
                                      'rc_output': pfcwd_show_stats_output
                                      }
                                    ],
             'pfcwd_show_stats_single_queue' :  [ {'cmd' : ['show', 'stats'],
                                                   'args': ['Ethernet0:3'],
                                                   'rc': 0,
                                                   'rc_output': pfcwd_show_stats_single_queue_output
                                                  }
                                                ],
             'pfcwd_show_stats_multi_queue' :  [ {'cmd' : ['show', 'stats'],
                                                  'args': ['Ethernet0:3', 'Ethernet4:3'],
                                                  'rc': 0,
                                                  'rc_output': pfcwd_show_stats_multi_queue_output
                                                 }
                                               ],
             'pfcwd_show_stats_invalid_queue' :  [ {'cmd' : ['show', 'stats'],
                                                    'args': ['Ethernet0:100'],
                                                    'rc': 0,
                                                    'rc_output': pfcwd_show_stats_invalid_queue_output
                                                   }
                                                 ]
           }
