# Scaffolding for local test development
from .context import google_nest_sdm

import unittest
from google_nest_sdm.device import Device


class DeviceTest(unittest.TestCase):
  def testDeviceId(self):
    raw = {
       "name": "my/device/name",
       "type": "sdm.devices.types.SomeDeviceType",
    }
    device = Device(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual("sdm.devices.types.SomeDeviceType", device.type)
