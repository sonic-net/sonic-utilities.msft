import click


FEATURE_TABLE = "FEATURE"
SYSLOG_CONFIG_TABLE = 'SYSLOG_CONFIG'
SYSLOG_CONFIG_GLOBAL_KEY = 'GLOBAL'
SYSLOG_CONFIG_FEATURE_TABLE = 'SYSLOG_CONFIG_FEATURE'

SYSLOG_RATE_LIMIT_INTERVAL = 'rate_limit_interval'
SYSLOG_RATE_LIMIT_BURST = 'rate_limit_burst'
SUPPORT_RATE_LIMIT = 'support_syslog_rate_limit'


def rate_limit_validator(interval, burst):
    """Validate input interval/burst

    Args:
        interval (int): Rate limit interval
        burst (int): Rate limit burst
    """
    if interval is None and burst is None:
        raise click.UsageError('Either interval or burst must be configured')


def service_validator(feature_data, service_name):
    """Validate input service name

    Args:
        feature_data (dict): feature entries of FEATURE table
        service_name (str): service name
    """
    if service_name not in feature_data:
        valid_service_names = ','.join(feature_data.keys())
        raise click.ClickException(f'Invalid service name {service_name}, please choose from: {valid_service_names}')

    service_data = feature_data[service_name]

    support_rate_limit = service_data.get(SUPPORT_RATE_LIMIT, '').lower() == 'true'
    if not support_rate_limit:
        raise click.ClickException(f'Service {service_name} does not support syslog rate limit configuration')


def save_rate_limit_to_db(db, service_name, interval, burst, log):
    """Save rate limit configuration to DB

    Args:
        db (object): db object
        service_name (str): service name. None means config for host.
        interval (int): rate limit interval
        burst (int): rate limit burst
        log (obj): log object
    """
    if service_name is None:
        service_name = 'host'
        table = SYSLOG_CONFIG_TABLE
        key = SYSLOG_CONFIG_GLOBAL_KEY
    else:
        table = SYSLOG_CONFIG_FEATURE_TABLE
        key = service_name

    if interval == 0 or burst == 0:
        msg = f'Disable syslog rate limit for {service_name}'
        click.echo(msg)
        log.log_notice(msg)
        interval = 0
        burst = 0

    data = {}
    if interval is not None:
        data[SYSLOG_RATE_LIMIT_INTERVAL] = interval
    if burst is not None:
        data[SYSLOG_RATE_LIMIT_BURST] = burst
    db.cfgdb.mod_entry(table, key, data)
    log.log_notice(f"Configured syslog {service_name} rate-limits: interval={data.get(SYSLOG_RATE_LIMIT_INTERVAL, 'N/A')},\
        burst={data.get(SYSLOG_RATE_LIMIT_BURST, 'N/A')}")

