# network statistics utility functions #

import json

STATUS_NA = 'N/A'
PORT_RATE = 40

def ns_diff(newstr, oldstr):
    """
        Calculate the diff.
    """
    if newstr == STATUS_NA or oldstr == STATUS_NA:
        return STATUS_NA
    else:
        new, old = int(newstr), int(oldstr)
        return '{:,}'.format(new - old)

def ns_brate(newstr, oldstr, delta):
    """
        Calculate the byte rate.
    """
    if newstr == STATUS_NA or oldstr == STATUS_NA:
        return STATUS_NA
    else:
        rate = int(ns_diff(newstr, oldstr).replace(',',''))/delta
        if rate > 1024*1024*10:
            rate = "{:.2f}".format(rate/1024/1024)+' MB'
        elif rate > 1024*10:
            rate = "{:.2f}".format(rate/1024)+' KB'
        else:
            rate = "{:.2f}".format(rate)+' B'
        return rate+'/s'

def ns_prate(newstr, oldstr, delta):
    """
        Calculate the packet rate.
    """
    if newstr == STATUS_NA or oldstr == STATUS_NA:
        return STATUS_NA
    else:
        rate = int(ns_diff(newstr, oldstr).replace(',',''))/delta
        return "{:.2f}".format(rate)+'/s'

def ns_util(newstr, oldstr, delta, port_rate=PORT_RATE):
    """
        Calculate the util.
    """
    if newstr == STATUS_NA or oldstr == STATUS_NA:
        return STATUS_NA
    else:
        rate = int(ns_diff(newstr, oldstr).replace(',',''))/delta
        util = rate/(port_rate*1024*1024*1024/8.0)*100
        return "{:.2f}%".format(util)

def table_as_json(table, header):
    """
        Print table as json format.
    """
    output = {}

    # Build a dictionary where the if_name is the key and the value is
    # a dictionary that holds MTU, TX_DRP, etc
    for line in table:
        if_name = line[0]
        output[if_name] = {header[i]: line[i] for i in range(1, len(header))}
    
    return json.dumps(output, indent=4, sort_keys=True)
