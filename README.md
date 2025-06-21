The display os optional
The firmware will detect the display on initialisation, and if not present will bypas the display routines

Firmware updgrades are initiated by restarting the device
The watchdog timer (if expired) will also trigger a firmware update on restart


To install the formware on the server use the git archive command
~~~
git archive --prefix=<prefix>/
~~~

The SIM7020e can be placed is severat different mode, and these seem to persist even across factory-resets
By default, the SIM7020e, when enabled, will wait for an AT command.
It is possible to place it into a mode where is sends unsilicited message even though it has not yet been communicated with
This causes problems, do we wait for the unsolicied messages to know when the chip is ready
or do we send an AT command and wait for the resoce.  

