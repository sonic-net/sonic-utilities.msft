ecn_show_config_output="""\
Profile: AZURE_LOSSLESS
-----------------------  -------
red_max_threshold        2097152
wred_green_enable        true
ecn                      ecn_all
green_min_threshold      1048576
red_min_threshold        1048576
wred_yellow_enable       true
yellow_min_threshold     1048576
green_max_threshold      2097152
green_drop_probability   5
yellow_max_threshold     2097152
wred_red_enable          true
yellow_drop_probability  5
red_drop_probability     5
-----------------------  -------

"""

testData = {
             'ecn_show_config' : {'cmd' : ['show'],
                                  'args' : [],
                                  'rc' : 0,
                                  'rc_output': ecn_show_config_output
                                 },
             'ecn_cfg_gmin' : {'cmd' : ['config'],
                               'args' : ['-profile', 'AZURE_LOSSLESS', '-gmin', '1048600'],
                               'rc' : 0,
                               'cmp_args' : ['AZURE_LOSSLESS,green_min_threshold,1048600']
                              },
             'ecn_cfg_gmax' : {'cmd' : ['config'],
                               'args' : ['-profile', 'AZURE_LOSSLESS', '-gmax', '2097153'],
                               'rc' : 0,
                               'cmp_args' : ['AZURE_LOSSLESS,green_max_threshold,2097153']
                              },
             'ecn_cfg_ymin' : {'cmd' : ['config'],
                               'args' : ['-profile', 'AZURE_LOSSLESS', '-ymin', '1048600'],
                               'rc' : 0,
                               'cmp_args' : ['AZURE_LOSSLESS,yellow_min_threshold,1048600']
                              },
             'ecn_cfg_ymax' : {'cmd' : ['config'],
                               'args' : ['-profile', 'AZURE_LOSSLESS', '-ymax', '2097153'],
                               'rc' : 0,
                               'cmp_args' : ['AZURE_LOSSLESS,yellow_max_threshold,2097153']
                              },
             'ecn_cfg_rmin' : {'cmd' : ['config'],
                               'args' : ['-profile', 'AZURE_LOSSLESS', '-rmin', '1048600'],
                               'rc' : 0,
                               'cmp_args' : ['AZURE_LOSSLESS,red_min_threshold,1048600']
                              },
             'ecn_cfg_rmax' : {'cmd' : ['config'],
                               'args' : ['-profile', 'AZURE_LOSSLESS', '-rmax', '2097153'],
                               'rc' : 0,
                               'cmp_args' : ['AZURE_LOSSLESS,red_max_threshold,2097153']
                              },
             'ecn_cfg_rdrop' : {'cmd' : ['config'],
                                'args' : ['-profile', 'AZURE_LOSSLESS', '-rdrop', '10'],
                                'rc' : 0,
                                'cmp_args' : ['AZURE_LOSSLESS,red_drop_probability,10']
                               },
             'ecn_cfg_ydrop' : {'cmd' : ['config'],
                                'args' : ['-profile', 'AZURE_LOSSLESS', '-ydrop', '11'],
                                'rc' : 0,
                                'cmp_args' : ['AZURE_LOSSLESS,yellow_drop_probability,11']
                               },
             'ecn_cfg_gdrop' : {'cmd' : ['config'],
                                'args' : ['-profile', 'AZURE_LOSSLESS', '-gdrop', '12'],
                                'rc' : 0,
                                'cmp_args' : ['AZURE_LOSSLESS,green_drop_probability,12']
                               },
             'ecn_cfg_multi_set' : {'cmd' : ['config'],
                                    'args' : ['-profile', 'AZURE_LOSSLESS', '-gdrop', '12', '-gmax', '2097153'],
                                    'rc' : 0,
                                    'cmp_args' : ['AZURE_LOSSLESS,green_drop_probability,12',
                                                  'AZURE_LOSSLESS,green_max_threshold,2097153'
                                                 ]
                                   },
             'ecn_cfg_gmin_gmax_invalid' : {'cmd' : ['config'],
                                            'args' : ['-profile', 'AZURE_LOSSLESS', '-gmax', '2097153', '-gmin', '2097154'],
                                            'rc' : 1,
                                            'rc_msg' : 'Invalid gmin (2097154) and gmax (2097153). gmin should be smaller than gmax'
                                           },
             'ecn_cfg_ymin_ymax_invalid' : {'cmd' : ['config'],
                                            'args' : ['-profile', 'AZURE_LOSSLESS', '-ymax', '2097153', '-ymin', '2097154'],
                                            'rc' : 1,
                                            'rc_msg' : 'Invalid ymin (2097154) and ymax (2097153). ymin should be smaller than ymax'
                                           },
             'ecn_cfg_rmin_rmax_invalid' : {'cmd' : ['config'],
                                            'args' : ['-profile', 'AZURE_LOSSLESS', '-rmax', '2097153', '-rmin', '2097154'],
                                            'rc' : 1,
                                            'rc_msg' : 'Invalid rmin (2097154) and rmax (2097153). rmin should be smaller than rmax'
                                           },
             'ecn_cfg_rmax_invalid' : {'cmd' : ['config'],
                                       'args' : ['-profile', 'AZURE_LOSSLESS', '-rmax', '-2097153'],
                                       'rc' : 1,
                                       'rc_msg' : 'Invalid rmax (-2097153). rmax should be an non-negative integer'
                                      },
             'ecn_cfg_rdrop_invalid' : {'cmd' : ['config'],
                                        'args' : ['-profile', 'AZURE_LOSSLESS', '-rdrop', '105'],
                                        'rc' : 1,
                                        'rc_msg' : 'Invalid value for "-rdrop": 105 is not in the valid range of 0 to 100'
                                      }

           }
