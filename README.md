The display os optional
The firmware will detect the display on initialisation, and if not present will bypass the display routines

Firmware upgrades are initiated by restarting the device
The watchdog timer (if expired) will also trigger a firmware update on restart


To install the formware on the server, use the git archive command
~~~
git archive --prefix=<prefix>/
~~~

The SIM7020e can be placed in several different modes, and these seem to persist even across factory-resets
By default; the SIM7020e, when enabled, will wait for an AT command.
It is possible to place it into a mode where it sends unsolicited messages, even though it has not yet been
communicated with. This causes problems, do we wait for the unsolicited messages to know when the chip is ready, 
or do we send an AT command and wait for the response.

The NB-IoT libray makes use of the sendCMD() method
This method in turm uses the

The SIM7020e comes with a default configuration that includes echo (ATE1)
however after a factory-reset (AT&F) the configuration is different to shipping defaults
for example, echo is disabled

The +CPIN unsolicited message cones after the initial AT command
if you wait for CPIN before sendind AT it will never come
An AT command must first be sent, then the +CPIN message is sent

DNS also sends an unsolicited message


