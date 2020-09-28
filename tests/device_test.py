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
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual("sdm.devices.types.SomeDeviceType", device.type)

  def testNoTraits(self):
    raw = {
       "name": "my/device/name",
       "type": "sdm.devices.types.SomeDeviceType",
       "traits": {
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual("sdm.devices.types.SomeDeviceType", device.type)

  def testInfoTraits(self):
    raw = {
       "name": "my/device/name",
       "type": "sdm.devices.types.SomeDeviceType",
       "traits": {
         "sdm.devices.traits.Info": {
           "customName": "Device Name",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual("sdm.devices.types.SomeDeviceType", device.type)
    self.assertEqual("Device Name", device.custom_name)
    self.assertEqual(["sdm.devices.traits.Info"], device.traits)

