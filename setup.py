# https://github.com/ninjaaron/fast-entry_points
# workaround for slow 'pkg_resources' import
#
# NOTE: this only has effect on console_scripts and no speed-up for commands
# under scripts/. Consider stop using scripts and use console_scripts instead
#
# https://stackoverflow.com/questions/18787036/difference-between-entry-points-console-scripts-and-scripts-in-setup-py
try:
    import fastentrypoints
except ImportError:
    from setuptools.command import easy_install
    import pkg_resources
    easy_install.main(['fastentrypoints'])
    pkg_resources.require('fastentrypoints')
    import fastentrypoints

import glob
from setuptools import setup

setup(
    name='sonic-utilities',
    version='1.2',
    description='Command-line utilities for SONiC',
    license='Apache 2.0',
    author='SONiC Team',
    author_email='linuxnetdev@microsoft.com',
    url='https://github.com/Azure/sonic-utilities',
    maintainer='Joe LeVeque',
    maintainer_email='jolevequ@microsoft.com',
    packages=[
        'acl_loader',
        'clear',
        'config',
        'connect',
        'consutil',
        'counterpoll',
        'crm',
        'debug',
        'pfcwd',
        'sfputil',
        'pfc',
        'psuutil',
        'show',
        'sonic_installer',
        'sonic-utilities-tests',
        'undebug',
        'utilities_common',
    ],
    package_data={
        'show': ['aliases.ini'],
        'sonic-utilities-tests': ['acl_input/*', 'mock_tables/*.py', 'mock_tables/*.json']
    },
    scripts=[
        'scripts/aclshow',
        'scripts/boot_part',
        'scripts/coredump-compress',
        'scripts/db_migrator.py',
        'scripts/decode-syseeprom',
        'scripts/dropcheck',
        'scripts/ecnconfig',
        'scripts/fast-reboot',
        'scripts/fast-reboot-dump.py',
        'scripts/fdbclear',
        'scripts/fdbshow',
        'scripts/generate_dump',
        'scripts/intfutil',
        'scripts/intfstat',
        'scripts/lldpshow',
        'scripts/mmuconfig',
        'scripts/nbrshow',
        'scripts/neighbor_advertiser',
        'scripts/pcmping',
        'scripts/port2alias',
        'scripts/portconfig',
        'scripts/portstat',
        'scripts/pfcstat',
        'scripts/psushow',
        'scripts/queuestat',
        'scripts/reboot',
        'scripts/route_check.py',
        'scripts/route_check_test.sh',
        'scripts/sfpshow',
        'scripts/teamshow',
        'scripts/warm-reboot',
        'scripts/watermarkstat',
        'scripts/watermarkcfg'
    ],
    data_files=[
        ('/etc/bash_completion.d', glob.glob('data/etc/bash_completion.d/*')),
    ],
    entry_points={
        'console_scripts': [
            'acl-loader = acl_loader.main:cli',
            'config = config.main:config',
            'connect = connect.main:connect',
            'consutil = consutil.main:consutil',
            'counterpoll = counterpoll.main:cli',
            'crm = crm.main:cli',
            'debug = debug.main:cli',
            'pfcwd = pfcwd.main:cli',
            'sfputil = sfputil.main:cli',
            'pfc = pfc.main:cli',
            'psuutil = psuutil.main:cli',
            'show = show.main:cli',
            'sonic-clear = clear.main:cli',
            'sonic_installer = sonic_installer.main:cli',
            'undebug = undebug.main:cli',
        ]
    },
    # NOTE: sonic-utilities also depends on other packages that are either only
    # available as .whl files or the latest available Debian packages are
    # out-of-date and we must install newer versions via pip. These
    # dependencies cannot be listed here, as this package is built as a .deb,
    # therefore all dependencies will be assumed to also be available as .debs.
    # These unlistable dependencies are as follows:
    # - sonic-config-engine
    # - swsssdk
    # - tabulate
    install_requires=[
        'click-default-group',
        'click',
        'natsort'
    ],
    setup_requires= [
        'pytest-runner'
    ],
    tests_require = [
        'pytest',
        'mock>=2.0.0',
        'mockredispy>=2.9.3'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
    ],
    keywords='sonic SONiC utilities command line cli CLI',
    test_suite='setup.get_test_suite'
)
