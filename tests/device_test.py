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
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertFalse(device.has_trait("sdm.devices.traits.Info"))
    self.assertFalse(hasattr(device, 'status'))
    self.assertFalse(hasattr(device, 'custom_name'))
    self.assertFalse(hasattr(device, 'ambient_humidity_percent'))
    self.assertFalse(hasattr(device, 'ambient_temperature_celsius'))
    self.assertFalse(hasattr(device, 'custom_name'))

  def testEmptyTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertFalse(device.has_trait("sdm.devices.traits.Info"))
    self.assertFalse(hasattr(device, 'status'))
    self.assertFalse(hasattr(device, 'custom_name'))
    self.assertFalse(hasattr(device, 'ambient_humidity_percent'))
    self.assertFalse(hasattr(device, 'ambient_temperature_celsius'))
    self.assertFalse(hasattr(device, 'custom_name'))

  def testInfoTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.Info": {
           "customName": "Device Name",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
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

  def testNoParentRelations(self):
    raw = {
       "name": "my/device/name",
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual({}, device.parent_relations)

  def testEmptyParentRelations(self):
    raw = {
       "name": "my/device/name",
       "parentRelations": [ ],
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual({}, device.parent_relations)

  def testParentRelation(self):
    raw = {
       "name": "my/device/name",
       "parentRelations": [
         {
           "parent": "my/structure/or/room",
           "displayName": "Some Name",
         },
       ],
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual({"my/structure/or/room": "Some Name"},
        device.parent_relations)

  def testMultipleParentRelationis(self):
    raw = {
       "name": "my/device/name",
       "parentRelations": [
         {
           "parent": "my/structure/or/room1",
           "displayName": "Some Name1",
         },
         {
           "parent": "my/structure/or/room2",
           "displayName": "Some Name2",
         },
       ],
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertEqual({
		    "my/structure/or/room1": "Some Name1",
		    "my/structure/or/room2": "Some Name2",
		    }, device.parent_relations)
