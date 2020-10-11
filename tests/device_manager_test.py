from .context import google_nest_sdm

import unittest
import datetime
from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.event import EventMessage


def MakeDevice(raw_data: dict) -> Device:
    return Device.MakeDevice(raw_data, auth=None)


def MakeEvent(raw_data: dict) -> EventMessage:
    return EventMessage(raw_data, auth=None)


class DeviceManagerTest(unittest.TestCase):

  def testAddDevice(self):
    mgr = DeviceManager()
    mgr.add_device(MakeDevice({
       "name": "my/device/name1",
       "type": "sdm.devices.types.SomeDeviceType",
    }))
    self.assertEqual(1, len(mgr.devices))
    mgr.add_device(MakeDevice({
       "name": "my/device/name2",
       "type": "sdm.devices.types.SomeDeviceType",
    }))
    self.assertEqual(2, len(mgr.devices))

  def testDuplicateDevice(self):
    mgr = DeviceManager()
    mgr.add_device(MakeDevice({
       "name": "my/device/name1",
       "type": "sdm.devices.types.SomeDeviceType",
    }))
    self.assertEqual(1, len(mgr.devices))
    mgr.add_device(MakeDevice({
       "name": "my/device/name1",
       "type": "sdm.devices.types.SomeDeviceType",
    }))
    self.assertEqual(1, len(mgr.devices))


  def testUpdateTraits(self):
    mgr = DeviceManager()
    mgr.add_device(MakeDevice({
       "name": "my/device/name1",
       "type": "sdm.devices.types.SomeDeviceType",
       "traits": {
           "sdm.devices.traits.Connectivity": {
               "status": "OFFLINE",
           },
       },
    }))
    self.assertEqual(1, len(mgr.devices))
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    self.assertEqual("OFFLINE", trait.status)
    mgr.handle_event(MakeEvent({
        "eventId" : "0120ecc7-3b57-4eb4-9941-91609f189fb4",
        "timestamp" : "2019-01-01T00:00:01Z",
        "resourceUpdate" : {
            "name" : "my/device/name1",
            "traits": {
                "sdm.devices.traits.Connectivity": {
                    "status": "ONLINE",
                }
            }
        },
        "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi"
    }))
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    self.assertEqual("ONLINE", trait.status)

  def testDeviceCreatedInStructure(self):
    mgr = DeviceManager()
    mgr.add_device(MakeDevice({
       "name": "enterprises/project-id/devices/device-id",
       "type": "sdm.devices.types.SomeDeviceType",
       "parentRelations": []
    }))
    self.assertEqual(1, len(mgr.devices))
    device = mgr.devices["enterprises/project-id/devices/device-id"]
    self.assertEqual(0, len(device.parent_relations))

    mgr.handle_event(MakeEvent({
        "eventId" : "0120ecc7-3b57-4eb4-9941-91609f189fb4",
        "timestamp" : "2019-01-01T00:00:01Z",
        "relationUpdate": {
            "type": "CREATED",
            "subject" : "enterprises/project-id/structures/structure-id",
            "object" : "enterprises/project-id/devices/device-id",
        },
        "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi"
    }))
    device = mgr.devices["enterprises/project-id/devices/device-id"]
    self.assertEqual({
        "enterprises/project-id/structures/structure-id": "Unknown",
    }, device.parent_relations)

    mgr.handle_event(MakeEvent({
        "eventId" : "0120ecc7-3b57-4eb4-9941-91609f189fb4",
        "timestamp" : "2019-01-01T00:00:01Z",
        "relationUpdate": {
            "type": "DELETED",
            "subject" : "enterprises/project-id/structures/structure-id",
            "object" : "enterprises/project-id/devices/device-id",
        },
        "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi"
    }))
    device = mgr.devices["enterprises/project-id/devices/device-id"]
    self.assertEqual(0, len(device.parent_relations))
