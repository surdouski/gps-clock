from .i2c_driver import I2CDriver

def _connectToI2CBus(freq=400000):
    try:
        from machine import I2C, Pin
        return I2C(id=0, scl=Pin(21), sda=Pin(20), freq=freq)
    except Exception as e:
        print(str(e))
        print('error: failed to connect to i2c bus')
    return None


class MicroPythonI2C(I2CDriver):
    _i2cbus = _connectToI2CBus()

    def __init__(self):
        I2CDriver.__init__(self)
        # sda = machine.Pin(20)
        # scl = machine.Pin(21)
        # self._i2cbus = machine.I2C(0, sda=sda, scl=scl, freq=400000)

    # -------------------------------------------------------------------------
    # General get attribute method
    #
    # Used to intercept getting the I2C bus object - so we can perform a lazy
    # connect ....
    #
    def __getattr__(self, name):
        if name == "i2cbus":
            if self._i2cbus is None:
                self._i2cbus = _connectToI2CBus()
            return self._i2cbus

        else:
            # Note - we call __getattribute__ to the super class (object).
            return super(I2CDriver, self).__getattribute__(name)

    # -------------------------------------------------------------------------
    # General set attribute method
    #
    # Basically implemented to make the i2cbus attribute readonly to users
    # of this class.
    #
    def __setattr__(self, name, value):

        if name != 'i2cbus':
            super(I2CDriver, self).__setattr__(name, value)

    # read commands ----------------------------------------------------------
    def readWord(self, address, commandCode):
        buffer = self.i2cbus.readfrom_mem(address, commandCode, 2)
        return (buffer[1] << 8) | buffer[0]

    def readByte(self, address, commandCode):
        return self.i2cbus.readfrom_mem(address, commandCode, 1)[0]

    def readBlock(self, address, commandCode, nBytes):
        return self.i2cbus.readfrom_mem(address, commandCode, nBytes)

    # write commands----------------------------------------------------------
    def writeCommand(self, address, commandCode):
        self.i2cbus.writeto(address, commandCode.to_bytes(1, 'little'))

    def writeWord(self, address, commandCode, value):
        self.i2cbus.writeto_mem(address, commandCode, value.to_bytes(2, 'little'))

    def writeByte(self, address, commandCode, value):
        self.i2cbus.writeto_mem(address, commandCode, value.to_bytes(1, 'little'))

    def writeBlock(self, address, commandCode, value):
        self.i2cbus.writeto_mem(address, commandCode, bytes(value))

    # scan -------------------------------------------------------------------
    @classmethod
    def scan(cls):
        """ Returns a list of addresses for the devices connected to the I2C bus."""

        if cls._i2cbus == None:
            cls._i2cbus = _connectToI2CBus()

        if cls._i2cbus == None:
            return []

        return cls._i2cbus.scan()