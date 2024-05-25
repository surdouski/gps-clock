# ili9486_pico.py Customise for your hardware config and rename

# Released under the MIT License (MIT). See LICENSE.

# ILI9486 on Pi Pico
# See DRIVERS.md for wiring details.

# from machine import Pin, SPI
import gc

from drivers.epaper.pico_epaper_42_v2 import EPD as SSD
from gui.core.nanogui import refresh

# pdc = Pin(7, Pin.OUT, value=0)
# prst = Pin(12, Pin.OUT, value=1)
# pcs = Pin(9, Pin.OUT, value=1)
# pbsy = Pin(13, Pin.IN, Pin.PULL_UP)
# spi = SPI(0, sck=Pin(10), mosi=Pin(11), baudrate=4_000_000)
gc.collect()  # Precaution before instantiating framebuf
ssd = SSD()
