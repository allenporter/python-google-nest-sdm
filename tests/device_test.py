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
    self.assertFalse(device.has_trait("sdm.devices.traits.Info"))
    self.assertFalse(hasattr(device, 'status'))
    self.assertFalse(hasattr(device, 'custom_name'))
    self.assertFalse(hasattr(device, 'ambient_humidity_percent'))
    self.assertFalse(hasattr(device, 'ambient_temperature_celsius'))
    self.assertFalse(hasattr(device, 'custom_name'))

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
    self.assertTrue(device.has_trait("sdm.devices.traits.Info"))
    self.assertEqual("Device Name", device.custom_name)
    self.assertEqual(["sdm.devices.traits.Info"], device.traits)

  def testConnectivityTraits(self):
    raw = {
       "traits": {
         "sdm.devices.traits.Connectivity": {
           "status": "OFFLINE",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("OFFLINE", device.status)
    self.assertEqual(["sdm.devices.traits.Connectivity"], device.traits)

  def testHumidityTraits(self):
    raw = {
       "traits": {
         "sdm.devices.traits.Humidity": {
           "ambientHumidityPercent": "25.3",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("25.3", device.ambient_humidity_percent)
    self.assertEqual(["sdm.devices.traits.Humidity"], device.traits)

  def testTemperatureTraits(self):
    raw = {
       "traits": {
         "sdm.devices.traits.Temperature": {
           "ambientTemperatureCelsius": "31.1",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("31.1", device.ambient_temperature_celsius)
    self.assertEqual(["sdm.devices.traits.Temperature"], device.traits)

  def testMultipleTraits(self):
    raw = {
       "name": "my/device/name",
       "type": "sdm.devices.types.SomeDeviceType",
       "traits": {
         "sdm.devices.traits.Info": {
           "customName": "Device Name",
         },
         "sdm.devices.traits.Connectivity": {
           "status": "OFFLINE",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual("sdm.devices.types.SomeDeviceType", device.type)
    self.assertEqual("Device Name", device.custom_name)
    self.assertEqual("OFFLINE", device.status)
    self.assertEqual(["sdm.devices.traits.Info",
                      "sdm.devices.traits.Connectivity"], device.traits)


