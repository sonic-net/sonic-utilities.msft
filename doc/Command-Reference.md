# SONiC COMMAND LINE INTERFACE GUIDE

Table of Contents
=================

   * [Document History](#document-history)
   * [Introduction](#introduction)
   * [Basic Configuration And Show](#basic-configuration-and-show)
      * [SSH Login](#ssh-login)
      * [Configuring Management Interface](#configuring-management-interface)
      * [Config Help](#config-help)
	  * [Show Help](#show-help)
      * [Show Versions](#show-versions)
      * [Show System Status](#show-system-status)
      * [Show Hardware Platform](#show-hardware-platform)
         * [Transceivers](#transceivers)
   * [AAA &amp; TACACS  Configuration And Show](#aaa--tacacs-configuration-and-show)
      * [AAA Configuration And Show](#aaa-configuration-and-show)
         * [AAA show commands](#aaa-show-commands)
         * [AAA config commands](#aaa-config-commands)
      * [TACACS  Configuration And Show](#tacacs-configuration-and-show)
         * [TACACS  show commands](#tacacs-show-commands)
         * [TACACS  Config commands](#tacacs-config-commands)
   * [ACL Configuration And Show](#acl-configuration-and-show)
      * [ACL show commands](#acl-show-commands)
      * [ACL config commands](#acl-config-commands)
   * [ARP &amp; NDP](#arp--ndp)
      * [ARP show commands](#arp-show-commands)
      * [NDP show commands](#ndp-show-commands)
   * [BGP Configuration And Show Commands](#bgp-configuration-and-show-commands)
      * [BGP show commands](#bgp-show-commands)
      * [BGP config commands](#bgp-config-commands)
   * [ECN Configuration And Show Commands](#ecn-configuration-and-show-commands)
      * [ECN show commands](#ecn-show-commands)
      * [ECN config commands](#ecn-config-commands)
   * [Interface Configuration And Show-Commands](#interface-configuration-and-show-commands)
      * [Interface Show Commands](#interface-show-commands)
      * [Interface Config Commands](#interface-config-commands)
   * [Interface Naming Mode](#interface-naming-mode)
      * [Interface naming mode show commands](#interface-naming-mode-show-commands)
      * [Interface naming mode config commands](#interface-naming-mode-config-commands)
   * [IP](#ip)
      * [IP show commands](#ip-show-commands)
	  * [IPv6 show commands](#ipv6-show-commands)
   * [LLDP](#lldp)
      * [LLDP show commands](#lldp-show-commands)
   * [Loading, Reloading And Saving Configuration](#loading-reloading-and-saving-configuration)
      * [Load config command](#load-config-command)
      * [Load_mgmt_config command](#load_mgmt_config-command)
      * [Load_minigraph config command](#load_minigraph-config-command)
      * [Reload config command](#reload-config-command)
      * [Save config  command](#save-config--command)
   * [Mirroring Configuration And Show](#mirroring-configuration-and-show)
      * [Mirroring Show command](#mirroring-show-command)
      * [Mirroring Config command](#mirroring-config-command)
   * [NTP](#ntp)
      * [NTP show command](#network-time-protocol-show-command)
   * [Platform Specific Commands](#platform-specific-commands)
   * [PortChannel Configuration And Show](#portchannel-configuration-and-show)
      * [PortChannel Show commands](#portchannel-show-commands)
      * [PortChannel Config commands](#portchannel-config-commands)
   * [QoS Configuration &amp; Show](#qos-configuration--show)
      * [QoS Show commands](#qos-show-commands)
         * [PFC](#pfc)
         * [Queue And Priority-Group](#queue-and-priority-group)
      * [QoS config commands](#qos-config-commands)
   * [Startup &amp; Running Configuration](#startup--running-configuration)
      * [Startup Configuration command](#startup-configuration-command)
      * [Running Configuration command](#running-configuration-command)
   * [System State](#system-state)
      * [Processes show commands](#processes-show-commands)
      * [Services &amp; memory show commands](#services--memory-show-commands)
   * [VLAN &amp; FDB](#vlan--fdb)
      * [VLAN](#vlan)
         * [VLAN show commands](#vlan-show-commands)
         * [VLAN Config commands](#vlan-config-commands)
      * [FDB](#fdb)
         * [FDB show commands](#fdb-show-commands)
   * [Warm Restart](#warm-restart)
      * [Warm Restart show command](#warm-restart-show-command)
      * [Warm Restart Config command](#warm-restart-config-command)
   * [Watermark Configuration And Show](#watermark-configuration-and-show)
      * [Watermark Show command](#watermark-show-command)
      * [Watermark Config command](#watermark-config-command)
   * [Software Installation Commands](#software-installation-commands)
      * [SONiC Installer](#sonic-installer)
   * [Troubleshooting Commands](#troubleshooting-commands)
   * [Routing Stack Configuration And Show](#routing-stack-configuration-and-show)
   * [Quagga BGP Show Commands](#Quagga-BGP-Show-Commands)


# Document History

| # | Date    |  Document Version | Details |
| --- | --- | --- | --- |
| 3 |  Jun-26-2019 |v3 | Update based on 201904 (build#19) release, "config interface" command changes related to interfacename order, FRR/Quagga show command changes, platform specific changes, ACL show changes and few formatting changes |
| 2 |  Apr-22-2019 |v2 | CLI Guide for SONiC 201811 version (build#32) with complete "config" command set |
| 1 |  Mar-23-2019 |v1 | Initial version of CLI Guide with minimal command set |

# Introduction
SONiC is an open source network operating system based on Linux that runs on switches from multiple vendors and ASICs. SONiC offers a full-suite of network functionality, like BGP and RDMA, that has been production-hardened in the data centers of some of the largest cloud-service providers. It offers teams the flexibility to create the network solutions they need while leveraging the collective strength of a large ecosystem and community.

SONiC software shall be loaded in these [supported devices](https://github.com/Azure/SONiC/wiki/Supported-Devices-and-Platforms) and this CLI guide shall be used to configure the devices as well as to display the configuration, state and status.

Follow the [Quick Start Guide](https://github.com/Azure/SONiC/wiki/Quick-Start) to boot the device in ONIE mode, install the SONiC software using the steps specified in the document and login to the device using the default username and password.

After logging into the device, SONiC software can be configured in following three methods.
 1) Command Line Interface (CLI)
 2) [config_db.json](https://github.com/Azure/SONiC/wiki/Configuration)
 3) [minigraph.xml](https://github.com/Azure/SONiC/wiki/Configuration-with-Minigraph-(~Sep-2017))

This document explains the first method and gives the complete list of commands that are supported in SONiC 201904 version (build#19).
All the configuration commands need root privileges to execute them. Note that show commands can be executed by all users without the root privileges.
Root privileges can be obtained either by using "sudo" keyword in front of all config commands, or by going to root prompt using "sudo -i".
Note that all commands are case sensitive.

  - Example:
  ```
  admin@sonic:~$ sudo config aaa authentication login tacacs+

  OR

  admin@sonic:~$ sudo -i
  root@sonic:~#  config aaa authentication login tacacs+
  ```

Note that the command list given in this document is just a subset of all possible configurations in SONiC.
Please follow config_db.json based configuration for the complete list of configuration options.

**Scope Of The Document**
It is assumed that all configuration commands start with the keyword “config” as prefix.
Any other scripts/utilities/commands  that need user configuration control are wrapped as sub-commands under the “config” command.
The direct scripts/utilities/commands (examples given below) that are not wrapped under the "config" command are not in the scope of this document.
  1)	Acl_loader – This script is already wrapped inside “config acl” command; i.e. any ACL configuration that user is allowed to do is already part of “config acl” command; users are not expected to use the acl_loader script directly and hence this document need not explain the “acl_loader” script.
  2)	Crm – this command is not explained in this document.
  3)	Sonic-clear, sfputil, etc., This document does not explain these scripts also.

# Basic Configuration And Show

This section covers the basic configurations related to the following
 1) [SSH login](#SSH-Login),
 2) [configuring the management interface](#Configuring-Management-Interface),
 3) [Help for Config Commands](#Config-Help),
 4) [Help For Show Commands](#Show-Help),
 5) [show version](#Show-Versions),
 6) [Show System Status](#Show-System-Status) and
 7) [Show Hardware Platform](#Show-Hardware-Platform).

## SSH Login

All SONiC devices support both the serial console based login and the SSH based login by default.
The default credential (if not modified at image build time) for login is `admin/YourPaSsWoRd`.
In case of SSH login, users can login to the management interface (eth0) IP address after configuring the same using serial console.
Refer the following section for configuring the IP address for management interface.

  - Example:
  ```
  At Console:
  Debian GNU/Linux 9 sonic ttyS1

  sonic login: admin
  Password: YourPaSsWoRd

  SSH from any remote server to sonic can be done by connecting to SONiC IP
  user@debug:~$ ssh admin@sonic_ip_address(or SONIC DNS Name)
  admin@sonic's password:
  ```

By default, login takes the user to the default prompt from which all the show commands can be executed.

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Basic-Configuration-And-Show)

## Configuring Management Interface

The management interface (eth0) in SONiC is configured (by default) to use DHCP client to get the IP address from the DHCP server. Connect the management interface to the same network in which your DHCP server is connected and get the IP address from DHCP server.
The IP address received from DHCP server can be verified using the "/sbin/ifconfig eth0" linux command.

SONiC does not provide a CLI to configure the static IP for the management interface. There are few alternate ways by which a static IP address can be configured for the management interface.
   1) use "ifconfig eth0" linux command (example: ifconfig eth0 10.11.12.13/24). This configuration won't be preserved across reboot.
   Example:
   ```
   admin@sonic:~$ /sbin/ifconfig eth0 10.11.12.13/24
   ```
   2) use config_db.json and configure the MGMT_INTERFACE key with the appropriate values. Refer [here](https://github.com/Azure/SONiC/wiki/Configuration#Management-Interface)
   3) use minigraph.xml and configure "ManagementIPInterfaces" tag inside "DpgDesc" tag as given at the [page](https://github.com/Azure/SONiC/wiki/Configuration-with-Minigraph-(~Sep-2017))

Once the IP address is configured, the same can be verified using "/sbin/ifconfig eth0" linux command.
Users can SSH login to this management interface IP address from their management network.

  - Example:
   ```
   admin@sonic:~$ /sbin/ifconfig eth0
   eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
         inet 10.11.11.13  netmask 255.255.255.0  broadcast 10.11.12.255
   ```
Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Basic-Configuration-And-Show)

## Config Help

All commands has got in-built help that helps the user to understand the command as well as the possible sub-commands and options.
"--help" can be used at any level of the command; i.e. it can be used at the command level, or sub-command level or at argument level. The in-built help will display the next possibilities corresponding to that particular command/sub-command.

**config --help**

This command lists all the possible configuration commands at the top level.

- Usage:
  config --help

- Example:
  ```
  admin@sonic:~$ config --help
  Usage: config [OPTIONS] COMMAND [ARGS]
  SONiC command line - 'config' command

  Options:
    --help  Show this message and exit.

  Commands:
    aaa                    AAA command line
    acl                    ACL-related configuration tasks
    bgp                    BGP-related configuration tasks
    ecn                    ECN-related configuration tasks
    interface              Interface-related configuration tasks
    interface_naming_mode  Modify interface naming mode for interacting...
    load                   Import a previous saved config DB dump file.
    load_mgmt_config       Reconfigure hostname and mgmt interface based...
    load_minigraph         Reconfigure based on minigraph.
    mirror_session
    platform               Platform-related configuration tasks
    portchannel
    qos
    reload                 Clear current configuration and import a...
    save                   Export current config DB to a file on disk.
    tacacs                 TACACS+ server configuration
    vlan                   VLAN-related configuration tasks
    warm_restart           warm_restart-related configuration tasks
    watermark              Configure watermark

  ```
Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Basic-Configuration-And-Show)

## Show Help

**show help**
This command displays the full list of show commands available in the software; the output of each of those show commands can be used to analyze, debug or troubleshoot the network node.

- Usage:
  You can enter `show -?`, `show -h` or `show --help`

- Example:
  ```
  admin@sonic:~$ show -?
  Usage: show [OPTIONS] COMMAND [ARGS]...
    SONiC command line - 'show' command

  Options:
    -?, -h, --help  Show this message and exit.

  Commands:
    aaa                   Show AAA configuration
    acl                   Show ACL related information
    arp                   Show IP ARP table
    clock                 Show date and time
    ecn                   Show ECN configuration
    environment           Show environmentals (voltages, fans, temps)
    interfaces            Show details of the network interfaces
    ip                    Show IP (IPv4) commands
    ipv6                  Show IPv6 commands
    line                  Show all /dev/ttyUSB lines and their info
    lldp                  LLDP (Link Layer Discovery Protocol)...
    logging               Show system log
    mac                   Show MAC (FDB) entries
    mirror_session        Show existing everflow sessions
    mmu                   Show mmu configuration
    ndp                   Show IPv6 Neighbour table
    ntp                   Show NTP information
    pfc                   Show details of the priority-flow-control...
    platform              Show platform-specific hardware info
    priority-group        Show details of the PGs
    processes             Display process information
    queue                 Show details of the queues
    reboot-cause          Show cause of most recent reboot
    route-map             show route-map
    runningconfiguration  Show current running configuration...
    services              Show all daemon services
    startupconfiguration  Show startup configuration information
    system-memory         Show memory information
    tacacs                Show TACACS+ configuration
    techsupport           Gather information for troubleshooting
    uptime                Show system uptime
    users                 Show users
    version               Show version information
    vlan                  Show VLAN information
    warm_restart          Show warm restart configuration and state
    watermark             Show details of watermark

  ```

The same syntax applies to all subgroups of `show` which themselves contain subcommands, and subcommands which accept options/arguments.

- Example:
  ```
  user@debug:~$ show interfaces -?

    Show details of the network interfaces

  Options:
    -?, -h, --help  Show this message and exit.

  Commands:
    counters     Show interface counters
    description  Show interface status, protocol and...
    naming_mode  Show interface naming_mode status
    neighbor     Show neighbor related information
    portchannel  Show PortChannel information
    status       Show Interface status information
    transceiver  Show SFP Transceiver information
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Basic-Configuration-And-Show)


## Show Versions

**show version**
This command displays software component versions of the currently running SONiC image. This includes the SONiC image version as well as Docker image versions.
This command displays relevant information as the SONiC and Linux kernel version being utilized, as well as the commit-id used to build the SONiC image. The second section of the output displays the various docker images and their associated id’s.

- Usage:
  show version

- Example:
  ```
  admin@sonic:~$ show version
  SONiC Software Version: SONiC.HEAD.32-21ea29a
  Distribution: Debian 9.8
  Kernel: 4.9.0-8-amd64
  Build commit: 21ea29a
  Build date: Fri Mar 22 01:55:48 UTC 2019
  Built by: johnar@jenkins-worker-4

  Docker images:
  REPOSITORY                 TAG                 IMAGE ID            SIZE
  docker-syncd-brcm          HEAD.32-21ea29a     434240daff6e        362MB
  docker-syncd-brcm          latest              434240daff6e        362MB
  docker-orchagent-brcm      HEAD.32-21ea29a     e4f9c4631025        287MB
  docker-orchagent-brcm      latest              e4f9c4631025        287MB
  docker-lldp-sv2            HEAD.32-21ea29a     9681bbfea3ac        275MB
  docker-lldp-sv2            latest              9681bbfea3ac        275MB
  docker-dhcp-relay          HEAD.32-21ea29a     2db34c7bc6f4        257MB
  docker-dhcp-relay          latest              2db34c7bc6f4        257MB
  docker-database            HEAD.32-21ea29a     badc6fc84cdb        256MB
  docker-database            latest              badc6fc84cdb        256MB
  docker-snmp-sv2            HEAD.32-21ea29a     e2776e2a30b7        295MB
  docker-snmp-sv2            latest              e2776e2a30b7        295MB
  docker-teamd               HEAD.32-21ea29a     caf957cd2ad1        275MB
  docker-teamd               latest              caf957cd2ad1        275MB
  docker-router-advertiser   HEAD.32-21ea29a     b1a62023958c        255MB
  docker-router-advertiser   latest              b1a62023958c        255MB
  docker-platform-monitor    HEAD.32-21ea29a     40b40a4b2164        287MB
  docker-platform-monitor    latest              40b40a4b2164        287MB
  docker-fpm-quagga          HEAD.32-21ea29a     546036fe6838        282MB
  docker-fpm-quagga          latest              546036fe6838        282MB

  ```
Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Basic-Configuration-And-Show)


## Show System Status
This sub-section explains some set of sub-commands that are used to display the status of various parameters pertaining to the physical state of the network node.

**show clock**
This command displays the current date and time configured on the system

-  Usage:
   show clock

- Example:
  ```
  admin@sonic:~$ show clock
  Mon Mar 25 20:25:16 UTC 2019
  ```

**show boot**
This command displays the current OS image, the image loaded on next reboot, and the lists the available images on the system

-  Usage:
   show boot

- Example:
  ```
  admin@sonic:~$ show boot
  Current: SONiC-OS-20181130.31
  Next: SONiC-OS-20181130.31
  Available: 
  SONiC-OS-20181130.31
  ```

**show environment**
This command displays the platform environmentals, such as voltages, temperatures and fan speeds

-  Usage:
   show environment

- Example:
  ```
  admin@sonic:~$ show environment
  coretemp-isa-0000
  Adapter: ISA adapter
  Core 0:       +28.0 C  (high = +98.0 C, crit = +98.0 C)
  Core 1:       +28.0 C  (high = +98.0 C, crit = +98.0 C)
  Core 2:       +28.0 C  (high = +98.0 C, crit = +98.0 C)
  Core 3:       +28.0 C  (high = +98.0 C, crit = +98.0 C)
  SMF_Z9100_ON-isa-0000
  Adapter: ISA adapter
  CPU XP3R3V_EARLY:              +3.22 V
  <... few more things ...>

  Onboard Temperature Sensors:
  CPU:                             30 C
  BCM56960 (PSU side):             35 C
  <... few more things ...>

  Onboard Voltage Sensors:
    CPU XP3R3V_EARLY                 3.22 V
  <... few more things ...>

  Fan Trays:
  Fan Tray 1:
    Fan1 Speed:     6192 RPM
    Fan2 Speed:     6362 RPM
    Fan1 State:        Normal
    Fan2 State:        Normal
    Air Flow:            F2B
  <... few more things ...>

  PSUs:
    PSU 1:
      Input:           AC
  <... few more things ...>

  ```
NOTE: The show output has got lot of information; only the sample output is given in the above example.
Though the displayed output slightly differs from one platform to another platform, the overall content will be similar to the example mentioned above.

**show reboot-cause**
This command displays the cause of the previous reboot

- Usage:
  show reboot-cause

-  Example:
  ```
  admin@sonic:~$ show reboot-cause
  User issued reboot command [User: admin, Time: Mon Mar 25 01:02:03 UTC 2019]
  ```

**show uptime**
This command displays the current system uptime

- Usage:
  show uptime

- Example:
  ```
  admin@sonic:~$ show uptime
  up 2 days, 21 hours, 30 minutes
  ```

**show logging**
This command displays all the currently stored log messages.
All the latest processes and corresponding transactions are stored in the "syslog" file.
This file is saved in the path `/var/log` and can be viewed by giving the command ` sudo cat syslog` as this requires root login.
Individual process can also be viewed using the command `ps -ax | grep <\process name>

- Usage:
  show logging ([\<process_name\>] [-l lines] | [-f])

- Example:
  ```
  admin@sonic:~$ show logging
  ```
  - It can be useful to pipe the output from `show logging` to the command `more` in order to examine one screenful of log messages at a time

- Example:
  ```
  admin@sonic:~$ show logging | more
  ```
  - Optionally, you can specify a process name in order to display only log messages mentioning that process

- Example:
  ```
  admin@sonic:~$ show logging sensord
  ```
  - Optionally, you can specify a number of lines to display using the `-l' or `--lines` option. Only the most recent N lines will be displayed. Also note that this option can be combined with a process name.

- Examples:
  ```
  admin@sonic:~$ show logging --lines 50
  ```
  ```
  admin@sonic:~$ show logging sensord --lines 50
  ```

  - Optionally, you can follow the log live as entries are written to it by specifying the `-f` or `--follow` flag

- Example:
  ```
  admin@sonic:~$ show logging --follow
  ```

**show users**
This command displays a list of users currently logged in to the device

- Usage:
  show users

- Examples:
  ```
  admin@sonic:~$ show users
  admin    pts/9        Mar 25 20:31 (100.127.20.23)

  admin@sonic:~$ show users
  admin    ttyS1        2019-03-25 20:31

  ```
Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Basic-Configuration-And-Show)

## Show Hardware Platform

The information displayed in this set of commands partially overlaps with the one generated by “show envinronment” instruction. In this case though, the information is presented in a more succinct fashion. In the future these two CLI stanzas may end up getting combined.

**show platform summary**
This command displays a summary of the device's hardware platform

- Usage:
  show platform summary

- Example:
  ```
  admin@sonic:~$ show platform summary
  Platform: x86_64-dell_s6000_s1220-r0
  HwSKU: Force10-S6000
  ASIC: broadcom
  ```

**show platform syseeprom**
This command displays information stored on the system EEPROM.
Note that the output of this command is not the same for all vendor's platforms.
Couple of example outputs are given below.

- Usage:
  show platform syseeprom

- Example:
  ```
  admin@sonic:~$ show platform syseeprom
  lsTLV Name             Len Value
  -------------------- --- -----
  PPID                  20 XX-XXXXXX-00000-000-0000
  DPN Rev                3 XXX
  Service Tag            7 XXXXXXX
  Part Number           10 XXXXXX
  Part Number Rev        3 XXX
  Mfg Test Results       2 FF
  Card ID                2 0x0000
  Module ID              2 0
  Base MAC Address      12 FE:EC:BA:AB:CD:EF
  (checksum valid)
  ```

  ```
	admin@arc-switch1025:~$ show platform syseeprom
	TlvInfo Header:
	  Id String:    TlvInfo
	  Version:      1
	  Total Length: 527
	TLV Name             Code Len Value
	---- --- -----
	Product Name         0x21  64 MSN2700
	Part Number          0x22  20 MSN2700-CS2FO
	Serial Number        0x23  24 MT1822K07815
	Base MAC Address     0x24   6 50:6B:4B:8F:CE:40
	Manufacture Date     0x25  19 05/28/2018 23:56:02
	Device Version       0x26   1 16
	MAC Addresses        0x2A   2 128
	Manufacturer         0x2B   8 Mellanox
	Vendor Extension     0xFD  36
	Vendor Extension     0xFD 164
	Vendor Extension     0xFD  36
	Vendor Extension     0xFD  36
	Vendor Extension     0xFD  36
	Platform Name        0x28  18 x86_64-mlnx_x86-r0
	ONIE Version         0x29  21 2018.08-5.2.0006-9600
	CRC-32               0xFE   4 0x11C017E1

	(checksum valid)
  ```



**show platform psustatus**
This command displays the status of the device's power supply units

- Usage:
  show platform psustatus

- Example:
  ```
  admin@sonic:~$ show platform psustatus
  PSU    Status
  -----  --------
  PSU 1  OK
  PSU 2  OK
  ```

### Transceivers
Displays diagnostic monitoring information of the transceivers

**show interfaces transceiver**
This command displays information for all the interfaces for the transceiver requested or a specific interface if the optional "interface-name" is specified.

- Usage:
  show interfaces transceiver [eeprom | lpmode | presence]
  show interfaces transceiver [eeprom [-d | --dom] | lpmode | presence] [<interface-name>]

- Example (Decode and display information stored on the SFP EEPROM):
  ```
  admin@sonic:~$ show interfaces transceiver eeprom --dom Ethernet0
  Ethernet0: SFP detected
          Connector : No separable connector
          Encoding : Unspecified
          Extended Identifier : Unknown
          Extended RateSelect Compliance : QSFP+ Rate Select Version 1
          Identifier : QSFP+
          Length Cable Assembly(m) : 1
          Specification compliance :
                  10/40G Ethernet Compliance Code : 40GBASE-CR4
                  Fibre Channel Speed : 1200 Mbytes/Sec
                  Fibre Channel link length/Transmitter Technology : Electrical inter-enclosure (EL)
                  Fibre Channel transmission media : Twin Axial Pair (TW)
          Vendor Date Code(YYYY-MM-DD Lot) : 2015-10-31
          Vendor Name : XXXXX
          Vendor OUI : XX-XX-XX
          Vendor PN : 1111111111
          Vendor Rev :
          Vendor SN : 111111111
          ChannelMonitorValues:
                RX1Power: -1.1936dBm
                RX2Power: -1.1793dBm
                RX3Power: -0.9388dBm
                RX4Power: -1.0729dBm
                TX1Bias: 4.0140mA
                TX2Bias: 4.0140mA
                TX3Bias: 4.0140mA
                TX4Bias: 4.0140mA
          ModuleMonitorValues :
                  Temperature : 1.1111C
                  Vcc : 0.0000Volts
  ```

- Example (Display status of low-power mode):
  ```
  admin@sonic:~$ show interfaces transceiver lpmode Ethernet100
  Port         Low-power Mode
  -----------  ----------------
  Ethernet100  On
  ```


- Example (Display SFP transceiver presence):
  ```
  admin@sonic:~$ show interfaces transceiver presence Ethernet100
  Port         Presence
  -----------  ----------
  Ethernet100  Present
  ```
Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Basic-Configuration-And-Show)

# AAA & TACACS+ Configuration And Show
This section captures the various show commands & configuration commands that are applicable for the AAA (Authentication, Authorization, and Accounting) module.
Admins can configure the type of authentication (local or remote tacacs based) required for the users and also the authentication failthrough and fallback options.
Following show command displays the current running configuration related to the AAA.

## AAA Configuration And Show

### AAA show commands

This command is used to view the Authentication, Authorization & Accounting settings that are configured in the network node.

**show aaa**
This command displays the AAA settings currently present in the network node

- Usage:
  show aaa

- Example:
   ```
   admin@sonic:~$ show aaa
   AAA authentication login local (default)
   AAA authentication failthrough True (default)
   AAA authentication fallback True (default)
   ```

### AAA config commands

This sub-section explains all the possible CLI based configuration options for the AAA module. The list of commands/sub-commands possible for aaa is given below.

	Command: aaa authentication
             sub-commands:
               aaa authentication failthrough
               aaa authentication fallback
               aaa authentication login

**aaa authentication failthrough**

This command is used to either enable or disable the failthrough option.
This command is useful when user has configured more than one tacacs+ server and when user has enabled tacacs+ authentication.
When authentication request to the first server fails, this configuration allows to continue the request to the next server.
When this configuration is enabled, authentication process continues through all servers configured.
When this is disabled and if the authentication request fails on first server, authentication process will stop and the login will be disallowed.


- Usage:
  config aaa authentication failthrough enable|disable|default

		   Allow AAA fail-through [enable | disable | default]
           enable - this allows the AAA module to process with local authentication if remote authentication fails.
		   disbale - this disallows the AAA module to proceed further if remote authentication fails.
		   default - this re-configures the default value, which is "enable".


- Example:
  ```
  admin@sonic:~$ sudo -i
  root@sonic:~# config aaa authentication failthrough enable
  root@sonic:~#
  ```
**aaa authentication fallback**

The command is not used at the moment.
When the tacacs+ authentication fails, it falls back to local authentication by default.

- Usage:
  config aaa authentication fallback enable|disable|default

	   Allow AAA fallback [enable | disable | default]

- Example:
  ```
  root@sonic:~# config aaa authentication fallback enable
  root@sonic:~#
  ```

**aaa authentication login**

This command is used to either configure whether AAA should use local database or remote tacacs+ database for user authentication.
By default, AAA uses local database for authentication. New users can be added/deleted using the linux commands (Note that the configuration done using linux commands are not preserved during reboot).
Admin can enable remote tacacs+ server based authentication by selecting the AUTH_PROTOCOL as tacacs+ in this command.
Admins need to configure the tacacs+ server accordingly and ensure that the connectivity to tacacas+ server is available via the management interface.
Once if the admins choose the remote authentication based on tacacs+ server, all user logins will be authenticated by the tacacs+ server.
If the authentication fails, AAA will check the "failthrough" configuration and authenticates the user based on local database if failthrough is enabled.

- Usage:
  Switch login authentication [ {tacacs+, local} | default ]

	  Switch login authentication [ {tacacs+, local} | default ]
	  tacacs+ - This enables remote authentication based on tacacs+
	  local - this disables remote authentication and uses local authentication
	  default - reset back to default value, which is nothing but the "local" authentication


- Example:
  ```
  root@sonic:~# config aaa authentication login tacacs+
  root@sonic:~#
  ```


## TACACS+ Configuration And Show

### TACACS+ show commands

**show tacacs**

This command displays the global configuration fields and the list of all tacacs servers and their correponding configurations.

- Usage:
	show tacacs

- Example:
  ```
	TACPLUS global auth_type pap (default)
	TACPLUS global timeout 99
	TACPLUS global passkey <EMPTY_STRING> (default)

	TACPLUS_SERVER address 10.11.12.14
				   priority 9
				   tcp_port 50
				   auth_type mschap
				   timeout 10
				   passkey testing789

	TACPLUS_SERVER address 10.0.0.9
				   priority 1
				   tcp_port 49
  ```

### TACACS+ Config commands

This sub-section explains the command "config tacacs" and its sub-commands that are used to configure the following tacacs+ parameters.
Some of the parameters like authtype, passkey and timeout can be either configured at per server level or at global level (global value will be applied if there no server level configuration)

1) Add/Delete the tacacs+ server details.
2) authtype - global configuration that is applied to all servers if there is no server specific configuration.
3) default - reset the authtype or passkey or timeout to the default values.
4) passkey - global configuration that is applied to all servers if there is no server specific configuration.
5) timeout - global configuration that is applied to all servers if there is no server specific configuration.

**config tacacs add**

This command is used to add a TACACS+ server to the tacacs server list.
Note that more than one tacacs+ (maximum of seven) can be added in the device.
When user tries to login, tacacs client shall contact the servers one by one.
When any server times out, device will try the next server one by one based on the priority value configured for that server.
When this command is executed, the configured tacacs+ server addresses are updated in /etc/pam.d/common-auth-sonic configuration file which is being used by tacacs service.

- Usage:
   config tacacs add <ip_address> [-t|--timeout SECOND] [-k|--key SECRET] [-a|--type TYPE] [-o|--port PORT] [-p|--pri PRIORITY] [-m|--use-mgmt-vrf]

	 **Arguments:**

	 ip_address - TACACS+ server IP address.
	 timeout - Transmission timeout interval in seconds, range 1 to 60, default 5
	 key - Shared secret
	 type - Authentication type, "chap" or "pap" or "mschap" or "login", default is "pap".
	 port - TCP port range is 1 to 65535, default 49
	 pri - Priority, priority range 1 to 64, default 1.
	 use-mgmt-vrf - this means that the server is part of Management vrf, default is "no vrf"


- Example:
  ```
  root@T1-2:~# config tacacs add 10.11.12.13 -t 10 -k testing789 -a mschap -o 50 -p 9
  root@T1-2:~#

	Example Server Configuration in /etc/pam.d/common-auth-sonic configuration file:

	auth    [success=done new_authtok_reqd=done default=ignore]     pam_tacplus.so server=10.11.12.14:50 secret=testing789 login=mschap timeout=10  try_first_pass
	auth    [success=done new_authtok_reqd=done default=ignore]     pam_tacplus.so server=10.11.12.24:50 secret=testing789 login=mschap timeout=987654321098765433211
	0987  try_first_pass
	auth    [success=done new_authtok_reqd=done default=ignore]     pam_tacplus.so server=10.0.0.9:49 secret= login=mschap timeout=5  try_first_pass
	auth    [success=done new_authtok_reqd=done default=ignore]     pam_tacplus.so server=10.0.0.8:49 secret= login=mschap timeout=5  try_first_pass
	auth    [success=done new_authtok_reqd=done default=ignore]     pam_tacplus.so server=10.11.12.13:50 secret=testing789 login=mschap timeout=10  try_first_pass
	auth    [success=1 default=ignore]      pam_unix.so nullok try_first_pass

	   NOTE: In the above example, the servers are stored (sorted) based on the priority value configured for the server.

  ```

**config tacacs delete**

This command is used to delete the tacacs+ servers configured.

- Usage:
   config tacacs delete <ip_address>

- Example:
  ```
  root@T1-2:~# config tacacs delete 10.11.12.13
  root@T1-2:~#
  ```

**config tacacs authtype**

This command is used to modify the global value for the TACACS+ authtype.
When user has not configured server specific authtype, this global value shall be used for that server.

   - Usage:
     config tacacs authtype  chap|pap||mschap|login

- Example:
  ```
  root@T1-2:~# config tacacs authtype mschap
  root@T1-2:~#
  ```

**config tacacs default**

This command is used to reset the global value for authtype or passkey or timeout to default value.
Default for authtype is "pap", default for passkey is EMPTY_STRING and default for timeout is 5 seconds.

- Usage:
   config tacacs default authtype|passkey|timeout


- Example:
  ```
  root@T1-2:~# config tacacs default authtype
  This will reset the global authtype back to the default value "pap".
  ```

**config tacacs passkey**

This command is used to modify the global value for the TACACS+ passkey.
When user has not configured server specific passkey, this global value shall be used for that server.

   - Usage:
     config tacacs passkey <pass_key>


- Example:
  ```
  root@T1-2:~# config tacacs passkey testing123
  root@T1-2:~#
  ```

**config tacacs timeout**

This command is used to modify the global value for the TACACS+ timeout.
When user has not configured server specific timeout, this global value shall be used for that server.


   - Usage:
    config tacacs [default] timeout [\<timeout_value_in_seconds\>]
     valid values for timeout is 1 to 60 seconds.
	 When the optional keyword "default" is specified, timeout_value_in_seconds parameter wont be used; default value of 5 is used.
	 Configuration using the keyword "default" is introduced in 201904 release.

- Example: To configure non-default timeout value
  ```
  root@T1-2:~# config tacacs timeout 60
  root@T1-2:~#
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#AAA-Configuration-And-Show)



# ACL Configuration And Show

This section explains the various show commands and configuration commands available for users.

## ACL show commands

**show acl table**

This command displays either all the ACL tables that are configured or only the specified "TABLE_NAME".
Output from the command displays the table name, type of the table, the list of interface(s) to which the table is bound and the description about the table.

- Usage:
  show acl table [TABLE_NAME]

- Example:
  ```
  admin@sonic:~$ show acl table
	Name      Type       Binding          Description
	--------  ---------  ---------------  -------------
	EVERFLOW  MIRROR     Ethernet16       EVERFLOW
						 Ethernet96
						 Ethernet108
						 Ethernet112
						 PortChannel0001
						 PortChannel0002
	SNMP_ACL  CTRLPLANE  SNMP             SNMP_ACL
	DT_ACL_T1 L3         Ethernet0        DATA_ACL_TABLE_1
						 Ethernet4
						 Ethernet112
						 Ethernet116
	SSH_ONLY  CTRLPLANE  SSH              SSH_ONLY

  ```

**show acl rule**

This command displays all the ACL rules present in all the ACL tables or only the rules present in specified table "TABLE_NAME" or only the rule matching the RULE_ID option.
Output from the command gives the following information about the rules
1) Table name - ACL table name to which the rule belongs to.
2) Rule name - ACL rule name
3) Priority - Priority for this rule.
4) Action - Action to be performed if the packet matches with this ACL rule. It could be either Drop or Permit. Users can choose to have a default permit rule or default deny rule. In case of default "deny all" rule, add the permitted rules on top of the deny rule. In case of the default "permit all" rule, users can add the deny rules on top of it. If users have not confgured any rule, SONiC allows all traffic (which is "permit all").
5) Match  - The fields from the packet header that need to be matched against the same present in the incoming traffic.

- Usage:
  show acl rule [TABLE_NAME] [RULE_ID]


- Example:
  ```
  admin@sonic:~$ show acl rule
	Table     Rule          Priority    Action    Match
	--------  ------------  ----------  --------  ------------------
	SNMP_ACL  RULE_1        9999        ACCEPT    IP_PROTOCOL: 17
												  SRC_IP: 1.1.1.1/32
	SSH_ONLY  RULE_1        9999        ACCEPT    IP_PROTOCOL: 6
												  SRC_IP: 1.1.1.1/32
	SNMP_ACL  DEFAULT_RULE  1           DROP      ETHER_TYPE: 2048
	SSH_ONLY  DEFAULT_RULE  1           DROP      ETHER_TYPE: 2048

  ```



## ACL config commands
This sub-section explains the list of configuration options available for ACL module.
Note that there is no direct command to add or delete or modify the ACL table and ACL rule.
Existing ACL tables and ACL rules can be updated by specifying the ACL rules in json file formats and configure those files using this CLI command.

	Command :acl
              update
                 full
                 incremental


**config acl update full**

This command is to update the rules in all the tables or in one specific table in full. If a table_name is provided, the operation will be restricted in the specified table. All existing rules in the specified table or all tables will be removed. New rules loaded from file will be installed. If the table_name is specified, only rules within that table will be removed and new rules in that table will be installed. If the table_name is not specified, all rules from all tables will be removed and only the rules present in the input file will be added.

The command does not modify anything in the list of acl tables. It modifies only the rules present in those pre-existing tables.

In order to create acl tables, either follow the config_db.json method or minigraph method to populate the list of ACL tables.

After creating tables, either the config_db.json method or the minigraph method or the CLI method (explained here) can be used to populate the rules in those ACL tables.

This command updates only the ACL rules and it does not disturb the ACL tables; i.e. the output of "show acl table" is not alterted by using this command; only the output of "show acl rule" will be changed after this command.

When "--session_name" optional argument is specified, command sets the session_name for the ACL table with this mirror session name. It fails if the specified mirror session name does not exist.

When the optional argument "max_priority"  is specified, each rule’s priority is calculated by subtracting its “sequence_id” value from the “max_priority”. If this value is not passed, the default “max_priority” 10000 is used.

- Usage:
  config acl update full FILE_NAME
	Some of the possible options are
	1) --table_name <table_name>, Example: config acl update full " --table_name DT_ACL_T1  /etc/sonic/acl_table_1.json "
	2) --session_name <session_name>, Example: config acl update full " --session_name mirror_ses1 /etc/sonic/acl_table_1.json "
	3) --max_priority <priority_value>, Example: config acl update full " --max-priority 100  /etc/sonic/acl_table_1.json "

	NOTE: All these optional parameters should be inside the double quotes. If none of the options are provided, double quotes is not required for specifying filename alone.
	Any number of optional parameters can be configured in the same command.

- Example:
  ```
  admin@sonic:~$ config acl update full /etc/sonic/acl_full_snmp_1_2_ssh_4.json
  admin@sonic:~$ config acl update full " --table_name SNMP-ACL /etc/sonic/acl_full_snmp_1_2_ssh_4.json "
  admin@sonic:~$ config acl update full " --session_name everflow0 /etc/sonic/acl_full_snmp_1_2_ssh_4.json "

  This command will remove all rules from all the ACL tables and insert all the rules present in this input file.
  Refer the example file [acl_full_snmp_1_2_ssh_4.json](#) that adds two rules for SNMP (Rule1 and Rule2) and one rule for SSH (Rule4)
  Refer an example for input file format [here](https://github.com/Azure/sonic-mgmt/blob/master/ansible/roles/test/files/helpers/config_service_acls.sh)
  Refer another example [here](https://github.com/Azure/sonic-mgmt/blob/master/ansible/roles/test/tasks/acl/acltb_test_rules_part_1.json)
  ```

**config acl update incremental:**

This command is used to perform incremental update of ACL rule table. This command gets existing rules from Config DB and compares with rules specified in input file and performs corresponding modifications.

With respect to DATA ACLs, the command does not assume that new dataplane ACLs can be inserted in betweeen by shifting existing ACLs in all ASICs. Therefore, this command performs a full update on dataplane ACLs.
With respect to control plane ACLs, this command performs an incremental update.
If we assume that "file1.json" is the already loaded ACL rules file and if "file2.json" is the input file that is passed as parameter for this command, the following requirements are valid for the input file.
1) First copy the file1.json to file2.json.
2) Remove the unwanted ACL rules from file2.json
3) Add the newly required ACL rules into file2.json.
4) Modify the existing ACL rules (that require changes) in file2.json.

NOTE: If any ACL rule that is already available in file1.json is required even after this command execution, such rules should remain unalterted in file2.json. Don't remove them.
Note that "incremental" is working like "full".

When "--session_name" optional argument is specified, command sets the session_name for the ACL table with this mirror session name. It fails if the specified mirror session name does not exist.

When the optional argument "max_priority"  is specified, each rule’s priority is calculated by subtracting its “sequence_id” value from the “max_priority”. If this value is not passed, the default “max_priority” 10000 is used.

  - Usage:
    config acl update incremental FILE_NAME
	Some of the possible options are
	1) --session_name <session_name>, Example: config acl update full " --session_name mirror_ses1 /etc/sonic/acl_table_1.json "
	2) --max-priority <priority_value>, Example: config acl update full " --max-priority 100  /etc/sonic/acl_table_1.json "

	NOTE: All these optional parameters should be inside the double quotes. If none of the options are provided, double quotes is not required for specifying filename alone.
	Any number of optional parameters can be configured in the same command.

- Example:
  ```
  admin@sonic:~$ config acl update incremental /etc/sonic/acl_incremental_snmp_1_3_ssh_4.json
  admin@sonic:~$ config acl update incremental " --session_name everflow0 /etc/sonic/acl_incremental_snmp_1_3_ssh_4.json "

  Refer the example file [acl_incremental_snmp_1_3_ssh_4.json](#) that adds two rules for SNMP (Rule1 and Rule3) and one rule for SSH (Rule4)
  When this "incremental" command is executed after "full" command, it has removed SNMP Rule2 and added SNMP Rule3 in the example.
  File "acl_full_snmp_1_2_ssh_4.json" has got SNMP Rule1, SNMP Rule2 and SSH Rule4.
  File "acl_incremental_snmp_1_3_ssh_4.json" has got SNMP Rule1, SNMP Rule3 and SSH Rule4.
  This file is created by copying the file "acl_full_snmp_1_2_ssh_4.json" to "acl_incremental_snmp_1_3_ssh_4.json" and then removing SNMP Rule2 and adding SNMP Rule3.

  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#ACL-Configuration-And-Show)


# ARP &amp; NDP

## ARP show commands

**show arp**

This command displays the ARP entries in the device with following options.
1) Display the entire table.
2) Display the ARP entries learnt on a specific interface.
3) Display the ARP of a specific ip-address.

  - Usage:
    show arp [-if \<if_name\>] [\<ip_address\>]
    show arp - displays all entries
    show arp -if <ifname> - displays the ARP specific to the specified interface.
    show arp <ip-address> - displays the ARP specific to the specicied ip-address.


- Example:
  ```
  admin@sonic:~$ show arp
   Address          MacAddress            Iface         Vlan
  -------------     -----------------     -------       ------
  192.168.1.183     88:5a:92:fb:bf:41     Ethernet44    -
  192.168.1.175     88:5a:92:fc:95:81     Ethernet28    -
  192.168.1.181     e4:c7:22:c1:07:7c     Ethernet40    -
  192.168.1.179     88:5a:92:de:a8:bc     Ethernet36    -
  192.168.1.118     00:1c:73:3c:de:43     Ethernet64    -
  192.168.1.11      00:1c:73:3c:e1:38     Ethernet88    -
  192.168.1.161     24:e9:b3:71:3a:01     Ethernet0     -
  192.168.1.189     24:e9:b3:9d:57:41     Ethernet56    -
  192.168.1.187     74:26:ac:8b:8f:c1     Ethernet52    -
  192.168.1.165     88:5a:92:de:a0:7c     Ethernet8     -

  Total number of entries 10
  ```

  - Optionally, you can specify the interface in order to display the ARPs learnt on that particular interface


- Example:
  ```
    admin@sonic:~$ show arp -if Ethernet40
    Address          MacAddress          Iface        Vlan
    -------------    -----------------   ----------   ------
    192.168.1.181    e4:c7:22:c1:07:7c   Ethernet40   -
    Total number of entries 1

  ```

  - Optionally, you can specify an IP address in order to display only that particular entry

- Example:
  ```
    admin@sonic:~$ show arp 192.168.1.181
    Address          MacAddress          Iface        Vlan
    -------------    -----------------   ----------   ------
    192.168.1.181    e4:c7:22:c1:07:7c   Ethernet40   -
    Total number of entries 1

  ```

## NDP show commands

**show ndp**
This command displays either all the IPv6 neighbor mac addresses, or for a particular IPv6 neighbor, or for all IPv6 neighbors reachable via a specific interface.

  - Usage:
    show ndp [-if|--iface \<interface_name\>] [IPv6_ADDRESS]


- Example:
  ```
    **ALL IPv6 NEIGHBORS:**
	admin@sonic:~$ show ndp
	Address                   MacAddress         Iface    Vlan    Status
	------------------------  -----------------  -------  ------  ---------
	fe80::20c:29ff:feb8:b11e  00:0c:29:b8:b1:1e  eth0     -       REACHABLE
	fe80::20c:29ff:feb8:cff0  00:0c:29:b8:cf:f0  eth0     -       REACHABLE
	fe80::20c:29ff:fef9:324   00:0c:29:f9:03:24  eth0     -       REACHABLE
	Total number of entries 3

	**SPECIFIC IPv6 NEIGHBOR**
	admin@sonic:~$ show ndp fe80::20c:29ff:feb8:b11e
	Address                   MacAddress         Iface    Vlan    Status
	------------------------  -----------------  -------  ------  ---------
	fe80::20c:29ff:feb8:b11e  00:0c:29:b8:b1:1e  eth0     -       REACHABLE
	Total number of entries 1

	**SPECIFIC INTERFACE**
	admin@sonic:~$ show ndp -if eth0
	Address                   MacAddress         Iface    Vlan    Status
	------------------------  -----------------  -------  ------  ---------
	fe80::20c:29ff:feb8:b11e  00:0c:29:b8:b1:1e  eth0     -       REACHABLE
	fe80::20c:29ff:feb8:cff0  00:0c:29:b8:cf:f0  eth0     -       REACHABLE
	fe80::20c:29ff:fef9:324   00:0c:29:f9:03:24  eth0     -       REACHABLE
	Total number of entries 3

  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Watermark-Configuration-And-Show)


# BGP Configuration And Show Commands

This section explains all the BGP show commands and BGP configuation commands in both "Quagga" and "FRR" routing software that are supported in SONiC.
In 201811 and older verisons "Quagga" was enabled by default. In current version "FRR" is enabled by default.
Most of the FRR show commands start with "show bgp". Similar commands in Quagga starts with "show ip bgp". All sub-options supported in all these show commands are common for FRR and Quagga.
Detailed show commands examples for Quagga are provided at the end of this document.This section captures only the commands supported by FRR.

## BGP show commands


**show bgp summary (for default FRR in 201904+ version) **
**show ip bgp summary (for Quagga in 201811- version) **

This command displays the summary of all IPv4 & IPv6 bgp neighbors that are configured and the corresponding states.

- Usage:
  show bgp summary (for default FRR in 201904+ version)
  show ip bgp summary (for Quagga in 201811- version)

- Example:
  ```
   root@sonic-z9264f-9251:~# show bgp summary

   IPv4 Unicast Summary:
   BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
   BGP table version 6465
   RIB entries 12807, using 2001 KiB of memory
   Peers 4, using 83 KiB of memory
   Peer groups 2, using 128 bytes of memory

   Neighbor        V         AS MsgRcvd MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd
   10.0.0.57       4      64600    3995    4001        0    0    0 00:39:32         6400
   10.0.0.59       4      64600    3995    3998        0    0    0 00:39:32         6400
   10.0.0.61       4      64600    3995    4001        0    0    0 00:39:32         6400
   10.0.0.63       4      64600    3995    3998        0    0    0 00:39:32         6400

   Total number of neighbors 4

   IPv6 Unicast Summary:
   BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
   BGP table version 12803
   RIB entries 12805, using 2001 KiB of memory
   Peers 4, using 83 KiB of memory
   Peer groups 2, using 128 bytes of memory

   Neighbor        V         AS MsgRcvd MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd
   fc00::72        4      64600    3995    5208        0    0    0 00:39:30         6400
   fc00::76        4      64600    3994    5208        0    0    0 00:39:30         6400
   fc00::7a        4      64600    3993    5208        0    0    0 00:39:30         6400
   fc00::7e        4      64600    3993    5208        0    0    0 00:39:30         6400

   Total number of neighbors 4
  ```
  Click [here](#Quagga-BGP-Show-Commands) to see the example for "show ip bgp summary" for Quagga.



**show bgp neighbors (for default FRR in 201904+ version)**
**show ip bgp neighbors (for Quagga in 201811- version)**


This command displays all the details of IPv4 & IPv6 BGP neighbors when no optional argument is specified.

When the optional argument IPv4_address is specified, it displays the detailed neighbor information about that specific IPv4 neighbor.

Command has got additional optional arguments to display only the advertised routes, or the received routes, or all routes.

In order to get details for an IPv6 neigbor, use "show bgp ipv6 neighbor <ipv6_address>" command.


- Usage:
  show bgp neighbors [\<ipv4-address\> [advertised-routes | received-routes | routes]] (for default FRR in 201904+ version)
  show ip bgp neighbors [\<ipv4-address\> [advertised-routes | received-routes | routes]] (for Quagga in 201811- version)

- Example:
  ```
   admin@sonic:~$ show bgp neighbors
   BGP neighbor is 10.0.0.57, remote AS 64600, local AS 65100, external link
   Description: ARISTA01T1
   BGP version 4, remote router ID 100.1.0.29, local router ID 10.1.0.32
   BGP state = Established, up for 00:42:15
   Last read 00:00:00, Last write 00:00:03
   Hold time is 10, keepalive interval is 3 seconds
   Configured hold time is 10, keepalive interval is 3 seconds
   Neighbor capabilities:
     4 Byte AS: advertised and received
     AddPath:
       IPv4 Unicast: RX advertised IPv4 Unicast and received
     Route refresh: advertised and received(new)
     Address Family IPv4 Unicast: advertised and received
     Hostname Capability: advertised (name: sonic-z9264f-9251,domain name: n/a) not received
     Graceful Restart Capabilty: advertised and received
       Remote Restart timer is 300 seconds
       Address families by peer:
         none
   Graceful restart information:
     End-of-RIB send: IPv4 Unicast
     End-of-RIB received: IPv4 Unicast
   Message statistics:
     Inq depth is 0
     Outq depth is 0
                          Sent       Rcvd
     Opens:                  2          1
     Notifications:          2          0
     Updates:             3206       3202
     Keepalives:           845        847
     Route Refresh:          0          0
     Capability:             0          0
     Total:               4055       4050
   Minimum time between advertisement runs is 0 seconds

  For address family: IPv4 Unicast
   Update group 1, subgroup 1
   Packet Queue length 0
   Inbound soft reconfiguration allowed
   Community attribute sent to this neighbor(all)
   6400 accepted prefixes

   Connections established 1; dropped 0
   Last reset 00:42:37, due to NOTIFICATION sent (Cease/Connection collision resolution)
   Local host: 10.0.0.56, Local port: 179
   Foreign host: 10.0.0.57, Foreign port: 46419
   Nexthop: 10.0.0.56
   Nexthop global: fc00::71
   Nexthop local: fe80::2204:fff:fe36:9449
   BGP connection: shared network
   BGP Connect Retry Timer in Seconds: 120
   Read thread: on  Write thread: on
  ```

- Optionally, you can specify an IP address in order to display only that particular neighbor. In this mode, you can optionally specify whether you want to display all routes advertised to the specified neighbor, all routes received from the specified neighbor or all routes (received and accepted) from the specified neighbor.


- Example:
  ```
    admin@sonic:~$ show bgp neighbors 10.0.0.57

    admin@sonic:~$ show bgp neighbors 10.0.0.57 advertised-routes

    admin@sonic:~$ show bgp neighbors 10.0.0.57 received-routes

    admin@sonic:~$ show bgp neighbors 10.0.0.57 routes

  ```

  Click [here](#Quagga-BGP-Show-Commands) to see the example for "show ip bgp neighbors" for Quagga.



**show bgp ipv6 summary (for default FRR in 201904+ version)**
**show ipv6 bgp summary (for Quagga in 201811- version)**

This command displays the summary of all IPv6 bgp neighbors that are configured and the corresponding states.

- Usage:
  show bgp ipv6 summary (for default FRR in 201904+ version)
  show ipv6 bgp summary (for Quagga in 201811- version)

- Example:
  ```
  admin@sonic:~$ show bgp ipv6 summary
  BGP router identifier 10.1.0.32, local AS number 65100 vrf-id 0
  BGP table version 12803
  RIB entries 12805, using 2001 KiB of memory
  Peers 4, using 83 KiB of memory
  Peer groups 2, using 128 bytes of memory

  Neighbor        V         AS MsgRcvd MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd
  fc00::72        4      64600    3995    5208        0    0    0 00:39:30         6400
  fc00::76        4      64600    3994    5208        0    0    0 00:39:30         6400
  fc00::7a        4      64600    3993    5208        0    0    0 00:39:30         6400
  fc00::7e        4      64600    3993    5208        0    0    0 00:39:30         6400

  Total number of neighbors 4

  ```
  Click [here](#Quagga-BGP-Show-Commands) to see the example for "show ipv6 bgp summary" for Quagga.



**show bgp ipv6 neighbors (for default FRR in 201904+ version)**
**show ipv6 bgp neighbors (for Quagga in 201811- version)**


This command displays all the details of one particular IPv6 Border Gateway Protocol (BGP) neighbor. Option is also available to display only the advertised routes, or the received routes, or all routes.


  - Usage:
    show bgp ipv6 neighbors [\<ipv6-address\> [(advertised-routes | received-routes | routes)]] (for default FRR in 201904+ version)
    show ipv6 bgp neighbors [\<ipv6-address\> [(advertised-routes | received-routes | routes)]] (for Quagga in 201811- version)

- Example:
  ```
   admin@sonic:~$ show bgp ipv6 neighbors fc00::72 advertised-routes

   admin@sonic:~$ show bgp ipv6 neighbors fc00::72 received-routes

   admin@sonic:~$ show bgp ipv6 neighbors fc00::72 routes

  ```
  Click [here](#Quagga-BGP-Show-Commands) to see the example for "show ip bgp summary" for Quagga.



**show route-map**

This command displays the routing policy that takes precedence over the other route processes that are configured.

  - Usage:
    show route-map

  - Example:
  ```
	admin@T1-2:~$ show route-map
	ZEBRA:
	route-map RM_SET_SRC, permit, sequence 10
	  Match clauses:
	  Set clauses:
		src 10.12.0.102
	  Call clause:
	  Action:
		Exit routemap
	ZEBRA:
	route-map RM_SET_SRC6, permit, sequence 10
	  Match clauses:
	  Set clauses:
		src fc00:1::102
	  Call clause:
	  Action:
		Exit routemap
	BGP:
	route-map FROM_BGP_SPEAKER_V4, permit, sequence 10
	  Match clauses:
	  Set clauses:
	  Call clause:
	  Action:
	    Exit routemap
	BGP:
	route-map TO_BGP_SPEAKER_V4, deny, sequence 10
	  Match clauses:
	  Set clauses:
	  Call clause:
	  Action:
	    Exit routemap
	BGP:
	route-map ISOLATE, permit, sequence 10
	  Match clauses:
	  Set clauses:
		as-path prepend 65000
	  Call clause:
	  Action:
		Exit routemap
  ```


## BGP config commands

This sub-section explains the list of configuration options available for BGP module for both IPv4 and IPv6 BGP neighbors.

The list of possible BGP config commands are given below.

	bgp
        shutdown
            all
            neighbor
        startup
            all
            neighbor

**config bgp shut down all**

This command is used to shutdown all the BGP IPv4 & IPv6 sessions.
When the session is shutdown using this command, BGP state in "show ip bgp summary" is displayed as "Idle (Admin)"

  - Usage:
    sudo config bgp shutdown all

- Examples:
  ```
  admin@sonic:~$ sudo config bgp shutdown all
  ```

**config bgp shutdown <neighbor>**

This command is to shut down a BGP session with a neighbor by that neighbor's IP address or hostname

  - Usage:
    sudo config bgp shutdown (<ip-address> | <hostname>)

- Examples:
  ```
  admin@sonic:~$ sudo config bgp shutdown neighbor 192.168.1.124
  ```
  ```
  admin@sonic:~$ sudo config bgp shutdown neighbor SONIC02SPINE
  ```


**config bgp startup all**

This command is used to start up all the IPv4 & IPv6 BGP neighbors

  - Usage:
    sudo config bgp startup all`

- Examples:
  ```
  admin@sonic:~$ sudo config bgp startup all
  ```


**config bgp startup <neighbor>**

This command is used to start up the particular IPv4 or IPv6 BGP neighbor using either the IP address or hostname.

  - Usage:
    sudo config bgp startup (<ip-address> | <hostname>)`

- Examples:
  ```
  admin@sonic:~$ sudo config bgp startup neighbor 192.168.1.124
  ```
  ```
  admin@sonic:~$ sudo config bgp startup neighbor SONIC02SPINE
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#BGP-Configuration-And-Show-Commands)


# ECN Configuration And Show Commands

This section explains all the Explicit Congestion Notification (ECN) show commands and ECN configuation options that are supported in SONiC.

## ECN show commands
This sub-section contains the show commands that are supported in ECN.

**show ecn**

This command displays all the WRED profiles that are configured in the device.

  - Usage:
    show ecn

- Example:
  ```
	show ecn
	Profile: **AZURE_LOSSLESS**
	-----------------------  -------
	red_max_threshold        2097152
	red_drop_probability     5
	yellow_max_threshold     2097152
	ecn                      ecn_all
	green_min_threshold      1048576
	red_min_threshold        1048576
	wred_yellow_enable       true
	yellow_min_threshold     1048576
	green_max_threshold      2097152
	green_drop_probability   5
	wred_green_enable        true
	yellow_drop_probability  5
	wred_red_enable          true
	-----------------------  -------

	Profile: **wredprofileabcd**
	-----------------  ---
	red_max_threshold  100
	-----------------  ---

  ```

## ECN config commands

This sub-section contains the configuration commands that can configure the WRED profiles.

**config ecn**

This command configures the possible fields in a particular WRED profile that is specified using "-profile <profilename>" argument.
The list of the WRED profile fields that are configurable is listed in the below "Usage".

  - Usage:
    config ecn [OPTIONS]

  ```
    ECN Config OPTIONS:
	  -profile <profile_name>       Profile name  [required] - Even though the profile_name is specified as optional parameter, it is a mandatory parameter.
	  -rmax <red threshold max>     Set red max threshold
	  -rmin <red threshold min>     Set red min threshold
	  -ymax <yellow threshold max>  Set yellow max threshold
	  -ymin <yellow threshold min>  Set yellow min threshold
	  -gmax <green threshold max>   Set green max threshold
	  -gmin <green threshold min>   Set green min threshold
	  -v, --verbose                 Enable verbose output
	  --help                        Show this message and exit.
  ```


- Example:
  ```
     root@T1-2:~# config ecn -profile wredprofileabcd -rmax 100
        This command configures the "red max threshold" for the WRED profile name "wredprofileabcd". It will create the WRED profile if it does not exist.
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#ECN-Configuration-And-Show-Commands)

# Interface Configuration And Show-Commands

## Interface Show Commands

This sub-section lists all the possible show commands for the interfaces available in the device. Following example gives the list of possible shows on interfaces.
Subsequent pages explain each of these commands in detail.

- Example:
  ```
  user@debug:~$ show interfaces -?

  Show details of the network interfaces

  Options:
    -?, -h, --help  Show this message and exit.

  Commands:
  counters     Show interface counters
  description  Show interface status, protocol and...
  naming_mode  Show interface naming_mode status
  neighbor     Show neighbor related information
  portchannel  Show PortChannel information
  status       Show Interface status information
  transceiver  Show SFP Transceiver information
  ```

**show interfaces counters**

This show command displays packet counters for all interfaces since the last time the counters were cleared. There is no facility to display counters for one specific interface. Optional argument "-a" does not have any significance in this command.
Optional argument "-c" can be used to clear the counters for all interfaces.
Optional argument "-p" specify a period (in seconds) with which to gather counters over.

  - Usage:
    show interfaces counters [OPTIONS]
      OPTIONS:
      -a, --printall
      -c, --clear
      -p, --period TEXT


- Example:
  ```
  admin@sonic:~$ show interfaces counters
        IFACE    STATE            RX_OK       RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR            TX_OK       TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
  -----------  -------  ---------------  -----------  ---------  --------  --------  --------  ---------------  -----------  ---------  --------  --------  --------
    Ethernet0        U  471,729,839,997  653.87 MB/s     12.77%         0    18,682         0  409,682,385,925  556.84 MB/s     10.88%         0         0         0
    Ethernet4        U  453,838,006,636  632.97 MB/s     12.36%         0     1,636         0  388,299,875,056  529.34 MB/s     10.34%         0         0         0
    Ethernet8        U  549,034,764,539  761.15 MB/s     14.87%         0    18,274         0  457,603,227,659  615.20 MB/s     12.02%         0         0         0
   Ethernet12        U  458,052,204,029  636.84 MB/s     12.44%         0    17,614         0  388,341,776,615  527.37 MB/s     10.30%         0         0         0
   Ethernet16        U   16,679,692,972   13.83 MB/s      0.27%         0    17,605         0   18,206,586,265   17.51 MB/s      0.34%         0         0         0
   Ethernet20        U   47,983,339,172   35.89 MB/s      0.70%         0     2,174         0   58,986,354,359   51.83 MB/s      1.01%         0         0         0
   Ethernet24        U   33,543,533,441   36.59 MB/s      0.71%         0     1,613         0   43,066,076,370   49.92 MB/s      0.97%         0         0         0
  ```

  - Optionally, you can specify a period (in seconds) with which to gather counters over. Note that this function will take `<period>` seconds to execute.

- Example:
  ```
  admin@sonic:~$ show interfaces counters -p 5
        IFACE    STATE    RX_OK       RX_BPS    RX_UTIL    RX_ERR    RX_DRP    RX_OVR    TX_OK       TX_BPS    TX_UTIL    TX_ERR    TX_DRP    TX_OVR
  -----------  -------  -------  -----------  ---------  --------  --------  --------  -------  -----------  ---------  --------  --------  --------
  Ethernet0         U      515   59.14 KB/s      0.00%         0         0         0    1,305  127.60 KB/s      0.00%         0         0         0
  Ethernet4         U      305   26.54 KB/s      0.00%         0         0         0      279   39.12 KB/s      0.00%         0         0         0
  Ethernet8         U      437   42.96 KB/s      0.00%         0         0         0      182   18.37 KB/s      0.00%         0         0         0
  Ethernet12        U      284   40.79 KB/s      0.00%         0         0         0      160   13.03 KB/s      0.00%         0         0         0
  Ethernet16        U      377   32.64 KB/s      0.00%         0         0         0      214   18.01 KB/s      0.00%         0         0         0
  Ethernet20        U      284   36.81 KB/s      0.00%         0         0         0      138  8758.25 B/s      0.00%         0         0         0
  Ethernet24        U      173   16.09 KB/s      0.00%         0         0         0      169   11.39 KB/s      0.00%         0         0         0
  ```


**show interfaces description**

This command displays the key fields of the interfaces such as Operational Status, Administrative Status, Alias and Description.

  - Usage:
    show interfaces description [INTERFACENAME]

- Example:
   ```
  admin@sonic:~$ show interfaces description
  Interface    Oper    Admin            Alias           Description
  -----------  ------  -------  ---------------  --------------------
  Ethernet0    down       up   hundredGigE1/1  T0-1:hundredGigE1/30
  Ethernet4    down       up   hundredGigE1/2  T0-2:hundredGigE1/30
  Ethernet8    down     down   hundredGigE1/3        hundredGigE1/3
  Ethernet12   down     down   hundredGigE1/4        hundredGigE1/4
  ```
  ```
  show the description for one particular interface.

  admin@sonic:~$ show interfaces description Ethernet4
  Interface    Oper    Admin           Alias           Description
  -----------  ------  -------  --------------  --------------------
  Ethernet4    down       up  hundredGigE1/2  T0-2:hundredGigE1/30

  ```


**show interfaces naming_mode**

Refer sub-section [Interface-Naming-Mode](#Interface-Naming-Mode)


**show interfaces neighbor**

This command is used to display the list of expected neighbors for all interfaces (or for a particular interface) that is configured.

  - Usage:
    show interfaces neighbor expected [INTERFACENAME]

- Example:
  ```
  root@sonic-z9264f-9251:~# show interfaces neighbor expected
	LocalPort    Neighbor    NeighborPort    NeighborLoopback    NeighborMgmt    NeighborType
	-----------  ----------  --------------  ------------------  --------------  --------------
	Ethernet112  ARISTA01T1  Ethernet1       None                10.16.205.100   ToRRouter
	Ethernet116  ARISTA02T1  Ethernet1       None                10.16.205.101   SpineRouter
	Ethernet120  ARISTA03T1  Ethernet1       None                10.16.205.102   LeafRouter
	Ethernet124  ARISTA04T1  Ethernet1       None                10.16.205.103   LeafRouter

  ```

**show interfaces portchannel**

This command displays information regarding port-channel interfaces

  - Usage:
    show interfaces portchannel

- Example:
  ```
  admin@sonic:~$ show interfaces portchannel
  Flags: A - active, I - inactive, Up - up, Dw - Down, N/A - not available, S - selected, D - deselected
    No.  Team Dev       Protocol     Ports
  -----  -------------  -----------  ---------------------------
     24  PortChannel24  LACP(A)(Up)  Ethernet28(S) Ethernet24(S)
     48  PortChannel48  LACP(A)(Up)  Ethernet52(S) Ethernet48(S)
     40  PortChannel40  LACP(A)(Up)  Ethernet44(S) Ethernet40(S)
      0  PortChannel0   LACP(A)(Up)  Ethernet0(S) Ethernet4(S)
      8  PortChannel8   LACP(A)(Up)  Ethernet8(S) Ethernet12(S)
  ```

**show interface status**

This command displays some more fields such as Lanes, Speed, MTU, Type, Asymmetric PFC status and also the operational and administrative status of the interfaces

- Usage:
  show interfaces status [INTERFACENAME]

- Example:
  ```
  show interface status of all interfaces

  admin@sonic:~$ show interfaces status
  Interface            Lanes    Speed    MTU            Alias    Oper    Admin    Type    Asym PFC
  -----------  ---------------  -------  -----  ---------------  ------  -------  ------  ----------
  Ethernet0      49,50,51,52     100G   9100   hundredGigE1/1    down       up     N/A         off
  Ethernet4      53,54,55,56     100G   9100   hundredGigE1/2    down       up     N/A         off
  Ethernet8      57,58,59,60     100G   9100   hundredGigE1/3    down     down     N/A         off
  <contiues to display all the interfaces>

  ```

  ```
  show interface status for one particular interface

  admin@sonic:~$ show interface status Ethernet0
  Interface     Lanes    Speed    MTU            Alias    Oper    Admin
  -----------  --------  -------  -----   --------------  ------  -------
  Ethernet0   101,102      40G   9100   fortyGigE1/1/1      up       up

  ```

**show interfaces transceiver**

This command is already explained [here](#Transceivers)

## Interface Config Commands
This sub-section explains the following list of configuration on the interfaces.
1) ip - To add or remove IP address for the interface
2) pfc - to set the PFC configuration for the interface
3) shutdown - to administratively shut down the interface
4) speed - to set the interface speed
5) startup - to bring up the administratively shutdown interface

From 201904 release onwards, the “config interface” command syntax is changed and the format is as follows

- config interface  interface_subcommand <interface_name>
i.e Interface name comes after the subcommand
- Ex: config interface startup Ethernet63

The syntax for all such interface_subcommands are given below under each command

NOTE: In older versions of SONiC until 201811 release, the command syntax was
      "config interface <interface_name> interface_subcommand"

**config interface ip add <interface-name> <ip_addr> (for 201904+ version)**
**config interface <interface-name> ip add <ip_addr> (for 201811- version)**

This command is used for adding the IP address for an interface.
IP address for either physical interface or for portchannel or for VLAN interface can be configured using this command.


- Usage:
    config interface ip add <interface-name> <ip_addr> (for 201904+ version)
    config interface <interface-name> ip add <ip_addr> (for 201811- version)

- Example:
  ```
  admin@sonic:~$ sudo config interface ip add Ethernet63 10.11.12.13/24
  ```
NOTE: In SONiC versions until 201811, syntax was "config <interface_name> ip add <ip_addr>"


**IP Address Configuration for Vlan Interface**
- Usage:
    config interface ip add <ip_addr> <vlan_IDName>

- Example:
  ```
  admin@sonic:~$ sudo config interface ip add vlan100 10.11.12.13/24
  ```
NOTE: In versions until 201811, syntax was "config interface <vlan_IDName> ip add <ip_addr>"



**config interface ip remove <interface_name> <ip_addr> (for 201904+ version)**
**config interface <interface_name> ip remove <ip_addr> (for 201811- version)**

- Usage:
    config interface ip remove <interface_name> <ip_addr> (for 201904+ version)
    config interface ip remove <interface_name> <ip_addr> (for 201811- version)

- Example:
  ```
  admin@sonic:~$ sudo config interface ip remove Ethernet63 10.11.12.13/24
  ```
NOTE: In versions until 201811, syntax is "config  interface <interface_name> ip remove <ip_addr>"



**IP Address Removal for Vlan Interface**
- Usage:
    config interface ip remove <vlan_IDName> <ip_addr>

- Example:
  ```
  admin@sonic:~$ sudo config interface ip remove vlan100 10.11.12.13/24
  ```
NOTE: In versions until 201811, syntax is "config interface <vlan_ID> ip remove <ip_addr>"



**config interface pfc asymmetric <interface_name> (for 201904+ version)**
**config interface <interface_name> pfc asymmetric (for 201811- version)**
This command is used for setting the asymmetric PFC for an interface to either "on" or "off". Once if it is configured, use "show interfaces status" to check the same.

- Usage:
    config interface pfc asymmetric <interface_name> on/off (for 201904+ version)
    config interface <interface_name> pfc asymmetric on/off (for 201811- version)

- Example:
  ```
  admin@sonic:~$ sudo config interface pfc asymmetric Ethernet60 on
  ```

**config interface shutdown <interface_name> (for 201904+ version)**
**config interface <interface_name> shutdown (for 201811- version)**

This command is used to administratively shut down either the Physical interface or port channel interface. Once if it is configured, use "show interfaces status" to check the same.

- Usage:
    config interface shutdown <interface_name> (for 201904+ version)
    config interface <interface_name> shutdown (for 201811- version)

- Example:
  ```
  admin@sonic:~$ sudo config interface shutdown Ethernet63
  ```
NOTE: In versions until 201811, syntax is "config interface <interface_name> shutdown"



**config interface startup <interface_name> (for 201904+ version)**
**config interface <interface_name> startup (for 201811- version)**

This command is used for administratively bringing up the Physical interface or port channel interface.Once if it is configured, use "show interfaces status" to check the same.

- Usage:
    config interface startup <interface_name> (for 201904+ version)
    config interface <interface_name> startup (for 201811- version)

- Example:
  ```
  admin@sonic:~$ sudo config interface startup Ethernet63
  ```
NOTE: In versions until 201811, syntax is "config interface <interface_name> startup"



**config interface speed <interface_name> (for 201904+ version)**
**config interface <interface_name> speed (for 201811- version)**

This command is used to configure the speed for the Physical interface. Use the value 40000 for setting it to 40G and 100000 for 100G. Users need to know the device to configure it properly.
Dynamic breakout feature is yet to be supported in SONiC and hence uses cannot configure any values other than 40G and 100G.

- Usage:
    config interface speed <interface_name> <speed_value>  (for 201904+ version)
    config interface <interface_name> speed <speed_value>  (for 201811- version)

- Example:
  ```
  admin@sonic:~$ sudo config interface speed Ethernet63 40000
  ```

NOTE: In versions until 201811, syntax is "config interface <interface_name> speed <4000>"


Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#interface-configuration-and-show-commands)


# Interface Naming Mode

## Interface naming mode show commands
This command displays the current interface naming mode. Interface naming mode originally set to 'default'. Interfaces are referenced by default SONiC interface names.
Users can change the naming_mode using "config interface_naming_mode" command.

**show interfce naming mode**
This command displays the current interface naming mode

  - Usage:
    show interfaces naming_mode

- Example:
  ```
  admin@sonic:~$ show interfaces naming_mode
  **default**
  - "default" is the name of the default naming_mode since users have not modified it in this example.

  Following example shows the modified interface_naming_mode
  admin@sonic:~$ show interfaces naming_mode
  **alias**
  ```


## Interface naming mode config commands

**config interface naming mode**
This command is used to change the interface naming mode.
Users can select between default mode (SONiC interface names) or alias mode (Hardware vendor names).
The user must log out and log back in for changes to take effect. Note that the newly-applied interface mode will affect all interface-related show/config commands.



NOTE: Some platforms do not support alias mapping. In such cases, this command is not applicable. Such platforms always use the same SONiC interface names.

  - Usage:
    config interface_naming_mode (default | alias)

  - Interface naming mode originally set to 'default'. Interfaces are referenced by default SONiC interface names:

- Example:
  ```
    admin@sonic:~$ show interfaces naming_mode
    default

    admin@sonic:~$ show interface status Ethernet0
      Interface     Lanes    Speed    MTU            Alias    Oper    Admin
    -----------  --------  -------  -----   --------------  ------  -------
      Ethernet0   101,102      40G   9100   fortyGigE1/1/1      up       up

    admin@sonic:~$ sudo config interface_naming_mode alias
    Please logout and log back in for changes take effect.
  ```

    - After user logs out and back in again, interfaces now referenced by hardware vendor aliases:

  ```
    admin@sonic:~$ show interfaces naming_mode
    alias

    admin@sonic:~$ sudo config interface fortyGigE1/1/1 shutdown
    admin@sonic:~$ show interface status fortyGigE1/1/1
      Interface     Lanes    Speed    MTU            Alias    Oper    Admin
    -----------  --------  -------  -----   --------------  ------  -------
      Ethernet0   101,102      40G   9100   fortyGigE1/1/1    down     down
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Interface-Naming-Mode)


# IP

## IP show commands

This sub-section explains the various IP protocol specific show commands that are used to display the following.
1) routes
2) bgp details - Explained in the [bgp section](#show-bgp)
3) IP interfaces
4) prefix-list
5) protocol

**show ip route**

This command displays either all the route entries from the routing table or a specific route.

  - Usage:
    show ip route [\<ip_address\>]


- Example:
  ```
  admin@sonic:~$ show ip route
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, P - PIM, A - Babel,
         > - selected route, * - FIB route
	S>* 0.0.0.0/0 [200/0] via 10.11.162.254, eth0
	C>* 1.1.0.0/16 is directly connected, Vlan100
	C>* 10.1.0.1/32 is directly connected, lo
	C>* 10.1.0.32/32 is directly connected, lo
	C>* 10.1.1.0/31 is directly connected, Ethernet112
	C>* 10.1.1.2/31 is directly connected, Ethernet116
	C>* 10.11.162.0/24 is directly connected, eth0
	C>* 10.12.0.102/32 is directly connected, lo
	C>* 127.0.0.0/8 is directly connected, lo
	C>* 240.127.1.0/24 is directly connected, docker0

  ```
 - Optionally, you can specify an IP address in order to display only routes to that particular IP address

- Example:
  ```
	admin@sonic:~$ show ip route 10.1.1.0
	Routing entry for 10.1.1.0/31
	  Known via "connected", distance 0, metric 0, best
	  * directly connected, Ethernet112
  ```

**show ip interfaces**

This command displays the details about all the Layer3 IP interfaces in the device for which IP address has been assigned.
The type of interfaces include the following.
1) Front panel physical ports.
2) PortChannel.
3) VLAN interface.
4) Loopback interfaces
5) docker interface and
6) management interface

  - Usage:
    show ip interfaces

- Example:
  ```
	admin@sonic:~$ show ip interfaces
	Interface      IPv4 address/mask    Admin/Oper    BGP Neighbor    Neighbor IP
	-------------  -------------------  ------------  --------------  -------------
	PortChannel01  10.0.0.56/31         up/down       DEVICE1         10.0.0.57
	PortChannel02  10.0.0.58/31         up/down       DEVICE2         10.0.0.59
	PortChannel03  10.0.0.60/31         up/down       DEVICE3         10.0.0.61
	PortChannel04  10.0.0.62/31         up/down       DEVICE4         10.0.0.63
	Vlan1000       192.168.0.1/27       up/up         N/A             N/A
	docker0        240.127.1.1/24       up/down       N/A             N/A
	eth0           10.3.147.252/23      up/up         N/A             N/A
	lo             127.0.0.1/8          up/up         N/A             N/A
  ```

**show ip protocol**

This command displays the route-map that is configured for the routing protocol.
Refer the routing stack [Quagga Command Reference](https://www.quagga.net/docs/quagga.pdf) or [FRR Command Reference](https://buildmedia.readthedocs.org/media/pdf/frrouting/latest/frrouting.pdf) to know more about this command.

  - Usage:
    show ip protocol


- Example:
  ```
	show ip protocol
	Protocol    : route-map
	------------------------
	system      : none
	kernel      : none
	connected   : none
	static      : none
	rip         : none
	ripng       : none
	ospf        : none
	ospf6       : none
	isis        : none
	bgp         : RM_SET_SRC
	pim         : none
	hsls        : none
	olsr        : none
	babel       : none
	any         : none
  ```

## IPv6 show commands

This sub-section explains the various IPv6 protocol specific show commands that are used to display the following.
1) routes
2) IPv6 bgp details - Explained in the [bgp section](#show-bgp)
3) IP interfaces
4) protocol

**show ipv6 route**

This command displays either all the IPv6 route entries from the routing table or a specific IPv6 route.

  - Usage:
    show ipv6 route [\<ipv6_address\>]


- Example:
  ```
  admin@sonic:~$ show ipv6 route
	Codes: K - kernel route, C - connected, S - static, R - RIPng,
		   O - OSPFv6, I - IS-IS, B - BGP, A - Babel,
		   > - selected route, * - FIB route

	C>* ::1/128 is directly connected, lo
	C>* 2018:2001::/126 is directly connected, Ethernet112
	C>* 2018:2002::/126 is directly connected, Ethernet116
	C>* fc00:1::32/128 is directly connected, lo
	C>* fc00:1::102/128 is directly connected, lo
	C>* fc00:2::102/128 is directly connected, eth0
	C * fe80::/64 is directly connected, Vlan100
	C * fe80::/64 is directly connected, Ethernet112
	C * fe80::/64 is directly connected, Ethernet116
	C * fe80::/64 is directly connected, Bridge
	C * fe80::/64 is directly connected, PortChannel0011
	C>* fe80::/64 is directly connected, eth0

  ```
 - Optionally, you can specify an IPv6 address in order to display only routes to that particular IPv6 address


- Example:
  ```
	admin@sonic:~$ show ipv6 route  fc00:1::32
	Routing entry for fc00:1::32/128
	  Known via "connected", distance 0, metric 0, best
	  * directly connected, lo
  ```

**show ipv6 interfaces**

This command displays the details about all the Layer3 IPv6 interfaces in the device for which IPv6 address has been assigned.
The type of interfaces include the following.
1) Front panel physical ports.
2) PortChannel.
3) VLAN interface.
4) Loopback interfaces
5) management interface

  - Usage:
    show ipv6 interfaces


- Example:
  ```
	admin@sonic:~$ show ipv6 interfaces
	Interface      IPv6 address/mask                         Admin/Oper    BGP Neighbor    Neighbor IP
	-------------  ----------------------------------------  ------------  --------------  -------------
	Bridge         fe80::7c45:1dff:fe08:cdd%Bridge/64        up/up         N/A             N/A
	PortChannel01  fc00::71/126                              up/down       DEVICE1         fc00::72
	PortChannel02  fc00::75/126                              up/down       DEVICE2         fc00::76
	PortChannel03  fc00::79/126                              up/down       DEVICE3         fc00::7a
	PortChannel04  fc00::7d/126                              up/down       DEVICE4         fc00::7e
	Vlan100        fe80::eef4:bbff:fefe:880a%Vlan100/64      up/up         N/A             N/A
	eth0           fe80::eef4:bbff:fefe:880a%eth0/64         up/up         N/A             N/A
	lo             fc00:1::32/128                            up/up         N/A             N/A
  ```

**show ipv6 protocol**

This command displays the route-map that is configured for the IPv6 routing protocol.
Refer the routing stack [Quagga Command Reference](https://www.quagga.net/docs/quagga.pdf) or [FRR Command Reference](https://buildmedia.readthedocs.org/media/pdf/frrouting/latest/frrouting.pdf) to know more about this command.


  - Usage:
    show ipv6 protocol


- Example:
  ```
	show ipv6 protocol
	Protocol    : route-map
	------------------------
	system      : none
	kernel      : none
	connected   : none
	static      : none
	rip         : none
	ripng       : none
	ospf        : none
	ospf6       : none
	isis        : none
	bgp         : RM_SET_SRC6
	pim         : none
	hsls        : none
	olsr        : none
	babel       : none
	any         : none
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#IP)


# LLDP

## LLDP show commands

**show lldp table**

This command displays the brief summary of all LLDP neighbors.

  - Usage:
    show lldp table


- Example:
  ```
	admin@sonic:~$ show lldp table
	Capability codes: (R) Router, (B) Bridge, (O) Other
	LocalPort    RemoteDevice       RemotePortID         Capability    RemotePortDescr
	-----------  -----------------  -------------------  ------------  --------------------
	Ethernet112  T1-1               hundredGigE1/2       BR            T0-2:hundredGigE1/29
	Ethernet116  T1-2               hundredGigE1/2       BR            T0-2:hundredGigE1/30
	eth0         swtor-b2lab2-1610  GigabitEthernet 0/2  OBR
	--------------------------------------------------
	Total entries displayed:  3
  ```

**show lldp neighbors**

This command displays more details about all LLDP neighbors or only the neighbors connected to a specific interface.

  - Usage:
    show lldp neighbors [INTERFACENAME]


- Example1: To display all neighbors in all interfaces
  ```
	admin@sonic:~$ show lldp neighbors
	-------------------------------------------------------------------------------
	LLDP neighbors:
	-------------------------------------------------------------------------------
	Interface:    eth0, via: LLDP, RID: 1, Time: 0 day, 12:21:21
	  Chassis:
		ChassisID:    mac 00:01:e8:81:e3:45
		SysName:      swtor-b2lab2-1610
		SysDescr:     Dell Force10 Networks Real Time Operating System Software. Dell Force10 Operating System Version: 1.0. Dell Force10 Application Software Version: 8.3.3.10d. Copyright (c) 1999-2012 by Dell Inc. All Rights Reserved.Build Time: Tue Sep 22 11:21:54 PDT 2015
		TTL:          20
		Capability:   Repeater, on
		Capability:   Bridge, on
		Capability:   Router, on
	  Port:
		PortID:       ifname GigabitEthernet 0/2
	  VLAN:         162, pvid: yes
	-------------------------------------------------------------------------------
	Interface:    Ethernet116, via: LLDP, RID: 3, Time: 0 day, 12:20:49
	  Chassis:
		ChassisID:    mac 4c:76:25:e7:f0:c0
		SysName:      T1-2
		SysDescr:     Debian GNU/Linux 8 (jessie) Linux 4.9.0-8-amd64 #1 SMP Debian 4.9.110-3+deb9u6 (2015-12-19) x86_64
		TTL:          120
		MgmtIP:       10.11.162.40
		Capability:   Bridge, on
		Capability:   Router, on
		Capability:   Wlan, off
		Capability:   Station, off
	  Port:
		PortID:       local hundredGigE1/2
		PortDescr:    T0-2:hundredGigE1/30
	-------------------------------------------------------------------------------
  ```


  - Optionally, you can specify an interface name in order to display only that particular interface

- Example2:
  ```
  admin@sonic:~$ show lldp neighbors Ethernet112
	show lldp neighbors Ethernet112
	-------------------------------------------------------------------------------
	LLDP neighbors:
	-------------------------------------------------------------------------------
	Interface:    Ethernet112, via: LLDP, RID: 2, Time: 0 day, 19:24:17
	  Chassis:
		ChassisID:    mac 4c:76:25:e5:e6:c0
		SysName:      T1-1
		SysDescr:     Debian GNU/Linux 8 (jessie) Linux 4.9.0-8-amd64 #1 SMP Debian 4.9.110-3+deb9u6 (2015-12-19) x86_64
		TTL:          120
		MgmtIP:       10.11.162.41
		Capability:   Bridge, on
		Capability:   Router, on
		Capability:   Wlan, off
		Capability:   Station, off
	  Port:
		PortID:       local hundredGigE1/2
		PortDescr:    T0-2:hundredGigE1/29
	-------------------------------------------------------------------------------

  ```
Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#LLDP)


# Loading, Reloading And Saving Configuration

This section explains the commands that are used to load the configuration from either the ConfigDB or from the minigraph.

## Load config command

This command is used to load the configuration from configDB.
This command loads the configuration from the input file (if user specifies this optional filename, it will use that input file. Or else, it will use the /etc/sonic/config_db.json as the input file) into CONFIG_DB.
The configurations present in the input file are applied on top of the already running configuration.
This command does not flush the config DB before loading the new configuration.
i.e. If the configuration present in the input file is same as the current running-configuration, nothing happens.
If the config present in the input file is not present in running-configuration, it will be added.
If the config present in the input file matches (when key matches) with the running-configuration, it will be modified as per the new values for those keys.

When user specifies the optional argument "-y" or "--yes", this command forces the loading without prompting the user for confirmation.
If the argument is not specified, it prompts the user to confirm whether user really wants to load this configuration file.

  - Usage:
    config load [OPTIONS] [FILENAME]
    OPTIONS : -y, --yes

- Example:
   ```
   root@T1-2:~# config load
	Load config from the file /etc/sonic/config_db.json? [y/N]: y
	Running command: /usr/local/bin/sonic-cfggen -j /etc/sonic/config_db.json --write-to-db
	root@T1-2:~#
   ```

## Load_mgmt_config command

This command is used to reconfigure hostname and mgmt interface based on device description file.
This command either uses the optional file specified as arguement or looks for the file "/etc/sonic/device_desc.xml".
If the file does not exist or if the file does not have valid fields for "hostname" and "ManagementAddress", it fails.

When user specifies the optional argument "-y" or "--yes", this command forces the loading without prompting the user for confirmation.
If the argument is not specified, it prompts the user to confirm whether user really wants to load this configuration file.

  - Usage:
    config load_mgmt_config [OPTIONS] [FILENAME]
    OPTIONS : -y, --yes

- Example:
   ```
   root@T1-2:~# config load_mgmt_config
	Reload config from minigraph? [y/N]: y
	Running command: /usr/local/bin/sonic-cfggen -M /etc/sonic/device_desc.xml --write-to-db
	root@T1-2:~#
   ```


## Load_minigraph config command

This command is used to load the configuration from /etc/sonic/minigraph.xml.
When users do not want to use configuration from config_db.json, they can copy the minigraph.xml configuration file to the device and load it using this command.
This command restarts various services running in the device and it takes some time to complete the command.

NOTE: If the user had logged in using SSH, users might get disconnected and some configuration failures might happen which might be hard to recover. Users need to reconnect their SSH sessions after configuring the management IP address. It is recommended to execute this command from console port
NOTE: Management interface IP address and default route (or specific route) may require reconfiguration in case if those parameters are not part of the minigraph.xml.

When user specifies the optional argument "-y" or "--yes", this command forces the loading without prompting the user for confirmation.
If the argument is not specified, it prompts the user to confirm whether user really wants to load this configuration file.

  - Usage:
    config load_minigraph [OPTIONS]
    OPTIONS : -y, --yes

- Example:
   ```
   root@T1-2:~# config load_minigraph
	Reload config from minigraph? [y/N]: y
	Running command: /usr/local/bin/sonic-cfggen -j /etc/sonic/config_db.json --write-to-db
	root@T1-2:~#
   ```

## Reload config command

This command is used to clear current configuration and import new configurationn from the input file or from /etc/sonic/config_db.json.
This command shall stop all services before clearing the configuration and it then restarts those services.

This command restarts various services running in the device and it takes some time to complete the command.
NOTE: If the user had logged in using SSH, users **might get disconnected** depending upon the new management IP address. Users need to reconnect their SSH sessions.
In general, it is recommended to execute this command from console port after disconnecting all SSH sessions to the device.
When users to do “config reload” the newly loaded config may have management IP address, or it may not have management IP address.
If mgmtIP is there in the newly loaded config file, that mgmtIP might be same as previously configured value or it might be different.
This difference in mgmtIP address values results in following possible behaviours.

Case1: Previously configured mgmtIP is same as newly loaded mgmtIP. The SSH session may not be affected at all, but it’s possible that there will be a brief interruption in the SSH session. But, assuming the client’s timeout value isn’t on the order of a couple of seconds, the session would most likely just resume again as soon as the interface is reconfigured and up with the same IP.
Case2: Previously configured mgmtIP is different from newly loaded mgmtIP. Users will lose their SSH connections.
Case3: Newly loaded config does not have any mgmtIP. Users will lose their SSH connections.

NOTE: Management interface IP address and default route (or specific route) may require reconfiguration in case if those parameters are not part of the minigraph.xml.

When user specifies the optional argument "-y" or "--yes", this command forces the loading without prompting the user for confirmation.
If the argument is not specified, it prompts the user to confirm whether user really wants to load this configuration file.

  - Usage:
    config reload [-y|--yes] [-l | --load-sysinfo] [FILENAME]

- Example:
   ```
   root@T1-2:~# config reload
	Clear current config and reload config from the file /etc/sonic/config_db.json? [y/N]: y
	Running command: systemctl stop dhcp_relay
	Running command: systemctl stop swss
	Running command: systemctl stop snmp
	Warning: Stopping snmp.service, but it can still be activated by:
	  snmp.timer
	Running command: systemctl stop lldp
	Running command: systemctl stop pmon
	Running command: systemctl stop bgp
	Running command: systemctl stop teamd
	Running command: /usr/local/bin/sonic-cfggen -H -k Force10-Z9100-C32 --write-to-db
	Running command: /usr/local/bin/sonic-cfggen -j /etc/sonic/config_db.json --write-to-db
	Running command: systemctl restart hostname-config
	Running command: systemctl restart interfaces-config
	Timeout, server 10.11.162.42 not responding.
	root@T1-2:~#
   ```

## Save config  command

This command is to save the config DB configuration into the user-specified filename or into the default /etc/sonic/config_db.json. This saves the configuration into the disk which is available even after reboots.
Saved file can be transferred to remote machines for debugging. If users wants to load the configuration from this new file at any point of time, they can use "config load" command and provide this newly generated file as input. If users wants this newly generated file to be used during reboot, they need to copy this file to /etc/sonic/config_db.json.

  - Usage:
    config save [OPTIONS] [FILENAME]
	OPTIONS : -y, --yes

- Example:
   ```
   root@T1-2:~# config save -y /etc/sonic/config2.json - this saves to the filename specified.
   root@T1-2:~# config save -y - this saves to /etc/sonic/config_db.json.
   ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#loading-reloading-and-saving-configuration)


# Mirroring Configuration And Show

## Mirroring Show command

**show mirror_session**

This command displays all the mirror sessions that are configured.

- Usage:
  show mirror_session


- Example:
  ```
  admin@sonic:~$ show mirror session
  Name       Status    SRC IP     DST IP    GRE    DSCP    TTL    Queue
  ---------  --------  ---------  --------  -----  ------  -----  -------
  everflow0  active    10.1.0.32  10.0.0.7

  ```

## Mirroring Config command

This command is used to add or remove mirroring sessions. Mirror session is identified by "session_name".
While adding a new session, users need to configure the following fields that are used while forwarding the mirrored packets.

1) source IP address,
2) destination IP address,
3) DSCP (QoS) value with which mirrored packets are forwarded
4) TTL value
5) optional - GRE Type in case if user wants to send the packet via GRE tunnel. GRE type could be anything; it could also be left as empty; by default, it is 0x8949 for Mellanox; and 0x88be for the rest of the chips.
6) optional - Queue in which packets shall be sent out of the device. Valid values 0 to 7 for most of the devices. Users need to know their device and the number of queues supported in that device.

  - Usage:
    config mirror_session add <session_name> <src_ip> <dst_ip>
                                 <dscp> <ttl> [gre_type] [queue]

- Example:
  ```
	root@T1-2:~# config mirror_session add mrr_abcd 1.2.3.4 20.21.22.23 8 100 0x6558 0
	root@T1-2:~# show mirror_session
	Name       Status    SRC IP       DST IP       GRE     DSCP    TTL    Queue
	---------  --------  -----------  -----------  ------  ------  -----  -------
	mrr_abcd   inactive  1.2.3.4      20.21.22.23  0x6558  8       100    0
	root@T1-2:~#

  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Mirroring-Configuration-And-Show)


# NTP

## NTP show command

**show ntp**

This command displays a list of NTP peers known to the server as well as a summary of their state.

  - Usage:
    show ntp


- Example:
  ```
  admin@sonic:~$ show ntp
		 remote           refid      st t when poll reach   delay   offset  jitter
	==============================================================================
	 23.92.29.245    .XFAC.          16 u    - 1024    0    0.000    0.000   0.000
	*204.2.134.164   46.233.231.73    2 u  916 1024  377    3.079    0.394   0.128
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#NTP)


# Platform Specific Commands

There are few commands that are platform specific. Mellanox has used this feature and implemented Mellanox specific commands as follows.

**show platform mlnx sniffer**

This command shows the SDK sniffer status

  - Usage:
    show platform mlnx sniffer


- Example:
  ```
  admin@arc-switch1004:~$ show platform mlnx sniffer
  sdk sniffer is disabled
  ```

**show platform mlnx sniffer**

Another show command available on ‘show platform mlnx’ which is the issu status.
This means if ISSU is enabled on this SKU or not. A warm boot command can be executed only when ISSU is enabled on the SKU.

  - Usage:
    show platform mlnx issu


  - Example:
  ```
  admin@arc-switch1004:~$ show platform mlnx issu
  ISSU is enabled
  ```

In the case ISSU is disabled and warm-boot is called, the user will get a notification message explaining that the command cannot be invoked.

Example:
```
admin@arc-switch1038:~$ sudo warm-reboot
ISSU is not enabled on this HWSKU
Warm reboot is not supported
```

**config platform mlnx**
This command is valid only on mellanox devices. The sub-commands for "config platform" gets populated only on mellanox platforms.
There are no other subcommands on non-Mellanox devices and hence this command appears empty and useless in other platforms.
The platform mellanox command currently includes a single sub command which is the SDK sniffer.
The SDK sniffer is a troubleshooting tool which records the RPC calls from the Mellanox SDK user API library to the sx_sdk task into a .pcap file.
This .pcap file can be replayed afterward to get the exact same configuration state on SDK and FW to reproduce and investigate issues.

A new folder will be created to store the sniffer files: "/var/log/mellanox/sniffer/". The result file will be stored in a .pcap file, which includes a time stamp of the starting time in the file name, for example, "sx_sdk_sniffer_20180224081306.pcap"
In order to have a complete .pcap file with all the RPC calls, the user should disable the SDK sniffer. Swss service will be restarted and no capturing is taken place from that moment.
It is recommended to review the .pcap file while sniffing is disabled.
Once SDK sniffer is enabled/disabled, the user is requested to approve that swss service will be restarted.
For example: To change SDK sniffer status, swss service will be restarted, continue? [y/N]:
In order to avoid that confirmation the -y / --yes option should be used.

  - Usage:
    config platform mlnx sniffer sdk [OPTIONS] OPTION
    Options:
    -y, --yes
    --help     Show this message and exit.

  - Example:
  ```
  admin@arc-switch1038:~$ config platform mlnx sniffer sdk
  To change SDK sniffer status, swss service will be restarted, continue? [y/N]: y
  NOTE: In order to avoid that confirmation the -y / --yes option should be used.
  ```

# PortChannel Configuration And Show

## PortChannel Show commands

**show interfaces portchannel**

This command displays all the port channels that are configured in the device and its current status.

  - Usage:
    show interfaces portchannel

- Example:
  ```
  admin@sonic:~$ show interfaces portchannel
  Flags: A - active, I - inactive, Up - up, Dw - Down, N/A - not available, S - selected, D - deselected
    No.  Team Dev       Protocol     Ports
  -----  -------------  -----------  ---------------------------
     24  PortChannel24  LACP(A)(Up)  Ethernet28(S) Ethernet24(S)
     48  PortChannel48  LACP(A)(Up)  Ethernet52(S) Ethernet48(S)
     40  PortChannel40  LACP(A)(Up)  Ethernet44(S) Ethernet40(S)
      0  PortChannel0   LACP(A)(Up)  Ethernet0(S) Ethernet4(S)
      8  PortChannel8   LACP(A)(Up)  Ethernet8(S) Ethernet12(S)
  ```


## PortChannel Config commands

This sub-section explains how to configure the portchannel and its member ports.

**config portchannel add/del <portchannel_name>**

This command is used to add or delete the portchannel.
It is recommended to use portchannel names in the format "PortChannelxxxx", where "xxxx" is number of 1 to 4 digits. Ex: "PortChannel0002".

NOTE: If users specify any other name like "pc99", command will succeed, but such names are not supported. Such names are not printed properly in the "show interface portchannel" command. It is recommended not to use such names.

When any port is already member of any other portchannel and if user tries to add the same port in some other portchannel (without deleting it from the current portchannel), the command fails internally. But, it does not print any error message. In such cases, remove the member from current portchannel and then add it to new portchannel.

Command takes two optional arguements given below.
1) min-links  - minimum number of links required to bring up the portchannel
2) fallback - true/false. LACP fallback feature can be enabled / disabled.  When it is set to true, only one member port will be selected as active per portchannel during fallback mode. Refer https://github.com/Azure/SONiC/blob/master/doc/lag/LACP%20Fallback%20Feature%20for%20SONiC_v0.5.md for more details about fallback feature.

  - Usage:
    config portchannel add/del <portchannel_name> [min-links INTEGER] [fallback true/false]

- Example:
  ```
  admin@sonic:~$ sudo config portchannel add PortChannel0011
  This command will create the portchannel with name "PortChannel0011".
  ```

**config portchannel member add/del <portchannel_name> <member_portname>**

This command is to add or delete a member port into the already created portchannel.

  - Usage:
    config portchannel member add/del <portchannel_name> <member_portname>

- Example:
  ```
  admin@sonic:~$ sudo config portchannel member add PortChannel0011 Ethernet4
  This command will add Ethernet4 as member of the portchannel "PortChannel0011".
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#PortChannel-Configuration-And-Show)

# QoS Configuration & Show

## QoS Show commands

### PFC

**show pfc counters**
This command displays the details of Rx & Tx priority-flow-control (pfc) for all ports. This command can be used to clear the counters using -c option.

  - Usage:
    show pfc counters [-c or --clear]

- Example:
   ```
   admin@sonic:~$ show pfc counters
      Port Rx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
    -----------  ------  ------  ------  ------  ------  ------  ------  ------
    Ethernet0       0       0       0       0       0       0       0       0
    Ethernet4       0       0       0       0       0       0       0       0
    Ethernet8       0       0       0       0       0       0       0       0
   Ethernet12       0       0       0       0       0       0       0       0

      Port Tx    PFC0    PFC1    PFC2    PFC3    PFC4    PFC5    PFC6    PFC7
    -----------  ------  ------  ------  ------  ------  ------  ------  ------
    Ethernet0       0       0       0       0       0       0       0       0
    Ethernet4       0       0       0       0       0       0       0       0
    Ethernet8       0       0       0       0       0       0       0       0
   Ethernet12       0       0       0       0       0       0       0       0
   ```

### Queue And Priority-Group

This sub-section explains the following queue parameters that can be displayed using "show queue" command.
1) queue counters
2) queue watermark
3) priority-group  watermark
4) queue persistent-watermark


**show queue counters**

This command displays packet and byte counters for all queues of all ports or one specific-port given as arguement.
This command can be used to clear the counters for all queues of all ports. Note that port specific clear is not supported.

  - Usage:
    show queue counters [-c or --clear] [<interface-name>]

- Example:
  ```
    This example gives the sample output from two ports Ethernet0 and Ethernet4.

    admin@sonic:~$ show queue counters
         Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
    ---------  -----  --------------  ---------------  -----------  ------------
    Ethernet0    UC0               0                0            0             0
    Ethernet0    UC1               0                0            0             0
    Ethernet0    UC2               0                0            0             0
    Ethernet0    UC3               0                0            0             0
    Ethernet0    UC4               0                0            0             0
    Ethernet0    UC5               0                0            0             0
    Ethernet0    UC6               0                0            0             0
    Ethernet0    UC7               0                0            0             0
    Ethernet0    UC8               0                0            0             0
    Ethernet0    UC9               0                0            0             0
    Ethernet0    MC0               0                0            0             0
    Ethernet0    MC1               0                0            0             0
    Ethernet0    MC2               0                0            0             0
    Ethernet0    MC3               0                0            0             0
    Ethernet0    MC4               0                0            0             0
    Ethernet0    MC5               0                0            0             0
    Ethernet0    MC6               0                0            0             0
    Ethernet0    MC7               0                0            0             0
    Ethernet0    MC8               0                0            0             0
    Ethernet0    MC9               0                0            0             0

         Port    TxQ    Counter/pkts    Counter/bytes    Drop/pkts    Drop/bytes
    ---------  -----  --------------  ---------------  -----------  ------------
    Ethernet4    UC0               0                0            0             0
    Ethernet4    UC1               0                0            0             0
    Ethernet4    UC2               0                0            0             0
    Ethernet4    UC3               0                0            0             0
    Ethernet4    UC4               0                0            0             0
    Ethernet4    UC5               0                0            0             0
    Ethernet4    UC6               0                0            0             0
    Ethernet4    UC7               0                0            0             0
    Ethernet4    UC8               0                0            0             0
    Ethernet4    UC9               0                0            0             0
    Ethernet4    MC0               0                0            0             0
    Ethernet4    MC1               0                0            0             0
    Ethernet4    MC2               0                0            0             0
    Ethernet4    MC3               0                0            0             0
    Ethernet4    MC4               0                0            0             0
    Ethernet4    MC5               0                0            0             0
    Ethernet4    MC6               0                0            0             0
    Ethernet4    MC7               0                0            0             0
    Ethernet4    MC8               0                0            0             0
    Ethernet4    MC9               0                0            0             0
  ```
  - Optionally, you can specify an interface name in order to display only that particular interface

- Example:
  ```
  admin@sonic:~$ show queue counters Ethernet72
  ```

**show queue watermark**

This command displays the user watermark for the queues (Egress shared pool occupancy per queue) for either the unicast queues or multicast queues for all ports

  - Usage:
    show queue watermark <multicast|unicast>

- Example:
  ```
  admin@sonic:~$ show queue  watermark unicast
  Egress shared pool occupancy per unicast queue:
         Port    UC0    UC1    UC2    UC3    UC4    UC5    UC6    UC7
  -----------  -----  -----  -----  -----  -----  -----  -----  -----
    Ethernet0      0      0      0      0      0      0      0      0
    Ethernet4      0      0      0      0      0      0      0      0
    Ethernet8      0      0      0      0      0      0      0      0
    Ethernet12     0      0      0      0      0      0      0      0

  admin@sonic:~$ show queue  watermark multicast (Egress shared pool occupancy per multicast queue)

  ```

**show priority-group watermark|persistent-watermark**
This command displays the user watermark or persistent-watermark for the Ingress "headroom" or "shared pool occupancy" per priority-group for  all ports

  - Usage:
    show priority-group <watermark|persistent-watermark> <headroom|shared>

- Example:
  ```
  admin@sonic:~$ show priority-group  watermark shared
  Ingress shared pool occupancy per PG:
         Port    PG0    PG1    PG2    PG3    PG4    PG5    PG6    PG7
  -----------  -----  -----  -----  -----  -----  -----  -----  -----
    Ethernet0      0      0      0      0      0      0      0      0
    Ethernet4      0      0      0      0      0      0      0      0
    Ethernet8      0      0      0      0      0      0      0      0
    Ethernet12     0      0      0      0      0      0      0      0

  admin@sonic:~$ show priority-group watermark headroom	(Ingress headroom per PG)
  admin@sonic:~$ show priority-group persistent-watermark shared (Ingress shared pool occupancy per PG)
  admin@sonic:~$ show priority-group persistent-watermark headroom (Ingress headroom per PG)
  ```

In addition to user watermark("show queue|priority-group watermark ..."), a persistent watermark is available.
It hold values independently of user watermark. This way user can use "user watermark" for debugging, clear it, etc, but the "persistent watermark" will not be affected.

**show queue persistent-watermark**
This command displays the user persistet-watermark for the queues (Egress shared pool occupancy per queue) for either the unicast queues or multicast queues for all ports
  - Usage:
    show queue persistent-watermark <unicast|multicast>

- Example:
  ```
  admin@sonic:~$ show queue persistent-watermark unicast
  Egress shared pool occupancy per unicast queue:
         Port    UC0    UC1    UC2    UC3    UC4    UC5    UC6    UC7
  -----------  -----  -----  -----  -----  -----  -----  -----  -----
    Ethernet0    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A
    Ethernet4    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A
    Ethernet8    N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A
    Ethernet12   N/A    N/A    N/A    N/A    N/A    N/A    N/A    N/A

  admin@sonic:~$ show queue persistent-watermark multicast (Egress shared pool occupancy per multicast queue)

  ```

  Both "user watermark" and "persistent watermark" can be cleared by user:
  ```
  root@sonic:~# sonic-clear queue persistent-watermark unicast

  root@sonic:~# sonic-clear queue persistent-watermark multicast

  root@sonic:~# sonic-clear priority-group persistent-watermark shared

  root@sonic:~# sonic-clear priority-group persistent-watermark headroom
  ```


## QoS config commands

**config qos clear**

This command is used to clear all the QoS configuration from all the following QOS Tables in ConfigDB.

1) TC_TO_PRIORITY_GROUP_MAP,
2) MAP_PFC_PRIORITY_TO_QUEUE,
3) TC_TO_QUEUE_MAP,
4) DSCP_TO_TC_MAP,
5) SCHEDULER,
6) PFC_PRIORITY_TO_PRIORITY_GROUP_MAP,
7) PORT_QOS_MAP,
8) WRED_PROFILE,
9) QUEUE,
10) CABLE_LENGTH,
11) BUFFER_POOL,
12) BUFFER_PROFILE,
13) BUFFER_PG,
14) BUFFER_QUEUE

   - Usage:
     config qos clear

- Example:
  ```
  admin@sonic:~$ sudo config qos clear

  ```

**config qos reload**

This command is used to reload the QoS configuration.
QoS configuration has got two sets of configurations.
1) Generic QOS Configuration - This gives complete list of all possible QOS configuration. Its given in the file /usr/share/sonic/templates/qos_config.j2 in the device.
   Reference: https://github.com/Azure/sonic-buildimage/blob/master/files/build_templates/qos_config.j2
   Users have flexibility to have platform specific qos configuration by placing the qos_config.j2 file at /usr/share/sonic/device/<platform>/<hwsku>/.
   If users want to modify any of this loaded QOS configuration, they can modify this file in the device and then issue the "config qos reload" command.

2) Platform specific buffer configuration. Every platform has got platform specific and topology specific (T0 or T1 or T2) buffer configuration at /usr/share/sonic/device/<platform>/<hwsku>/buffers_defaults_tx.j2
   In addition to platform specific configuration file, a generic configuration file is also present at /usr/share/sonic/templates/buffers_config.j2.
   Reference: https://github.com/Azure/sonic-buildimage/blob/master/files/build_templates/buffers_config.j2
   Users can either modify the platform specific configuration file, or the generic configuration file and then issue this "config qos reload" command.

These configuration files are already loaded in the device as part of the reboot process. In case if users wants to modify any of these configurations, they need to modify the appropriate QOS tables and fields in these files and then use this reload command.
This command uses those modified buffers.json.j2 file & qos.json.j2 file and reloads the new QOS configuration.
If users have not made any changes in these configuration files, this command need not be executed.

Some of the example QOS configurations that users can modify are given below.
1) TC_TO_PRIORITY_GROUP_MAP
2) MAP_PFC_PRIORITY_TO_QUEUE
3) TC_TO_QUEUE_MAP
4) DSCP_TO_TC_MAP
5) SCHEDULER
6) PFC_PRIORITY_TO_PRIORITY_GROUP_MAP
7) PORT_QOS_MAP
8) WRED_PROFILE
9) CABLE_LENGTH
10) BUFFER_QUEUE

   - Usage:
     config qos reload

- Example:
  ```
	root@T1-2:~# config qos reload
	Running command: /usr/local/bin/sonic-cfggen -d -t /usr/share/sonic/device/x86_64-dell_z9100_c2538-r0/Force10-Z9100-C32/buffers.json.j2 >/tmp/buffers.json
	Running command: /usr/local/bin/sonic-cfggen -d -t /usr/share/sonic/device/x86_64-dell_z9100_c2538-r0/Force10-Z9100-C32/qos.json.j2 -y /etc/sonic/sonic_version.yml >/tmp/qos.json
	Running command: /usr/local/bin/sonic-cfggen -j /tmp/buffers.json --write-to-db
	Running command: /usr/local/bin/sonic-cfggen -j /tmp/qos.json --write-to-db
	root@T1-2:~#
	In this example, it uses the buffers.json.j2 file and qos.json.j2 file from platform specific folders.
	When there are no changes in the platform specific configutation files, they internally use the file "/usr/share/sonic/templates/buffers_config.j2" and "/usr/share/sonic/templates/qos_config.j2" to generate the configuration.
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#QoS-Configuration-And-Show)


# Startup & Running Configuration

## Startup Configuration command

**show startupconfiguration bgp**

This command is used to display the startup configuration for the BGP module.

  - Usage:
    show startupconfiguration bgp`


- Example:
  ```
	admin@sonic:~$ show startupconfiguration bgp
	Routing-Stack is: quagga
	!
	! =========== Managed by sonic-cfggen DO NOT edit manually! ====================
	! generated by templates/quagga/bgpd.conf.j2 with config DB data
	! file: bgpd.conf
	!
	!
	hostname T1-2
	password zebra
	log syslog informational
	log facility local4
	! enable password !
	!
	! bgp multiple-instance
	!
	route-map FROM_BGP_SPEAKER_V4 permit 10
	!
	route-map TO_BGP_SPEAKER_V4 deny 10
	!
	router bgp 65000
	  bgp log-neighbor-changes
	  bgp bestpath as-path multipath-relax
	  no bgp default ipv4-unicast
	  bgp graceful-restart restart-time 180

	  <Only the partial output is shown here. In actual command, more configuration information will be displayed>
  ```

## Running Configuration command
This sub-section explains the show commands for displaying the running configuration for the following modules.
1) bgp
2) interfaces
3) ntp
4) snmp
5) all
6) acl
7) ports
8) syslog

**show runningconfiguration all**

This command displays the entire running configuration.

  - Usage:
    show runningconfiguration all


- Example:
  ```
  admin@sonic:~$ show runningconfiguration all
  ```

**show runningconfiguration bgp**

This command displays the running configuration of the BGP module.

  - Usage:
    show runningconfiguration bgp


- Example:
  ```
  admin@sonic:~$ show runningconfiguration bgp
  ```

**show runningconfiguration interfaces**

This command displays the running configuration for the "interfaces".

  - Usage:
    show runningconfiguration interfaces


- Example:
  ```
  admin@sonic:~$ show runningconfiguration interfaces
  ```

**show runningconfiguration ntp**

This command displays the running configuration of the ntp module.

  - Usage:
    show runningconfiguration ntp


- Example:
  ```
  admin@str-s6000-acs-11:~$ show runningconfiguration ntp
  NTP Servers
  -------------
  1.1.1.1
  2.2.2.2
  ```

**show runningconfiguration syslog**

This command displays the running configuration of the syslog module. 

  - Usage:
    show runningconfiguration syslog


- Example:
  ```
  admin@str-s6000-acs-11:~$ show runningconfiguration syslog 
  Syslog Servers
  ----------------
  4.4.4.4
  5.5.5.5
  ```


**show runningconfiguration snmp**

This command displays the running configuration of the snmp module.

  - Usage:
    show runningconfiguration snmp


- Example:
  ```
  admin@sonic:~$ show runningconfiguration snmp
  ```

**show runningconfiguration acl**

 This command displays the running configuration of the acls

   - Usage:
    show runningconfiguration acl


 - Example:
  ```
  admin@sonic:~$ show runningconfiguration acl
  ```

 **show runningconfiguration ports <portname>**

 This command displays the running configuration of the ports

   - Usage:
    show runningconfiguration ports <portname>


 - Example:
  ```
  admin@sonic:~$ show runningconfiguration ports
  ```

   ```
  admin@sonic:~$ show runningconfiguration ports <portname>
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Startup--Running-Configuration)



# System State

## Processes show commands

This command is used to determine the CPU utilization. It also lists the active processes along with their corresponding process ID and other relevant parameters.

This sub-section explains the various "processes" specific data that includes the following.
1) cpu      Show processes CPU info
2) memory   Show processes memory info
3) summary  Show processes info

“show processes” commands provide a wrapper over linux’s “top” command. “show process cpu” sorts the processes being displayed by cpu-utilization, whereas “show process memory” does it attending to processes’ memory-utilization.

**show processes cpu**

This command displays the current CPU usage by process. This command uses linux's "top -bn 1 -o %CPU" command to display the output.

  - Usage:
    show processes cpu

	NOTE that pipe option can be used using " | head -n" to display only the "n" number of lines.


- Example:
  ```
  admin@SONiC:~$ show processes cpu
  top - 23:50:08 up  1:18,  1 user,  load average: 0.25, 0.29, 0.25
  Tasks: 161 total,   1 running, 160 sleeping,   0 stopped,   0 zombie
  %Cpu(s):  3.8 us,  1.0 sy,  0.0 ni, 95.1 id,  0.1 wa,  0.0 hi,  0.0 si,  0.0 st
  KiB Mem:   8181216 total,  1161060 used,  7020156 free,   105656 buffers
  KiB Swap:        0 total,        0 used,        0 free.   557560 cached Mem

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
   2047 root      20   0  683772 109288  39652 S  23.8  1.3   7:44.79 syncd
   1351 root      20   0   43360   5616   2844 S  11.9  0.1   1:41.56 redis-server
  10093 root      20   0   21944   2476   2088 R   5.9  0.0   0:00.03 top
      1 root      20   0   28992   5508   3236 S   0.0  0.1   0:06.42 systemd
      2 root      20   0       0      0      0 S   0.0  0.0   0:00.00 kthreadd
      3 root      20   0       0      0      0 S   0.0  0.0   0:00.56 ksoftirqd/0
      5 root       0 -20       0      0      0 S   0.0  0.0   0:00.00 kworker/0:0H
  ```

**show processes memory**

This command displays the current memory usage by processes. This command uses linux's "top -bn 1 -o %MEM" command to display the output.

  - Usage:
    show processes memory

	NOTE that pipe option can be used using " | head -n" to display only the "n" number of lines.


- Example:
  ```
	admin@SONiC:~$  show processes memory
	top - 23:41:24 up 7 days, 39 min,  2 users,  load average: 1.21, 1.19, 1.18
	Tasks: 191 total,   2 running, 189 sleeping,   0 stopped,   0 zombie
	%Cpu(s):  2.8 us, 20.7 sy,  0.0 ni, 76.3 id,  0.0 wa,  0.0 hi,  0.2 si,  0.0 st
	KiB Mem :  8162264 total,  5720412 free,   945516 used,  1496336 buff/cache
	KiB Swap:        0 total,        0 free,        0 used.  6855632 avail Mem

	  PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
	18051 root      20   0  851540 274784   8344 S   0.0  3.4   0:02.77 syncd
	17760 root      20   0 1293428 259212  58732 S   5.9  3.2  96:46.22 syncd
	  508 root      20   0  725364  76244  38220 S   0.0  0.9   4:54.49 dockerd
	30853 root      20   0   96348  56824   7880 S   0.0  0.7   0:00.98 show
	17266 root      20   0  509876  49772  30640 S   0.0  0.6   0:06.36 docker
	24891 admin     20   0  515864  49560  30644 S   0.0  0.6   0:05.54 docker
	17643 admin     20   0  575668  49428  30628 S   0.0  0.6   0:06.29 docker
	23885 admin     20   0  369552  49344  30840 S   0.0  0.6   0:05.57 docker
	18055 root      20   0  509076  49260  30296 S   0.0  0.6   0:06.36 docker
	17268 root      20   0  371120  49052  30372 S   0.0  0.6   0:06.45 docker
	 1227 root      20   0  443284  48640  30100 S   0.0  0.6   0:41.91 docker
	23785 admin     20   0  443796  48552  30128 S   0.0  0.6   0:05.58 docker
	17820 admin     20   0  435088  48144  29480 S   0.0  0.6   0:06.33 docker
	  506 root      20   0 1151040  43140  23964 S   0.0  0.5   8:51.08 containerd
	18437 root      20   0   84852  26388   7380 S   0.0  0.3  65:59.76 python3.6
  ```


**show processes summary**

This command displays the current summary information about all the processes

  - Usage:
    show processes summary


- Example:
  ```
	admin@SONiC:~$  show processes summary
	  PID  PPID CMD                         %MEM %CPU
		1     0 /sbin/init                   0.0  0.0
		2     0 [kthreadd]                   0.0  0.0
		3     2 [ksoftirqd/0]                0.0  0.0
		5     2 [kworker/0:0H]               0.0  0.0
  ```


## Services & memory show commands

These commands are used to know the services that are running and the memory that is utilized currently.


**show services**

This command displays the state of all the SONiC processes running inside a docker container. This helps to identify the status of SONiC’s critical processes.

  - Usage:
    sonic_installer remove <image_name>


- Example:
  ```
	admin@lnos-x1-a-asw02:~$ show services
	dhcp_relay      docker
	---------------------------
	UID        PID  PPID  C STIME TTY          TIME CMD
	root         1     0  0 05:26 ?        00:00:12 /usr/bin/python /usr/bin/supervi
	root        24     1  0 05:26 ?        00:00:00 /usr/sbin/rsyslogd -n

	snmp    docker
	---------------------------
	UID        PID  PPID  C STIME TTY          TIME CMD
	root         1     0  0 05:26 ?        00:00:16 /usr/bin/python /usr/bin/supervi
	root        24     1  0 05:26 ?        00:00:02 /usr/sbin/rsyslogd -n
	Debian-+    29     1  0 05:26 ?        00:00:04 /usr/sbin/snmpd -f -LS4d -u Debi
	root        31     1  1 05:26 ?        00:15:10 python3.6 -m sonic_ax_impl

	syncd   docker
	---------------------------
	UID        PID  PPID  C STIME TTY          TIME CMD
	root         1     0  0 05:26 ?        00:00:13 /usr/bin/python /usr/bin/supervi
	root        12     1  0 05:26 ?        00:00:00 /usr/sbin/rsyslogd -n
	root        17     1  0 05:26 ?        00:00:00 /usr/bin/dsserve /usr/bin/syncd
	root        27    17 22 05:26 ?        04:09:30 /usr/bin/syncd --diag -p /usr/sh
	root        51    27  0 05:26 ?        00:00:01 /usr/bin/syncd --diag -p /usr/sh

	swss    docker
	---------------------------
	UID        PID  PPID  C STIME TTY          TIME CMD
	root         1     0  0 05:26 ?        00:00:29 /usr/bin/python /usr/bin/supervi
	root        25     1  0 05:26 ?        00:00:00 /usr/sbin/rsyslogd -n
	root        30     1  0 05:26 ?        00:00:13 /usr/bin/orchagent -d /var/log/s
	root        42     1  1 05:26 ?        00:12:40 /usr/bin/portsyncd -p /usr/share
	root        45     1  0 05:26 ?        00:00:00 /usr/bin/intfsyncd
	root        48     1  0 05:26 ?        00:00:03 /usr/bin/neighsyncd
	root        59     1  0 05:26 ?        00:00:01 /usr/bin/vlanmgrd
	root        92     1  0 05:26 ?        00:00:01 /usr/bin/intfmgrd
	root      3606     1  0 23:36 ?        00:00:00 bash -c /usr/bin/arp_update; sle
	root      3621  3606  0 23:36 ?        00:00:00 sleep 300
  ```

**show system-memory**

This command displays the system-wide memory utilization information – just a wrapper over linux native “free” command

  - Usage:
    show system-memory


- Example:
  ```
	admin@lnos-x1-a-asw02:~$ show system-memory
	Command: free -m -h
				 total       used       free     shared    buffers     cached
	Mem:          3.9G       2.0G       1.8G        33M       324M       791M
	-/+ buffers/cache:       951M       2.9G
	Swap:           0B         0B         0B
  ```

**show mmu**

This command displays virtual address to the physical address translation status of the Memory Management Unit (MMU).

  - Usage:
    show mmu


- Example:
  ```
	admin@T1-2:~$ show mmu
	Pool: ingress_lossless_pool
	----  --------
	xoff  4194112
	type  ingress
	mode  dynamic
	size  10875072
	----  --------

	Pool: egress_lossless_pool
	----  --------
	type  egress
	mode  static
	size  15982720
	----  --------

	Pool: egress_lossy_pool
	----  -------
	type  egress
	mode  dynamic
	size  9243812
	----  -------

	Profile: egress_lossy_profile
	----------  -------------------------------
	dynamic_th  3
	pool        [BUFFER_POOL|egress_lossy_pool]
	size        1518
	----------  -------------------------------

	Profile: pg_lossless_100000_300m_profile
	----------  -----------------------------------
	xon_offset  2288
	dynamic_th  -3
	xon         2288
	xoff        268736
	pool        [BUFFER_POOL|ingress_lossless_pool]
	size        1248
	----------  -----------------------------------

	Profile: egress_lossless_profile
	---------  ----------------------------------
	static_th  3995680
	pool       [BUFFER_POOL|egress_lossless_pool]
	size       1518
	---------  ----------------------------------

	Profile: pg_lossless_100000_40m_profile
	----------  -----------------------------------
	xon_offset  2288
	dynamic_th  -3
	xon         2288
	xoff        177632
	pool        [BUFFER_POOL|ingress_lossless_pool]
	size        1248
	----------  -----------------------------------

	Profile: ingress_lossy_profile
	----------  -----------------------------------
	dynamic_th  3
	pool        [BUFFER_POOL|ingress_lossless_pool]
	size        0
	----------  -----------------------------------

	Profile: pg_lossless_40000_40m_profile
	----------  -----------------------------------
	xon_offset  2288
	dynamic_th  -3
	xon         2288
	xoff        71552
	pool        [BUFFER_POOL|ingress_lossless_pool]
	size        1248
	----------  -----------------------------------
   ```

**show line**

This command displays serial port or a virtual network connection status.
This command is used only when SONiC is used as console switch.
This command is not applicable when SONiC used as regular switch.
NOTE: This command is not working. It crashes as follows. A bug ticket is opened for this issue.

  - Usage:
    show line

- Example:

  ```
  admin@T1-2:~$ show line

  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#System-State)


# VLAN &amp; FDB

## VLAN

### VLAN show commands

**show vlan brief**

This command displays brief information about all the vlans configured in the device. It displays the vlan ID, IP address (if configured for the vlan), list of vlan member ports, whether the port is tagged or in untagged mode and the DHCP Helper Address.

  - Usage:
    show vlan brief


- Example:
  ```
  admin@sonic:~$ show vlan brief

	+-----------+--------------+-----------+----------------+-----------------------+
	|   VLAN ID | IP Address   | Ports     | Port Tagging   | DHCP Helper Address   |
	+===========+==============+===========+================+=======================+
	|       100 | 1.1.2.2/16   | Ethernet0 | tagged         | 192.0.0.1             |
	|           |              | Ethernet4 | tagged         | 192.0.0.2             |
	|           |              |           |                | 192.0.0.3             |
	+-----------+--------------+-----------+----------------+-----------------------+

  ```

**show vlan config**

This command displays all the vlan configuration.

  - Usage:
    show vlan config


- Example:
  ```
  admin@sonic:~$ show vlan config
	Name       VID  Member     Mode
	-------  -----  ---------  ------
	Vlan100    100  Ethernet0  tagged
	Vlan100    100  Ethernet4  tagged

  ```


### VLAN Config commands

This sub-section explains how to configure the vlan and its member ports.

**config vlan add/del**

This command is used to add or delete the vlan.

  - Usage:
    config vlan add/del <vlan__id>


- Example:
  ```
  admin@sonic:~$ sudo config vlan add 100
  This command will create the vlan 100 if not exists.
  ```

**config vlan member add/del**

This command is to add or delete a member port into the already created vlan.

  - Usage:
    config vlan member add/del [-u or --untagged] <vlan_id> <member_portname>
    -u will set the port in untagged mode.


- Example:
  ```
  admin@sonic:~$ sudo config vlan member add 100 Ethernet0
  This command will add Ethernet0 as member of the vlan 100

  admin@sonic:~$ sudo config vlan member add 100 Ethernet4
  This command will add Ethernet4 as member of the vlan 100.
  ```

## FDB

### FDB show commands

**show mac**

This command displays the MAC (FDB) entries either in full or partial as given below.
1) show mac - displays the full table
2) show mac -v <vlanid> - displays the MACs learnt on the particular VLAN ID.
3) show mac -p <port>  - displays the MACs learnt on the particular port.


  - Usage:
    show mac [-v vlan_id] [-p port_name]


- Example:
  ```
  admin@sonic:~$ show mac
  No.    Vlan  MacAddress         Port
  -----  ------  -----------------  -----------
    1    1000  E2:8C:56:85:4A:CD  Ethernet192
    2    1000  A0:1B:5E:47:C9:76  Ethernet192
    3    1000  AA:54:EF:2C:EE:30  Ethernet192
    4    1000  A4:3F:F2:17:A3:FC  Ethernet192
    5    1000  0C:FC:01:72:29:91  Ethernet192
    6    1000  48:6D:01:7E:C9:FD  Ethernet192
    7    1000  1C:6B:7E:34:5F:A6  Ethernet192
    8    1000  EE:81:D9:7B:93:A9  Ethernet192
    9    1000  CC:F8:8D:BB:85:E2  Ethernet192
   10    1000  0A:52:B3:9C:FB:6C  Ethernet192
   11    1000  C6:E2:72:02:D1:23  Ethernet192
   12    1000  8A:C9:5C:25:E9:28  Ethernet192
   13    1000  5E:CD:34:E4:94:18  Ethernet192
   14    1000  7E:49:1F:B5:91:B5  Ethernet192
   15    1000  AE:DD:67:F3:09:5A  Ethernet192
   16    1000  DC:2F:D1:08:4B:DE  Ethernet192
   17    1000  50:96:23:AD:F1:65  Ethernet192
   18    1000  C6:C9:5E:AE:24:42  Ethernet192
  Total number of entries 18
  ```

  - Optionally, you can specify a VLAN ID or interface name in order to display only that particular entries

- Example:
  ```
  admin@sonic:~$ show mac -v 1000
  No.    Vlan  MacAddress         Port
  -----  ------  -----------------  -----------
    1    1000  E2:8C:56:85:4A:CD  Ethernet192
    2    1000  A0:1B:5E:47:C9:76  Ethernet192
    3    1000  AA:54:EF:2C:EE:30  Ethernet192
    4    1000  A4:3F:F2:17:A3:FC  Ethernet192
    5    1000  0C:FC:01:72:29:91  Ethernet192
    6    1000  48:6D:01:7E:C9:FD  Ethernet192
    7    1000  1C:6B:7E:34:5F:A6  Ethernet192
    8    1000  EE:81:D9:7B:93:A9  Ethernet192
    9    1000  CC:F8:8D:BB:85:E2  Ethernet192
   10    1000  0A:52:B3:9C:FB:6C  Ethernet192
   11    1000  C6:E2:72:02:D1:23  Ethernet192
   12    1000  8A:C9:5C:25:E9:28  Ethernet192
   13    1000  5E:CD:34:E4:94:18  Ethernet192
   14    1000  7E:49:1F:B5:91:B5  Ethernet192
   15    1000  AE:DD:67:F3:09:5A  Ethernet192
   16    1000  DC:2F:D1:08:4B:DE  Ethernet192
   17    1000  50:96:23:AD:F1:65  Ethernet192
   18    1000  C6:C9:5E:AE:24:42  Ethernet192
  Total number of entries 18

  admin@sonic:~$ show mac -p Ethernet192
  No.    Vlan  MacAddress         Port
  -----  ------  -----------------  -----------
    1    1000  E2:8C:56:85:4A:CD  Ethernet192
    2    1000  A0:1B:5E:47:C9:76  Ethernet192
    3    1000  AA:54:EF:2C:EE:30  Ethernet192
    4    1000  A4:3F:F2:17:A3:FC  Ethernet192
    5    1000  0C:FC:01:72:29:91  Ethernet192
    6    1000  48:6D:01:7E:C9:FD  Ethernet192
    7    1000  1C:6B:7E:34:5F:A6  Ethernet192
    8    1000  EE:81:D9:7B:93:A9  Ethernet192
    9    1000  CC:F8:8D:BB:85:E2  Ethernet192
   10    1000  0A:52:B3:9C:FB:6C  Ethernet192
   11    1000  C6:E2:72:02:D1:23  Ethernet192
   12    1000  8A:C9:5C:25:E9:28  Ethernet192
   13    1000  5E:CD:34:E4:94:18  Ethernet192
   14    1000  7E:49:1F:B5:91:B5  Ethernet192
   15    1000  AE:DD:67:F3:09:5A  Ethernet192
   16    1000  DC:2F:D1:08:4B:DE  Ethernet192
   17    1000  50:96:23:AD:F1:65  Ethernet192
   18    1000  C6:C9:5E:AE:24:42  Ethernet192
  Total number of entries 18
  ```

- `sonic-clear fdb [OPTIONS]`
  - Clear FDB table


- Example:
  ```
  admin@sonic:~$ sonic-clear fdb all
  FDB entries are cleared.
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#vlan--FDB)



# Warm Restart

## Warm Restart show command

**show warm_restart config**

This command displays all the configuration related to warm_restart.

  - Usage:
    show warm_restart config


- Example:
  ```
	admin@sonic:~$ show warm_restart config
	name    enable    timer_name        timer_duration
	------  --------  ----------------  ----------------
	bgp     true      bgp_timer         100
	teamd   false     teamsyncd_timer   300
	swss    false     neighsyncd_timer  200
	system  true      NULL              NULL
  ```

**show warm_restart state**

This command displays the warm_restart state.

  - Usage:
    show warm_restart state


- Example:
  ```
	name          restore_count  state
	----------  ---------------  ----------
	orchagent                 0
	vlanmgrd                  0
	bgp                       1  reconciled
	portsyncd                 0
	teammgrd                  1
	neighsyncd                0
	teamsyncd                 1
	syncd                     0

  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#VLAN-Configuration-And-Show)

## Warm Restart Config command

This sub-section explains the various configuration related to warm restart feature. Following parameters can be configured using this command.
1) bgp_timer
2) disable
3) enable
4) neighsyncd_timer
5) teamsyncd_timer
Each of these sub-commands are explained in the following section.

Users can use an optional parameter "-s" to use the unix domain socket for communicating with the RedisDB which will be faster when compared to using the default network sockets.
All these commands have the following option.

Options:
  -s, --redis-unix-socket-path TEXT
       unix socket path for redis connection


**config warm_restart bgp_timer**

This command is used to set the bgp_timer value for warm_restart of BGP service.
bgp_timer holds the time interval utilized by fpmsyncd during warm-restart episodes.
During this interval fpmsyncd will recover all the routing state previously pushed to AppDB, as well as all the new state coming from zebra/bgpd.
Upon expiration of this timer, fpmsyncd will execute the reconciliation logic to eliminate all the stale entries from AppDB.
This timer should match the BGP-GR restart-timer configured within the elected routing-stack.
Supported range: 1-3600.

  - Usage:
    config warm_restart bgp_timer <seconds>
	seconds range 1 to 3600.


- Example:
  ```
	admin@sonic:~$ sudo config warm_restart bgp_timer 1000
  ```

**config warm_restart enable/disable**

This command is used to enable or disable the warm_restart for a particular service that supports warm reboot.
Following four services support warm reboot. When user restarts the particular service using "systemctl restart <service_name>", this configured value will be checked for whether it is enabled or disabled.
If this configuration is enabled for that service, it will perform warm reboot for that service. Otherwise, it will do cold restart of the service.

  - Usage:
    config warm_restart enable [<module_name>]

       module_name can be either system or swss or bgp or teamd.
	   If "module_name" argument is not specified, it will enable "system" module.


- Example:
  ```
	admin@sonic:~$ sudo config warm_restart enable
	The above command will set warm_restart as "enable" for the "system" service.

	admin@sonic:~$ sudo config warm_restart enable swss
	The above command will set warm_restart as "enable" for the "swss" service. When user does "systemctl restart swss", it will perform warm reboot instead of cold reboot.

	admin@sonic:~$ sudo config warm_restart enable teamd
	The above command will set warm_restart as "enable" for the "teamd" service. When user does "systemctl restart teamd", it will perform warm reboot instead of cold reboot.


  ```


**config warm_restart neighsyncd_timer**

This command is used to set the neighsyncd_timer value for warm_restart of "swss" service.
neighsyncd_timer is the timer used for "swss" (neighsyncd) service during the warm restart.
Timer is started after the neighborTable is restored to internal data structures.
neighborsyncd then starts to read all linux kernel entries and mark the entries in the data structures accordingly.
Once the timer is expired, reconciliation is done and the delta is pushed to appDB
Valid value is 1-9999. 0 is invalid.

  - Usage:
    config warm_restart bgp_timerneighsyncd_timer <seconds>
	seconds range 1 to 9999.


- Example:
  ```
	admin@sonic:~$ sudo config warm_restart neighsyncd_timer 2000
  ```


**config warm_restart teamsyncd_timer**

This command is used to set the teamsyncd_timer value for warm_restart of teamd service.
teamsyncd_timer holds the time interval utilized by teamsyncd during warm-restart episodes.
The timer is started when teamsyncd starts. During the timer interval, teamsyncd will preserve all LAG interface changes, but it will not apply them.
The changes will only be applied when the timer expires.
When the changes are applied, the stale LAG entries will be removed, the new LAG entries will be created.
Supported range: 1-9999. 0 is invalid

  - Usage:
    config warm_restart teamsyncd_timer <seconds>
	seconds range 1 to 9999.


- Example:
  ```
	admin@sonic:~$ sudo config warm_restart teamsyncd_timer 3000
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Warm-Restart)


# Watermark Configuration And Show

## Watermark Show command

**show watermark telemetry interval**

This command displays the configured interval for the telemetry.

  - Usage:
    show watermark telemetry interval


- Example:
  ```
	admin@sonic:~$ show watermark telemetry interval

      Telemetry interval 120 second(s)

  ```

## Watermark Config command

**config watermark telemetry interval**

This command is used to configure the interval for telemetry.
The default interval is 120 seconds.
There is no regulation on the valid range of values; it leverages linux timer.

  - Usage:
    config watermark telemetry interval <value>


- Example:
  ```
	admin@sonic:~$ sudo config watermark telemetry interval 999
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Watermark-Configuration-And-Show)



# Software Installation Commands

SONiC software can be installed in two methods, viz, "using sonic_installer tool", "ONIE Installer".


## SONiC Installer
This is a command line tool available as part of the SONiC software; If the device is already running the SONiC software, this tool can be used to install an alternate image in the partition.
This tool has facility to install an alternate image, list the available images and to set the next reboot image.

**sonic_installer install**

This command is used to install a new image on the alternate image partition.  This command takes a path to an installable SONiC image or URL and installs the image.

  - Usage:
    sonic_installer install <path>


- Example:
  ```
  admin@sonic:~$ sonic_installer install https://sonic-jenkins.westus.cloudapp.azure.com/job/xxxx/job/buildimage-xxxx-all/xxx/artifact/target/sonic-xxxx.bin
  New image will be installed, continue? [y/N]: y
  Downloading image...
  ...100%, 480 MB, 3357 KB/s, 146 seconds passed
  Command: /tmp/sonic_image
  Verifying image checksum ... OK.
  Preparing image archive ... OK.
  ONIE Installer: platform: XXXX
  onie_platform:
  Installing SONiC in SONiC
  Installing SONiC to /host/image-xxxx
  Directory /host/image-xxxx/ already exists. Cleaning up...
  Archive:  fs.zip
     creating: /host/image-xxxx/boot/
    inflating: /host/image-xxxx/boot/vmlinuz-3.16.0-4-amd64
    inflating: /host/image-xxxx/boot/config-3.16.0-4-amd64
    inflating: /host/image-xxxx/boot/System.map-3.16.0-4-amd64
    inflating: /host/image-xxxx/boot/initrd.img-3.16.0-4-amd64
     creating: /host/image-xxxx/platform/
   extracting: /host/image-xxxx/platform/firsttime
    inflating: /host/image-xxxx/fs.squashfs
    inflating: /host/image-xxxx/dockerfs.tar.gz
  Log file system already exists. Size: 4096MB
  Installed SONiC base image SONiC-OS successfully

  Command: cp /etc/sonic/minigraph.xml /host/

  Command: grub-set-default --boot-directory=/host 0

  Done
  ```

**sonic_installer list**

This command displays information about currently installed images. It displays a list of installed images, currently running image and image set to be loaded in next reboot.

  - Usage:
    sonic_installer list

- Example:
   ```
  admin@sonic:~$ sonic_installer list
  Current: SONiC-OS-HEAD.XXXX
  Next: SONiC-OS-HEAD.XXXX
  Available:
  SONiC-OS-HEAD.XXXX
  SONiC-OS-HEAD.YYYY
  ```

**sonic_installer set_default**

This command is be used to change the image which can be loaded by default in all the subsequent reboots.

  - Usage:
    sonic_installer set_default <image_name>

- Example:
  ```
  admin@sonic:~$ sonic_installer set_default SONiC-OS-HEAD.XXXX
  ```

**sonic_installer set_next_boot**

This command is used to change the image that can be loaded in the *next* reboot only. Note that it will fallback to current image in all other subsequent reboots after the next reboot.

  - Usage:
    sonic_installer set_next_boot <image_name>

- Example:
  ```
  admin@sonic:~$ sonic_installer set_next_boot SONiC-OS-HEAD.XXXX
  ```

**sonic_installer remove**

This command is used to remove the unused SONiC image from the disk. Note that it's *not* allowed to remove currently running image.

  - Usage:
    sonic_installer remove <image_name>

- Example:
  ```
  admin@sonic:~$ sonic_installer remove SONiC-OS-HEAD.YYYY
  Image will be removed, continue? [y/N]: y
  Updating GRUB...
  Done
  Removing image root filesystem...
  Done
  Command: grub-set-default --boot-directory=/host 0

  Image removed
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Software-Installation-Commands)



# Troubleshooting Commands

For troubleshooting and debugging purposes, this command gathers pertinent information about the state of the device; information is as diverse as syslog entries, database state, routing-stack state, etc., It then compresses it into an archive file. This archive file can be sent to the SONiC development team for examination.
Resulting archive file is saved as `/var/dump/<DEVICE_HOST_NAME>_YYYYMMDD_HHMMSS.tar.gz`

  - Usage:
    show techsupport


- Example:
  ```
  admin@sonic:~$ show techsupport
  ```
If the SONiC system was running for quite some time `show techsupport` will produce a large dump file. To reduce the amount of syslog and core files gathered during system dump use `--since` option:

- Example:
  ```
  admin@sonic:~$ show techsupport --since=yesterday  # Will collect syslog and core files for the last 24 hours
  admin@sonic:~$ show techsupport --since='hour ago' # Will collect syslog and core files for the last one hour
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Troubleshooting-commands)

# Routing Stack Configuration And Show

SONiC software is agnostic of the routing software that is being used in the device. For example, users can use either Quagga or FRR routing stack as per their requirement.
A separate shell (vtysh) is provided to configure such routing stacks.
Once if users go to "vtysh", they can use the routing stack specific commands as given in the following example.

  - Example: Quagga Routing Stack
  ```
	admin@T1-2:~$ vtysh

	Hello, this is Quagga (version 0.99.24.1).
	Copyright 1996-2005 Kunihiro Ishiguro, et al.

	T1-2# show route-map (This command displays the route-map that is configured for the routing protocol.)
	ZEBRA:
	route-map RM_SET_SRC, permit, sequence 10
	  Match clauses:
	  Set clauses:
		src 10.12.0.102
	  Call clause:
	  Action:
		Exit routemap
  ```

Refer the routing stack [Quagga Command Reference](https://www.quagga.net/docs/quagga.pdf) or [FRR Command Reference](https://buildmedia.readthedocs.org/media/pdf/frrouting/latest/frrouting.pdf) to know more about about the routing stack configuration.


Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE)


# Quagga BGP Show Commands

**show ip bgp summary**

This command displays the summary of all IPv4 bgp neighbors that are configured and the corresponding states.

  - Usage:
    show ip bgp summary

- Example:
  ```
  admin@sonic:~$ show ip bgp summary
  BGP router identifier 1.2.3.4, local AS number 65061
  RIB entries 6124, using 670 KiB of memory
  Peers 2, using 143 KiB of memory

  Neighbor        V         AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
  192.168.1.161    4 65501   88698  102781        0    0    0 08w5d14h        2
  192.168.1.163    4 65502   88698  102780        0    0    0 08w5d14h        2

  Total number of neighbors 2
  ```

**show ip bgp neighbors**

This command displays all the details of IPv4 & IPv6 BGP neighbors when no optional argument is specified.

When the optional argument IPv4_address is specified, it displays the detailed neighbor information about that specific IPv4 neighbor.

Command has got additional optional arguments to display only the advertised routes, or the received routes, or all routes.

In order to get details for an IPv6 neigbor, use "show ipv6 bgp neighbor <ipv6_address>" command.

  - Usage:
    show ip bgp neighbors [<ipv4-address> [advertised-routes | received-routes | routes]]


- Example:
  ```
  admin@sonic:~$ show ip bgp neighbors
  BGP neighbor is 192.168.1.161, remote AS 65501, local AS 65061, external link
   Description: ARISTA01T0
    BGP version 4, remote router ID 1.2.3.4
    BGP state = Established, up for 08w5d14h
    Last read 00:00:46, hold time is 180, keepalive interval is 60 seconds
    Neighbor capabilities:
      4 Byte AS: advertised and received
      Dynamic: received
      Route refresh: advertised and received(old & new)
      Address family IPv4 Unicast: advertised and received
      Graceful Restart Capabilty: advertised and received
        Remote Restart timer is 120 seconds
        Address families by peer:
          IPv4 Unicast(not preserved)
    Graceful restart informations:
      End-of-RIB send: IPv4 Unicast
      End-of-RIB received: IPv4 Unicast
    Message statistics:
      Inq depth is 0
      Outq depth is 0
                           Sent       Rcvd
      Opens:                  1          1
      Notifications:          0          0
      Updates:            14066          3
      Keepalives:         88718      88698
      Route Refresh:          0          0
      Capability:             0          0
      Total:             102785      88702
    Minimum time between advertisement runs is 30 seconds

   For address family: IPv4 Unicast
    Community attribute sent to this neighbor(both)
    2 accepted prefixes

    Connections established 1; dropped 0
    Last reset never
  Local host: 192.168.1.160, Local port: 32961
  Foreign host: 192.168.1.161, Foreign port: 179
  Nexthop: 192.168.1.160
  Nexthop global: fe80::f60f:1bff:fe89:bc00
  Nexthop local: ::
  BGP connection: non shared network
  Read thread: on  Write thread: off
  ```

  - Optionally, you can specify an IP address in order to display only that particular neighbor. In this mode, you can optionally specify whether you want to display all routes advertised to the specified neighbor, all routes received from the specified neighbor or all routes (received and accepted) from the specified neighbor.


- Example:
  ```
  admin@sonic:~$ show ip bgp neighbors 192.168.1.161

  admin@sonic:~$ show ip bgp neighbors 192.168.1.161 advertised-routes

  admin@sonic:~$ show ip bgp neighbors 192.168.1.161 received-routes

  admin@sonic:~$ show ip bgp neighbors 192.168.1.161 routes
  ```

**show ipv6 bgp summary**

This command displays the summary of all IPv4 bgp neighbors that are configured and the corresponding states.

  - Usage:
     show ipv6 bgp summary


- Example:
  ```
  admin@sonic:~$ show ipv6 bgp summary
  BGP router identifier 10.1.0.32, local AS number 65100
  RIB entries 12809, using 1401 KiB of memory
  Peers 8, using 36 KiB of memory

  Neighbor        V         AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
  fc00::72        4 64600   12588   12591        0    0    0 06:51:17     6402
  fc00::76        4 64600   12587    6190        0    0    0 06:51:28     6402
  fc00::7a        4 64600   12587    9391        0    0    0 06:51:23     6402
  fc00::7e        4 64600   12589   12592        0    0    0 06:51:25     6402

  Total number of neighbors 4
  ```

**show ipv6 bgp neighbors**

This command displays all the details of one particular IPv6 Border Gateway Protocol (BGP) neighbor. Option is also available to display only the advertised routes, or the received routes, or all routes.

  - Usage:
    show ipv6 bgp neighbors <ipv6-address> (advertised-routes | received-routes | routes)`

- Example:
  ```
  admin@sonic:~$ show ipv6 bgp neighbors fc00::72 advertised-routes

  admin@sonic:~$ show ipv6 bgp neighbors fc00::72 received-routes

  admin@sonic:~$ show ipv6 bgp neighbors fc00::72 routes
  ```

**show route-map**

This command displays the routing policy that takes precedence over the other route processes that are configured.

  - Usage:
    show route-map

  - Example:
  ```
	admin@T1-2:~$ show route-map
	ZEBRA:
	route-map RM_SET_SRC, permit, sequence 10
	  Match clauses:
	  Set clauses:
		src 10.12.0.102
	  Call clause:
	  Action:
		Exit routemap
	ZEBRA:
	route-map RM_SET_SRC6, permit, sequence 10
	  Match clauses:
	  Set clauses:
		src fc00:1::102
	  Call clause:
	  Action:
		Exit routemap
	BGP:
	route-map FROM_BGP_SPEAKER_V4, permit, sequence 10
	  Match clauses:
	  Set clauses:
	  Call clause:
	  Action:
	    Exit routemap
	BGP:
	route-map TO_BGP_SPEAKER_V4, deny, sequence 10
	  Match clauses:
	  Set clauses:
	  Call clause:
	  Action:
	    Exit routemap
	BGP:
	route-map ISOLATE, permit, sequence 10
	  Match clauses:
	  Set clauses:
		as-path prepend 65000
	  Call clause:
	  Action:
		Exit routemap
  ```

# Syslog Server Configuration Commands 

This sub-section of commands is used to add or remove the configured syslog servers.

**config syslog add** 

This command is used to add a SYSLOG server to the syslog server list.  Note that more that one syslog server can be added in the device.

- Usage: config syslog add <ip-address>
- Example: 
  ```
  admin@str-s6000-acs-11:~$ sudo config syslog add 1.1.1.1
  Syslog server 1.1.1.1 added to configuration
  Restarting rsyslog-config service...
  admin@str-s6000-acs-11:~$
  ```

**config syslog delete**

This command is used to delete the syslog server configured. 

- Usage: config syslog del <ip-address>
- Example:
  ```
  admin@str-s6000-acs-11:~$ sudo config syslog del 1.1.1.1
  Syslog server 1.1.1.1 removed from configuration
  Restarting rsyslog-config service...
  admin@str-s6000-acs-11:~$
  ```

# DHCP Relay Destination IP address Configuration Commands 

This sub-section of commands is used to add or remove the DHCP Relay Destination IP address(es) for a VLAN interface.

**config vlan dhcp_relay add** 

This command is used to add a DHCP Relay Destination IP address to the a VLAN.  Note that more that one DHCP Relay Destination IP address can be added on a VLAN interface.

- Usage: config vlan dhcp_relay add <vlan-id> <dhcp_relay_destination_ip>
- Example: 
  ```
  admin@str-s6000-acs-11:~$ sudo config vlan dhcp_relay add 1000 7.7.7.7
  Added DHCP relay destination address 7.7.7.7 to Vlan1000
  Restarting DHCP relay service...
  Running command: systemctl restart dhcp_relay
  admin@str-s6000-acs-11:~$ 
  ```

**config vlan dhcp_relay delete**

This command is used to delete a configured DHCP Relay Destination IP address from a VLAN interface. 

- Usage: config vlan dhcp_relay del <vlan-id> <dhcp_relay_destination_ip>
- Example:
  ```
  admin@str-s6000-acs-11:~$ sudo config vlan dhcp_relay del 1000 7.7.7.7
  Removed DHCP relay destination address 7.7.7.7 from Vlan1000
  Restarting DHCP relay service...
  Running command: systemctl restart dhcp_relay
  admin@str-s6000-acs-11:~$ 
  ```
  
# NTP Server Configuration Commands 

This sub-section of commands is used to add or remove the configured NTP servers.

**config ntp add** 

This command is used to add a NTP server IP address to the NTP server list.  Note that more that one NTP server IP address can be added in the device.

- Usage: config ntp add <ip-address>
- Example: 
  ```
  admin@str-s6000-acs-11:~$ sudo config ntp add 9.9.9.9
  NTP server 9.9.9.9 added to configuration
  Restarting ntp-config service...
  admin@str-s6000-acs-11:~$
  ```

**config ntp delete**

This command is used to delete a configured NTP server IP address. 

- Usage: config ntp del <ip-address>
- Example:
  ```
  admin@str-s6000-acs-11:~$ sudo config ntp del 9.9.9.9
  NTP server 9.9.9.9 removed from configuration
  Restarting ntp-config service...
  admin@str-s6000-acs-11:~$
  ```

Go Back To [Beginning of the document](#SONiC-COMMAND-LINE-INTERFACE-GUIDE) or [Beginning of this section](#Quagga-BGP-Show-Commands)
