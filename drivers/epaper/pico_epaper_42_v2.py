# Materials used for discovery can be found here
# https://www.waveshare.com/wiki/4.2inch_e-Paper_Module_Manual#Introduction
# Note, at the time of writing this, none of the source materials have working
# code that works with partial refresh, as the C code has a bug and all the other
# materials use that reference material as the source of truth.
# *****************************************************************************
# * | File        :	  pico_epaper_42_v2.py
# * | Author      :   michael surdouski
# * | Function    :   Electronic paper driver
# *----------------
# * | This version:   rev2.2
# * | Date        :   2024-05-22
# -----------------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from machine import Pin, SPI
import framebuf
import time
import asyncio
from drivers.boolpalette import BoolPalette


def asyncio_running():
    return False
    # try:
    #     _ = asyncio.current_task()
    # except:
    #     return False
    # return True


# Display resolution
_EPD_WIDTH = const(400)
_BWIDTH = _EPD_WIDTH // 8
_EPD_HEIGHT = const(300)

_RST_PIN = 12
# changed default to 7, as this can be confusing on pico -- pin 8 for SPI1 is the Rx, which overrides DC pin if miso is set to none
_DC_PIN = 7
_CS_PIN = 9
_BUSY_PIN = 13

EPD_LUT_ALL = b"\x01\x0A\x1B\x0F\x03\x01\x01\x05\x0A\x01\x0A\x01\x01\x01\x05\x08\x03\x02\x04\x01\x01\x01\x04\x04\x02\x00\x01\x01\x01\x00\x00\x00\x00\x01\x01\
\x01\x00\x00\x00\x00\x01\x01\x01\x0A\x1B\x0F\x03\x01\x01\x05\x4A\x01\x8A\x01\x01\x01\x05\x48\x03\x82\x84\x01\x01\x01\x84\x84\x82\x00\x01\x01\
\x01\x00\x00\x00\x00\x01\x01\x01\x00\x00\x00\x00\x01\x01\x01\x0A\x1B\x8F\x03\x01\x01\x05\x4A\x01\x8A\x01\x01\x01\x05\x48\x83\x82\x04\x01\x01\
\x01\x04\x04\x02\x00\x01\x01\x01\x00\x00\x00\x00\x01\x01\x01\x00\x00\x00\x00\x01\x01\x01\x8A\x1B\x8F\x03\x01\x01\
\x05\x4A\x01\x8A\x01\x01\x01\x05\x48\x83\x02\x04\x01\x01\x01\x04\x04\x02\x00\x01\x01\x01\x00\x00\x00\x00\x01\x01\
\x01\x00\x00\x00\x00\x01\x01\x01\x8A\x9B\x8F\x03\x01\x01\x05\x4A\x01\x8A\x01\x01\x01\x05\x48\x03\x42\x04\x01\x01\
\x01\x04\x04\x42\x00\x01\x01\x01\x00\x00\x00\x00\x01\x01\x01\x00\x00\x00\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\
\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x07\x17\x41\xA8\x32\x30"


class EPD(framebuf.FrameBuffer):
    # A monochrome approach should be used for coding this. The rgb method ensures
    # nothing breaks if users specify colors.
    @staticmethod
    def rgb(r, g, b):
        return int((r > 127) or (g > 127) or (b > 127))

    def __init__(self, spi=None, cs=None, dc=None, rst=None, busy=None, partial=False):
        self._rst = Pin(_RST_PIN, Pin.OUT) if rst is None else rst
        self._busy_pin = Pin(_BUSY_PIN, Pin.IN, Pin.PULL_UP) if busy is None else busy
        self._cs = Pin(_CS_PIN, Pin.OUT) if cs is None else cs
        self._dc = Pin(_DC_PIN, Pin.OUT) if dc is None else dc
        self._spi = (
            SPI(1, sck=Pin(10), mosi=Pin(11), miso=Pin(28)) if spi is None else spi
        )
        self._spi.init(baudrate=4_000_000)
        # Busy flag: set immediately on .show(). Cleared when busy pin is logically false.
        self._busy = False
        # Async API
        self.updated = asyncio.Event()
        self.complete = asyncio.Event()
        # partial refresh
        self._partial = partial

        # Public bound variables required by nanogui.
        # Dimensions in pixels as seen by nanogui
        self.width = _EPD_WIDTH
        self.height = _EPD_HEIGHT
        # Other public bound variable.
        # Special mode enables demos written for generic displays to run.
        self.demo_mode = False

        self._buf = bytearray(_EPD_HEIGHT * _BWIDTH)
        self._mvb = memoryview(self._buf)
        self._ibuf = bytearray(1000)  # Buffer for inverted pixels
        mode = framebuf.MONO_HLSB
        self.palette = BoolPalette(mode)  # Enable CWriter.
        super().__init__(self._buf, _EPD_WIDTH, _EPD_HEIGHT, mode)
        self.init()
        time.sleep_ms(500)

    # Hardware reset
    def reset(self):
        for v in (1, 0, 1):
            self._rst(v)
            time.sleep_ms(20)

    def _command(self, command, data=None):
        self._dc(0)
        self._cs(0)
        self._spi.write(command)
        self._cs(1)
        if data is not None:
            self._data(data)

    def _data(self, data):
        self._dc(1)
        self._cs(0)
        self._spi.write(data)
        self._cs(1)

    def display_on(self):
        self._command(b"\x22")
        self._data(b"\xF7")
        self._command(b"\x20")

    def display_on_partial(self):
        self._command(b"\x22")
        self._data(b"\xFF")
        self._command(b"\x20")

    def init(self):
        self.set_full(update_partial=False, force_update=True)

        # Clear display
        self.clear()

        self.display_on()

    def clear(self):
        self._command(b"\x24")
        for j in range(_EPD_HEIGHT):
            self._data(b"\xff" * _BWIDTH)
        self._command(b"\x26")
        for j in range(_EPD_HEIGHT):
            self._data(b"\xff" * _BWIDTH)

    def set_full(self, update_partial=True, force_update=False):
        print(f'set_full: {update_partial}, {force_update}')
        if self._partial or force_update:
            self.reset()
            self.wait_until_ready()

            self._command(b"\x12")  # SWRESET
            self.wait_until_ready()

            self._command(b"\x21")  # Display update control
            self._data(b"\x40")
            self._data(b"\x00")

            self._command(b"\x3C")  # BorderWaveform
            self._data(b"\x05")

            self._command(b"\x11")  # data  entry  mode
            self._data(b"\x03")  # X-mode

            self._set_window()
            self._set_cursor()

            self.wait_until_ready()

        self._partial = False if update_partial else self._partial

    def set_partial(self):
        print(f'set_partial: True')
        self._partial = True

    def ready(self):
        return not (self._busy or (self._busy_pin() == 1))  # 1 == busy

    def _line(self, n, buf=bytearray(_BWIDTH)):
        img = self._mvb
        s = n * _BWIDTH
        for x, b in enumerate(img[s: s + _BWIDTH]):
            buf[x] = b ^ 0xFF
        self._data(buf)

    async def _as_show_full(self):
        self._command(b"\x24")
        for j in range(_EPD_HEIGHT):  # Loop would take ~300ms
            self._line(j)
            await asyncio.sleep_ms(0)
        self._command(b"\x26")
        for j in range(_EPD_HEIGHT):  # Loop would take ~300ms
            self._line(j)
            await asyncio.sleep_ms(0)
        self.wait_until_ready()
        self._updated.set()
        self._updated.clear()
        self._busy = False

    def show(self):
        if self._busy:
            raise RuntimeError("Cannot refresh: display is busy.")
        if self._partial:
            print('show_partial')
            self._show_partial()
        else:
            print('show_full')
            self._show_full()

    def _show_full(self):
        self._busy = True  # Immediate busy flag. Pin goes low much later.
        if asyncio_running():
            print('asyncio_running')
            self.updated.clear()
            self.complete.clear()
            asyncio.create_task(self._as_show_full())
            return

        # self._command(b"\x11")  # data  entry  mode
        # self._data(b"\x03")  # X-mode

        self._command(b"\x24")
        for j in range(_EPD_HEIGHT):
            self._line(j)
        self._command(b"\x26")
        for j in range(_EPD_HEIGHT):
            self._line(j)
        self._busy = False

        self.display_on()

        # if not self.demo_mode:
        #     # Immediate return to avoid blocking the whole application.
        #     # User should wait for ready before calling refresh()
        #     return

        self.wait_until_ready()


    def _show_partial(self):
        self.reset()
        self.wait_until_ready()

        self._command(b"\x3C")  # BorderWaveform
        self._data(b"\x80")

        self._command(b"\x21")  # Display update control
        self._data(b"\x00")
        self._data(b"\x00")

        self._command(b"\x3C")  # BorderWaveform
        self._data(b"\x80")

        self._command(b"\x11")  # data  entry  mode
        self._data(b"\x03")  # X-mode

        self._set_window()
        self._set_cursor()

        self.wait_until_ready()

        self._command(b"\x24")
        for j in range(_EPD_HEIGHT):
            self._line(j)

        self.display_on_partial()

        # self._command(b"\x22")
        # self._command(b"\xFF")
        # self._command(b"\x20")

        # if not self.demo_mode:
        #     # Immediate return to avoid blocking the whole application.
        #     # User should wait for ready before calling refresh()
        #     return

        self.wait_until_ready()

    def wait_until_ready(self):
        while not self.ready():
            time.sleep_ms(100)


    def sleep(self):
        self._command(b"\x10")  # deep sleep
        self._data(b"\x01")

    # window and cursor always the same for 4.2"
    def _set_window(self):
        self._command(b"\x44")
        self._data(b"\x00")
        self._data(b"\x31")

        self._command(b"\x45")
        self._data(b"\x00")
        self._data(b"\x00")
        self._data(b"\x2B")
        self._data(b"\x01")

    def _set_cursor(self):
        self._command(b"\x4E")
        self._data(b"\x00")

        self._command(b"\x4F")
        self._data(b"\x00")
        self._data(b"\x00")

    # def init_4gray(self):
    #     self.reset()
    #     self.wait_until_ready()

    #     self._command(b"\x12") #SWRESET
    #     self.wait_until_ready()

    #     self._command(b"\x21")  # Display update control
    #     self._data(b"\x00")
    #     self._data(b"\x00")

    #     self._command(b"\x3C")  # BorderWaveform
    #     self._data(b"\x03")

    #     self._command(b"\x0C")  # BTST
    #     self._data(b"\x8B") # 8B
    #     self._data(b"\x9C") # 9C
    #     self._data(b"\xA4") # 96 A4
    #     self._data(b"\x0F") # 0F

    #     self.lut()

    #     self._command(b"\x11")  # data  entry  mode
    #     self._data(b"\x03")  # X-mode

    #     self._command(b"\x44")
    #     self._data(b"\x00")
    #     self._data(b"\x31")

    #     self._command(b"\x45")
    #     self._data(b"\x00")
    #     self._data(b"\x00")
    #     self._data(b"\x2B")
    #     self._data(b"\x01")

    #     self._command(b"\x4E")
    #     self._data(b"\x00")

    #     self._command(b"\x4F")
    #     self._data(b"\x00")
    #     self._data(b"\x00")

    #     self.wait_until_ready()

    # TODO: [pr comment] I am a software developer, so some of this goes over my head. my use case was to get partial refresh working, which I did. I'm willing
    #  to validate fast as well, but I don't know what a validation success looks like, so I'd need some assistance on that.
    # def init_fast(self):
    #     self.reset()
    #     self.wait_until_ready()

    #     self._command(b"\x12") #SWRESET
    #     self.wait_until_ready()

    #     self._command(b"\x21")  # Display update control
    #     self._data(b"\x40")
    #     self._data(b"\x00")

    #     if some_conditional_logic_here():
    #         self._command(b"\x3C")  # BorderWaveform
    #         self._data(b"\x05")
    #     else:
    #         self._command(b"\x1A")  # BorderWaveform
    #         self._data(b"\x6E")

    #     self._command(b"\x22")  # load temperature value
    #     self._data(b"\x91")
    #     self._command(b"\x20")
    #     self.wait_until_ready()

    #     self._command(b"\x11")  # data  entry  mode
    #     self._data(b"\x03")  # X-mode

    #     self._command(b"\x44")
    #     self._data(b"\x00")
    #     self._data(b"\x31")

    #     self._command(b"\x45")
    #     self._data(b"\x00")
    #     self._data(b"\x00")
    #     self._data(b"\x2B")
    #     self._data(b"\x01")

    #     self._command(b"\x4E")
    #     self._data(b"\x00")

    #     self._command(b"\x4F")
    #     self._data(b"\x00")
    #     self._data(b"\x00")

    #     self._command(b"\x24")
    #     for j in range(_EPD_HEIGHT):
    #         self._line(j)

    #     self._command(b"\x26")
    #     for j in range(_EPD_HEIGHT):
    #         self._line(j)

    #     self.display_on_fast()

    # def show_4gray(self):
    #     self._command(b"\x24")
    #     for j in range(_EPD_HEIGHT):
    #         self._line(j)

    #     self._command(b"\x26")
    #     for j in range(_EPD_HEIGHT):
    #         self._line(j)

    #     self.display_4gray()
    #     self.wait_until_ready()

    # def show_fast(self):
    #     self._command(b"\x24")
    #     for j in range(_EPD_HEIGHT):
    #         self._line(j)

    #     self._command(b"\x26")
    #     for j in range(_EPD_HEIGHT):
    #         self._line(j)

    #     self.display_on_fast()
    #     self.wait_until_ready()

    # def display_4gray(self):
    #     self._command(b"\x22")
    #     self._data(b"\xC7")
    #     self._command(b"\x20")
    #     time.sleep_ms(100)
    #     self.wait_until_ready()

    # def lut(self):
    #     self._command(b"\x32")
    #     self._data(EPD_LUT_ALL[0:127])

    #     self._command(b"\x3F")
    #     self._data(EPD_LUT_ALL[127:128])

    #     self._command(b"\x03")
    #     self._data(EPD_LUT_ALL[128:129])

    #     self._command(b"\x04")
    #     self._data(EPD_LUT_ALL[229:232])

    #     self._command(b"\x2c")
    #     self._data(EPD_LUT_ALL[232:233])

    # def display_on_fast(self):
    #     self._command(b"\x22")
    #     self._command(b"\xC7")
    #     self._command(b"\x20")
    #     self.wait_until_ready()
