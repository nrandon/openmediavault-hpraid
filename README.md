openmediavault-hpraid
=====================

Plugin Prerequisites:
---------------------
Before installing this plugin the HPE MCP apt repository must be setup
following the instructions given here:
https://downloads.linux.hpe.com/SDR/project/mcp/


The HPE Smart Array plugin is splits into two parts:

Array Details:
--------------
This executes a helper script __'31-hpraid'__ that is placed in
__'/usr/share/openmediavault/sysinfo/modules.d'__ which supplies information
on the current status of any installed Smart Array Controller compatible with
the HPE __'ssacli'__ command. The script output is obtained from OMV GUI
__'Storage->HPE Smart Array->Array Details'__ and it is also included
in the OMV GUI __'Diagnostics->Reports'__.

Notification Settings:
----------------------
This configures a notification e-mail that is sent if a problem is found with
the Smart Array Controller, any of it peripherals (cache cards, capacitors or
battery's) or any of the defined physical/logical volumes.

To enable the e-mail notification the OMV e-mail __'Notification'__ must be
configured and enabled in __'System->Notification->Settings'__, as the HPE
Smart Array Notification will inherit these e-mail settings. If the OMV
Notifications is not enabled the __'Notification Setting'__ will keep disabling
even if enable is selected.

On the __'Notification Settings'__ page the user must define how often to query
the controller cards, the default is every 900 seconds (15 minuets). The user
must also specify the maximum operating temperatures of the controller(s) and
there peripheral using the YAML editor (usually the specifications are
available from HPE web-site). An empty template to help is supplied on
installation:
```
<Controller type>:
  Cache Module Maximum Temperature (C): <int>
  Capacitor Maximum Temperature (C): <int>
  Controller Maximum Temperature (C): <int>
```
For example, a configuration for a p420 controller(s) with a cache card(s) with
capacitor backup could be:
```
Smart Array P420:
  Cache Module Maximum Temperature (C): 55
  Capacitor Maximum Temperature (C): 60
  Controller Maximum Temperature (C): 100
```
Alternatively for a P410 controller(s) with battery cache backup the
configuration could be:
```
Smart Array P410:
  Cache Module Maximum Temperature (C): 55
  Battery Maximum Temperature (C): 85
  Controller Maximum Temperature (C): 55
```
Note the above value are examples and should be validated against the hardware
being used. Drive temperature are not required as these can be read directly
from the drive firmware. An example of a notification e-mail that could be send
in the event of a problem being detected on a controller card is as follows:
```
[omvsys.local] HPE Smart Array(s) Problem Detected: Warning

Smart Array(s) Description:

Smart Array P410 in Slot 1: (Host SN: XXXXXXXXXXXX)
   OK - Controller Status: (SN: XXXXXXXXXXXXXX, Temp: OK, OK)
   Warning - Cache Status: (SN: XXXXXXXXXXXXXX, Temp: OK, 1.0 GB, Temporarily Disabled)
   Warning - Battery/Capacitor Status: (Temp: OK, Source: Capacitor, Recharging)
   OK - Array A (SATA, Unused Space: 0 MB, OK)
      OK - Logical Drive: 1 (/dev/sda, 1.82 TB, RAID 0, OK)
      OK - Physical Drive: 2I:0:1 (SN: XXXXXXXXXXXX, Temp: OK, port 2I:box 0:bay 1, SATA HDD, 2 TB, OK)
   OK - Array B (SATA, Unused Space: 0 MB, OK)
      OK - Logical Drive: 2 (/dev/sdb, 10.92 TB, RAID 5, OK)
      OK - Physical Drive: 2I:0:2 (SN: XXXXXXXXXXXX, Temp: OK, port 2I:box 0:bay 2, SATA HDD, 4 TB, OK)
      OK - Physical Drive: 2I:0:3 (SN: XXXXXXXXXXXX, Temp: OK, port 2I:box 0:bay 3, SATA HDD, 4 TB, OK)
      OK - Physical Drive: 2I:0:4 (SN: XXXXXXXXXXXX, Temp: OK, port 2I:box 0:bay 4, SATA HDD, 4 TB, OK)

Updated At: 13:31:06 24-07-2021
```
