from .context import google_nest_sdm

import unittest
import datetime
from google_nest_sdm.event import EventMessage


def MakeEvent(raw_data: dict) -> EventMessage:
    return EventMessage(raw_data, auth=None)


class EventTest(unittest.TestCase):
    def testCameraSoundEvent(self):
        event = MakeEvent(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "enterprises/project-id/devices/device-id",
                    "events": {
                        "sdm.devices.events.CameraSound.Sound": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
        self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
        self.assertEqual(
            datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc),
            event.timestamp,
        )
        self.assertEqual(
            "enterprises/project-id/devices/device-id", event.resource_update_name
        )
        events = event.resource_update_events
        assert "sdm.devices.events.CameraSound.Sound" in events
        e = events["sdm.devices.events.CameraSound.Sound"]
        self.assertEqual("FWWVQVUdGNUlTU2V4MGV2aTNXV...", e.event_id)
        self.assertEqual("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", e.event_session_id)

    def testCameraPersonEvent(self):
        event = MakeEvent(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "enterprises/project-id/devices/device-id",
                    "events": {
                        "sdm.devices.events.CameraPerson.Person": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
        self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
        self.assertEqual(
            datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc),
            event.timestamp,
        )
        self.assertEqual(
            "enterprises/project-id/devices/device-id", event.resource_update_name
        )
        events = event.resource_update_events
        assert "sdm.devices.events.CameraPerson.Person" in events
        e = events["sdm.devices.events.CameraPerson.Person"]
        self.assertEqual("FWWVQVUdGNUlTU2V4MGV2aTNXV...", e.event_id)
        self.assertEqual("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", e.event_session_id)

    def testCameraMotionEvent(self):
        event = MakeEvent(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "enterprises/project-id/devices/device-id",
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
        self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
        self.assertEqual(
            datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc),
            event.timestamp,
        )
        self.assertEqual(
            "enterprises/project-id/devices/device-id", event.resource_update_name
        )
        events = event.resource_update_events
        assert "sdm.devices.events.CameraMotion.Motion" in events
        e = events["sdm.devices.events.CameraMotion.Motion"]
        self.assertEqual("FWWVQVUdGNUlTU2V4MGV2aTNXV...", e.event_id)
        self.assertEqual("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", e.event_session_id)

    def testDoorbellChimeEvent(self):
        event = MakeEvent(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "enterprises/project-id/devices/device-id",
                    "events": {
                        "sdm.devices.events.DoorbellChime.Chime": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
        self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
        self.assertEqual(
            datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc),
            event.timestamp,
        )
        self.assertEqual(
            "enterprises/project-id/devices/device-id", event.resource_update_name
        )
        events = event.resource_update_events
        assert "sdm.devices.events.DoorbellChime.Chime" in events
        e = events["sdm.devices.events.DoorbellChime.Chime"]
        self.assertEqual("FWWVQVUdGNUlTU2V4MGV2aTNXV...", e.event_id)
        self.assertEqual("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", e.event_session_id)

    def testRelation(self):
        event = MakeEvent(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "relationUpdate": {
                    "type": "CREATED",
                    "subject": "enterprises/project-id/structures/structure-id",
                    "object": "enterprises/project-id/devices/device-id",
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
        self.assertEqual("0120ecc7-3b57-4eb4-9941-91609f189fb4", event.event_id)
        self.assertEqual(
            datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc),
            event.timestamp,
        )
        self.assertTrue(event.resource_update_name is None)
        self.assertTrue(event.resource_update_events is None)
        self.assertTrue(event.resource_update_traits is None)
        update = event.relation_update
        self.assertEqual("CREATED", update.type)
        self.assertEqual(
            "enterprises/project-id/structures/structure-id", update.subject
        )
        self.assertEqual("enterprises/project-id/devices/device-id", update.object)
