import glob
from setuptools import setup
import unittest

def get_test_suite():
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('sonic-utilities-tests', pattern='*.py')
    return test_suite

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
    ],
    package_data={
        'show': ['aliases.ini']
    },
    scripts=[
        'scripts/aclshow',
        'scripts/boot_part',
        'scripts/coredump-compress',
        'scripts/decode-syseeprom',
        'scripts/dropcheck',
        'scripts/ecnconfig',
        'scripts/fast-reboot',
        'scripts/fast-reboot-dump.py',
        'scripts/fdbclear',
        'scripts/fdbshow',
        'scripts/generate_dump',
        'scripts/intfutil',
        'scripts/lldpshow',
        'scripts/pcmping',
        'scripts/port2alias',
        'scripts/portconfig',
        'scripts/portstat',
        'scripts/pfcstat',
        'scripts/queuestat',
        'scripts/reboot',
        'scripts/teamshow',
        'scripts/nbrshow'
    ],
    data_files=[
        ('/etc/bash_completion.d', glob.glob('data/etc/bash_completion.d/*')),
    ],
    entry_points={
        'console_scripts': [
            'acl-loader = acl_loader.main:cli',
            'config = config.main:cli',
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
    install_requires=[
        'click-default-group',
        'click',
        'natsort',
        'tabulate'
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
