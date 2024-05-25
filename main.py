# eclock_test.py Unusual clock display for nanogui
# see micropython-epaper/epd-clock

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2023 Peter Hinch

"""
# color_setup.py:
import gc
from drivers.epaper.pico_epaper_42 import EPD as SSD
gc.collect()  # Precaution before instantiating framebuf
ssd = SSD()  #asyn=True)  # Create a display instance
"""
import sys
import gc
import asyncio
from color_setup import ssd
import time
from machine import RTC

from mgps.micro_gps import GPS
from mgps.nmea_parser import NmeaParser

gc.collect()

from gui.core.writer import CWriter
from gui.widgets.label import ALIGN_CENTER
from gui.core.nanogui import refresh
gc.collect()
import gui.fonts.font10 as font
import gui.fonts.arial35 as arial
from gui.core.colors import *
from extras.widgets.eclock import EClock
gc.collect()
from extras.widgets.grid import Grid
gc.collect()
from extras.date import DateCal
gc.collect()

epaper = hasattr(ssd, "wait_until_ready")
if epaper and not hasattr(ssd, "set_partial"):
    raise OSError("ePaper display does not support partial update.")

rtc = None

async def main():
    # rtc.datetime((2023, 3, 18, 5, 10, 0, 0, 0))

    gps = GPS()
    parser = NmeaParser(-4)

    gps_initialize(gps, parser)

    asyncio.create_task(gps_update(gps, parser))
    asyncio.create_task(clock_writer())

    while True:
        await asyncio.sleep(10_000)  # foreverrrrrrr


def gps_initialize(gps, parser):
    global rtc

    while rtc is None:
        print('aquiring gps for RTC update')
        try:
            for character in gps.get_raw_data():
                parser.update(character)
        except Exception as e:
            sys.print_exception(e)
            time.sleep(5)  # blocking because we rely on rtc being updated once
            continue  # continue operations even if failure

        _timestamp = tuple(int(x) for x in parser.timestamp)  # hours, minutes, seconds
        _date = tuple(int(x) for x in parser.date)  # day, month, year

        print(f"_timestamp: {_timestamp}")
        print(f"_date: {_date}")

        if _timestamp != (0,0,0) and _date != (0,0,0):
            try:
                year = int(f"20{_date[2]}")
                month = _date[1]
                day = _date[0]
                hour = _timestamp[0]
                minute = _timestamp[1]
                second = _timestamp[2]

                # Validate date and time values
                if (1 <= month <= 12 and
                        1 <= day <= 31 and
                        0 <= hour <= 23 and
                        0 <= minute <= 59 and
                        0 <= second <= 59):
                    rtc = RTC()
                    print(f"year: {year}")
                    print(f"month: {month}")
                    print(f"day: {day}")
                    print(f"hour: {hour}")
                    print(f"minute: {minute}")
                    print(f"second: {second}")
                    rtc.datetime((year, month, day, _calculate_weekday(year, month, day), hour, minute, second, 0))
                else:
                    raise ValueError("Invalid date or time values")
            except ValueError as ve:
                print(f"Error: {ve}")
                rtc = None
                time.sleep(5)  # blocking because we rely on rtc being updated once
        else:
            time.sleep(5)  # blocking because we rely on rtc being updated once
    print('end of gps initialize')


async def gps_update(gps, parser):
    global rtc
    while True:
        print(f"current datetime: {rtc.datetime()}")
        print(f"current localtime: {time.localtime()}")
        try:
            for character in gps.get_raw_data():
                parser.update(character)

            _timestamp = tuple(int(x) for x in parser.timestamp)  # hours, minutes, seconds
            _date = tuple(int(x) for x in parser.date)  # day, month, year

            print(f"_timestamp: {_timestamp}")
            print(f"_date: {_date}")

            if _timestamp != (0,0,0) and _date != (0,0,0):
                try:
                    year = int(f"20{_date[2]}")
                    month = _date[1]
                    day = _date[0]
                    hour = _timestamp[0]
                    minute = _timestamp[1]
                    second = _timestamp[2]

                    # Validate date and time values
                    if (1 <= month <= 12 and
                            1 <= day <= 31 and
                            0 <= hour <= 23 and
                            0 <= minute <= 59 and
                            0 <= second <= 59):
                        print(f"year: {year}")
                        print(f"month: {month}")
                        print(f"day: {day}")
                        print(f"hour: {hour}")
                        print(f"minute: {minute}")
                        print(f"second: {second}")
                        rtc.datetime((year, month, day, _calculate_weekday(year, month, day), hour, minute, second, 0))
                    else:
                        raise ValueError("Invalid date or time values")
                except ValueError as ve:
                    sys.print_exception(ve)
        except Exception as e:
            sys.print_exception(e)

        await asyncio.sleep(43_200)  # 12 hours


def _calculate_weekday(year, month, day):
    # Zeller's Congruence algorithm to calculate the weekday
    # Adjust month and year for the algorithm
    if month < 3:
        month += 12
        year -= 1
    k = year % 100
    j = year // 100
    # Zeller's Congruence formula
    day_of_week = (day + ((13*(month+1))//5) + k + (k//4) + (j//4) + (5*j)) % 7
    return (day_of_week + 6) % 7  # Adjusting to match MicroPython's weekday numbering (0-6)


async def clock_writer():
    clock_wri = CWriter(ssd, font, verbose=False)
    clock_wri.set_clip(True, True, False)  # Clip to screen, no wrap

    wri = CWriter(ssd, arial, verbose=False)
    wri.set_clip(True, True, False)  # Clip to screen, no wrap

    refresh(ssd, True)
    if epaper:
        ssd.wait_until_ready()

    screen_width = 400

    ec_height = 242  # height == width
    ec_row = 30
    ec_col = 10

    end_col_1 = ec_height + ec_col
    margin = 3

    ec = EClock(clock_wri, ec_row, ec_col, ec_height, fgcolor=WHITE, bgcolor=BLACK)
    ec.value(t := time.localtime())  # Initial drawing


    start_col_2 = end_col_1 + margin
    grid_width = screen_width - margin - start_col_2

    date_cal = DateCal()

    date_info_grid = Grid(wri, 120, start_col_2, lwidth=grid_width, nrows=2, ncols=1, fgcolor=WHITE, bgcolor=BLACK, bdcolor=False, align=ALIGN_CENTER)
    date_info_grid[0, 0] = f"{date_cal.day_str} {date_cal.mday}"
    date_info_grid[1, 0] = f"{date_cal.month_str}"

    while True:
        t = time.localtime()
        print(f"localtime: {t}")
        if 30 <= t[4] < 31:  # weird way to do this... but it works
            ssd.set_full()
        else:
            ssd.set_partial()
        ssd.wait_until_ready()
        ec.value(t)
        refresh(ssd)
        ssd.wait_until_ready()

        ssd.sleep()

        #sleep 5 minutes for power conservation
        # TODO: turn this into a deep sleep
        await asyncio.sleep(60)

        ssd.reset()  # wake up
        ssd.wait_until_ready()


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
