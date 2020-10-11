from .context import google_nest_sdm

import unittest
import datetime
from google_nest_sdm.event import EventMessage


class DeviceTest(unittest.TestCase):
  def testCameraSoundEvent(self):
    raw = {
        "eventId" : "0120ecc7-3b57-4eb4-9941-91609f189fb4",
        "timestamp" : "2019-01-01T00:00:01Z",
        "resourceUpdate" : {
            "name" : "enterprises/project-id/devices/device-id",
            "events" : {
                "sdm.devices.events.CameraSound.Sound" : {
                    "eventSessionId" : "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                    "eventId" : "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
                }
            }
        },
        "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi"
    }
    event = EventMessage(raw, auth=None)
    self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
    self.assertEqual(datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc), event.timestamp)
    self.assertEqual("enterprises/project-id/devices/device-id", event.resource_update_name)
    events = event.resource_update_events
    assert "sdm.devices.events.CameraSound.Sound" in events
    e = events["sdm.devices.events.CameraSound.Sound"]
    self.assertEqual("FWWVQVUdGNUlTU2V4MGV2aTNXV...", e.event_id)
    self.assertEqual("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", e.event_session_id)

  def testCameraPersonEvent(self):
    raw = {
        "eventId" : "0120ecc7-3b57-4eb4-9941-91609f189fb4",
        "timestamp" : "2019-01-01T00:00:01Z",
        "resourceUpdate" : {
            "name" : "enterprises/project-id/devices/device-id",
            "events" : {
                "sdm.devices.events.CameraPerson.Person" : {
                    "eventSessionId" : "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                    "eventId" : "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
                }
            }
        },
        "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi"
    }
    event = EventMessage(raw, auth=None)
    self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
    self.assertEqual(datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc), event.timestamp)
    self.assertEqual("enterprises/project-id/devices/device-id", event.resource_update_name)
    events = event.resource_update_events
    assert "sdm.devices.events.CameraPerson.Person" in events
    e = events["sdm.devices.events.CameraPerson.Person"]
    self.assertEqual("FWWVQVUdGNUlTU2V4MGV2aTNXV...", e.event_id)
    self.assertEqual("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", e.event_session_id)

  def testCameraMotionEvent(self):
    raw = {
        "eventId" : "0120ecc7-3b57-4eb4-9941-91609f189fb4",
        "timestamp" : "2019-01-01T00:00:01Z",
        "resourceUpdate" : {
            "name" : "enterprises/project-id/devices/device-id",
            "events" : {
                "sdm.devices.events.CameraMotion.Motion" : {
                    "eventSessionId" : "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                    "eventId" : "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
                }
            }
        },
        "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi"
    }
    event = EventMessage(raw, auth=None)
    self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
    self.assertEqual(datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc), event.timestamp)
    self.assertEqual("enterprises/project-id/devices/device-id", event.resource_update_name)
    events = event.resource_update_events
    assert "sdm.devices.events.CameraMotion.Motion" in events
    e = events["sdm.devices.events.CameraMotion.Motion"]
    self.assertEqual("FWWVQVUdGNUlTU2V4MGV2aTNXV...", e.event_id)
    self.assertEqual("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", e.event_session_id)

  def testCameraMotionEvent(self):
    raw = {
        "eventId" : "0120ecc7-3b57-4eb4-9941-91609f189fb4",
        "timestamp" : "2019-01-01T00:00:01Z",
        "resourceUpdate" : {
            "name" : "enterprises/project-id/devices/device-id",
            "events" : {
                "sdm.devices.events.DoorbellChime.Chime" : {
                    "eventSessionId" : "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                    "eventId" : "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
                }
            }
        },
        "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi"
    }
    event = EventMessage(raw, auth=None)
    self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
    self.assertEqual(datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc), event.timestamp)
    self.assertEqual("enterprises/project-id/devices/device-id", event.resource_update_name)
    events = event.resource_update_events
    assert "sdm.devices.events.DoorbellChime.Chime" in events
    e = events["sdm.devices.events.DoorbellChime.Chime"]
    self.assertEqual("FWWVQVUdGNUlTU2V4MGV2aTNXV...", e.event_id)
    self.assertEqual("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", e.event_session_id)
