from setuptools import setup

setup(
    name='sonic-utilities',
    version='1.0',
    description='Command-line utilities for SONiC',
    license='Apache 2.0',
    author='SONiC Team',
    author_email='linuxnetdev@microsoft.com',
    url='https://github.com/Azure/sonic-utilities',
    maintainer='Joe LeVeque',
    maintainer_email='jolevequ@microsoft.com',
    packages=['sonic_cli', 'sonic_eeprom', 'sonic_sfp'],
    package_data={
        'sonic_cli': ['aliases.ini']
    },
    scripts=[
        'scripts/boot_part',
        'scripts/coredump-compress',
        'scripts/decode-syseeprom',
        'scripts/generate_dump',
        'scripts/portstat',
        'scripts/sfputil',
    ],
    data_files=[
        ('/etc/bash_completion.d', ['data/etc/bash_completion.d/show'])
    ],
    entry_points={
        'console_scripts': [
            'show = sonic_cli.main:cli',
        ]
    },
    install_requires=[
        'click',
        'click-default-group',
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
)
