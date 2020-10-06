# Scaffolding for local test development
from .context import google_nest_sdm

import unittest
from google_nest_sdm.device import (
    Device,
    ThermostatEcoTrait,
    ThermostatHvacTrait,
    ThermostatModeTrait,
    ThermostatTemperatureSetpointTrait
)


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
    self.assertFalse("sdm.devices.traits.Info" in device.traits)

  def testEmptyTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertEqual("my/device/name", device.name)
    self.assertFalse("sdm.devices.traits.Info" in device.traits)

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
    self.assertTrue("sdm.devices.traits.Info" in device.traits)
    trait = device.traits["sdm.devices.traits.Info"]
    self.assertEqual("Device Name", trait.custom_name)

  def testConnectivityTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.Connectivity": {
           "status": "OFFLINE",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.Connectivity" in device.traits)
    trait = device.traits["sdm.devices.traits.Connectivity"]
    self.assertEqual("OFFLINE", trait.status)

  def testHumidityTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.Humidity": {
           "ambientHumidityPercent": "25.3",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.Humidity" in device.traits)
    trait = device.traits["sdm.devices.traits.Humidity"]
    self.assertEqual("25.3", trait.ambient_humidity_percent)

  def testTemperatureTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.Temperature": {
           "ambientTemperatureCelsius": "31.1",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.Temperature" in device.traits)
    trait = device.traits["sdm.devices.traits.Temperature"]
    self.assertEqual("31.1", trait.ambient_temperature_celsius)

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
    self.assertTrue("sdm.devices.traits.Info" in device.traits)
    trait = device.traits["sdm.devices.traits.Info"]
    self.assertEqual("Device Name", trait.custom_name)
    self.assertTrue("sdm.devices.traits.Connectivity" in device.traits)
    trait = device.traits["sdm.devices.traits.Connectivity"]
    self.assertEqual("OFFLINE", trait.status)

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

  def testMultipleParentRelations(self):
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


  def testThermostatEcoTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.ThermostatEco": {
           "availableModes": ["MANUAL_ECHO", "OFF"],
           "mode": "MANUAL_ECHO",
           "heatCelsius": 20.0,
           "coolCelsius": 22.0,
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.ThermostatEco" in device.traits)
    trait = device.traits["sdm.devices.traits.ThermostatEco"]
    self.assertEqual(["MANUAL_ECHO", "OFF"], trait.available_modes)
    self.assertEqual("MANUAL_ECHO", trait.mode)
    self.assertEqual(20.0, trait.heat_celsius)
    self.assertEqual(22.0, trait.cool_celsius)

  def testThermostatHvacTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.ThermostatHvac": {
           "status": "HEATING",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.ThermostatHvac" in device.traits)
    trait = device.traits["sdm.devices.traits.ThermostatHvac"]
    self.assertEqual("HEATING", trait.status)

  def testThermostatModeTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.ThermostatMode": {
           "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
           "mode": "COOL",
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.ThermostatMode" in device.traits)
    trait = device.traits["sdm.devices.traits.ThermostatMode"]
    self.assertEqual(["HEAT", "COOL", "HEATCOOL", "OFF"], trait.available_modes)
    self.assertEqual("COOL", trait.mode)

  def testThermostatTemperatureSetpointTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.ThermostatTemperatureSetpoint": {
           "heatCelsius": 20.0,
           "coolCelsius": 22.0,
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.ThermostatTemperatureSetpoint" in device.traits)
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    self.assertEqual(20.0, trait.heat_celsius)
    self.assertEqual(22.0, trait.cool_celsius)

  def testThermostatMultipleTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.ThermostatEco": {
           "availableModes": ["MANUAL_ECHO", "OFF"],
           "mode": "MANUAL_ECHO",
           "heatCelsius": 21.0,
           "coolCelsius": 22.0,
         },
         "sdm.devices.traits.ThermostatHvac": {
           "status": "HEATING",
         },
         "sdm.devices.traits.ThermostatMode": {
           "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
           "mode": "COOL",
         },
         "sdm.devices.traits.ThermostatTemperatureSetpoint": {
           "heatCelsius": 23.0,
           "coolCelsius": 24.0,
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.ThermostatEco" in device.traits)
    self.assertTrue("sdm.devices.traits.ThermostatHvac" in device.traits)
    self.assertTrue("sdm.devices.traits.ThermostatMode" in device.traits)
    self.assertTrue("sdm.devices.traits.ThermostatTemperatureSetpoint" in device.traits)
    trait = device.traits["sdm.devices.traits.ThermostatEco"]
    self.assertEqual(["MANUAL_ECHO", "OFF"], trait.available_modes)
    self.assertEqual("MANUAL_ECHO", trait.mode)
    self.assertEqual(21.0, trait.heat_celsius)
    self.assertEqual(22.0, trait.cool_celsius)
    trait = device.traits["sdm.devices.traits.ThermostatHvac"]
    self.assertEqual("HEATING", trait.status)
    trait = device.traits["sdm.devices.traits.ThermostatMode"]
    self.assertEqual(["HEAT", "COOL", "HEATCOOL", "OFF"], trait.available_modes)
    self.assertEqual("COOL", trait.mode)
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    self.assertEqual(23.0, trait.heat_celsius)
    self.assertEqual(24.0, trait.cool_celsius)

  def testCameraImageTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.CameraImage": {
           "maxImageResolution": {
               "width": 500,
               "height": 300,
           }
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.CameraImage" in device.traits)
    trait = device.traits["sdm.devices.traits.CameraImage"]
    self.assertEqual(500, trait.max_image_resolution.width)
    self.assertEqual(300, trait.max_image_resolution.height)

  def testCameraLiveStreamTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.CameraLiveStream": {
           "maxVideoResolution": {
               "width": 500,
               "height": 300,
           },
           "videoCodecs": ["H264"],
           "audioCodecs": ["AAC"],
         },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.CameraLiveStream" in device.traits)
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    self.assertEqual(500, trait.max_video_resolution.width)
    self.assertEqual(300, trait.max_video_resolution.height)
    self.assertEqual(["H264"], trait.video_codecs)
    self.assertEqual(["AAC"], trait.audio_codecs)

  def testCameraEventImageTraits(self):
    raw = {
       "name": "my/device/name",
       "traits": {
         "sdm.devices.traits.CameraEventImage": { },
       },
    }
    device = Device.MakeDevice(raw, auth=None)
    self.assertTrue("sdm.devices.traits.CameraEventImage" in device.traits)
