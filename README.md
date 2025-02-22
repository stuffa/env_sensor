The display os optional
The firmware will detect the display on initialisation, and if not present will bypas the display routines

Firmware updgrades are initiated by restarting the device
The watchdog timer (if expired) will also trigger a firmware update on restart


To install the formware on the server use the git archive command
~~~
git archive --prefix=<prefix>/
~~~