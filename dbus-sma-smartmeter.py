#!/usr/bin/env python3

"""
Created by Waldmensch aka Waldmaus in 2023.
Changed by Ersus in 202503

Inspired by:
 - https://github.com/RalfZim/venus.dbus-fronius-smartmeter (Inspiration)
 - https://github.com/victronenergy/velib_python/blob/master/dbusdummyservice.py (Template)
 - https://github.com/iobroker-community-adapters/ioBroker.sma-em/ (SMA Protocol)

This code and its documentation can be found on: https://github.com/Waldmensch1/venus.dbus-sma-smartmeter
"""

from gi.repository import GLib
from vedbus import VeDbusService
import socket
import struct
import platform
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import threading
import time

MULTICAST_IP = "239.12.255.254"
MULTICAST_PORT = 9522
EM_SERIAL = 0

sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../ext/velib_python'))

os.makedirs('/var/log/dbus-sma-smartmeter', exist_ok=True)
logging.basicConfig(
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler('/var/log/dbus-sma-smartmeter/current.log', maxBytes=200000, backupCount=5)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)

class DbusSMAEMService(object):
    def __init__(self, servicename, deviceinstance, productname='SMA-EM Speedwire Bridge', connection='SMA-EM Service'):
        # ... (deel van het script weggelaten voor beknoptheid, zoals OBIS-definities)

        self._dbusservice = VeDbusService(servicename, register=False)
        logger.info('Connected to dbus, DbusSMAEMService class created')

        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/Connected', 1)
        self._last_data_timestamp = 0
        GLib.timeout_add_seconds(10, self._check_data_freshness)

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", MULTICAST_PORT))

        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_IP), socket.INADDR_ANY)
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        threading.Thread(target=self._alive, args=(self._sock,), daemon=True).start()
        GLib.timeout_add_seconds(30, self._rejoin_multicast)
        self._dbusservice.register()

    def _alive(self, sock):
        logger.info('Socket Thread started')
        while True:
            try:
                data = sock.recv(1024)
                self._update(data)
                self._last_data_timestamp = time.time()
            except Exception as e:
                logger.warning(f"Socket error: {e}")

    def _check_data_freshness(self):
        try:
            elapsed = time.time() - self._last_data_timestamp
            logger.debug(f"Elapsed time since last data: {elapsed:.1f} sec")
            if elapsed > 30:
                if self._dbusservice['/Connected'] != 0:
                    logger.warning("SMA data timeout. Setting /Connected = 0")
                    self._dbusservice['/Connected'] = 0
            else:
                if self._dbusservice['/Connected'] != 1:
                    logger.info("SMA data restored. Setting /Connected = 1")
                    self._dbusservice['/Connected'] = 1
        except Exception as e:
            logger.error(f"Error in _check_data_freshness: {e}")
        return True

    def _rejoin_multicast(self):
        try:
            mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_IP), socket.INADDR_ANY)
            self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            logger.debug("Refreshed multicast join")
        except Exception as e:
            logger.warning(f"Failed to refresh multicast join: {e}")
        return True

def main():
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)
    DbusSMAEMService(servicename='com.victronenergy.grid.smaem', deviceinstance=0)
    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
