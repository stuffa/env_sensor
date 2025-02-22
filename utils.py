import machine

SIE_STATUS_REG = 0x50110000 + 0x50
SIE_CONNECTED  = 1 << 16
SIE_SUSPENDED  = 1 << 4


def console_connected():
    return (machine.mem32[SIE_STATUS_REG] & (SIE_CONNECTED | SIE_SUSPENDED)) == SIE_CONNECTED


# Return the unique id of the device as a string
def uid():
    return "{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}".format(*machine.unique_id())


def rjust(s, n):
    return "".join((" "*(n - len(s)), s))
