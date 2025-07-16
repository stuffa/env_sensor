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


def titleise(s):
     return "".join([w[0].upper() + w[1:] for w in s.split()])


# def is_pico_w():
#     return sys.implementation._machine.startswith("Raspberry Pi Pico W")


def get_vsys():
    conversion_factor = 3 * 3.3 / 65535

    # make sure pin 25 (LED) is high. - required for reading vsys
    led = machine.Pin(25, mode=machine.Pin.OUT)
    led.high()

    # Reconfigure pin 29 as an input, required for ADC use
    machine.Pin(29, machine.Pin.IN)
    vsys = machine.ADC(29).read_u16() * conversion_factor

    # return the LED to a low/off state to save power
    led.low()
    return vsys


if __name__ == "__main__":
    test_voltage = get_vsys()
    print(f"Battery: {test_voltage} Volts")
