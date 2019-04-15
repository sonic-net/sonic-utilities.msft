def get_uptime():
    with open('/proc/uptime') as fp:
        return float(fp.read().split(' ')[0])