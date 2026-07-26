from __future__ import annotations

import base64
import datetime
import json
from typing import Any, Callable, Dict, Optional

import pytest

from google_nest_sdm.event import (
    CameraClipPreviewEvent,
    EventImageType,
    EventMessage,
    EventToken,
    ImageEventBase,
)
from google_nest_sdm.exceptions import DecodeException


def test_camera_sound_event(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    event = fake_event_message(
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
    assert "0120ecc7-3b57-4eb4-9941-91609f189fb4" == event.event_id
    ts = datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)

    assert ts == event.timestamp
    assert "enterprises/project-id/devices/device-id" == event.resource_update_name
    events = event.resource_update_events
    assert events is not None
    assert "sdm.devices.events.CameraSound.Sound" in events
    e = events["sdm.devices.events.CameraSound.Sound"]
    assert "FWWVQVUdGNUlTU2V4MGV2aTNXV..." == e.event_id
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." == e.event_session_id
    assert ts == e.timestamp
    expire_ts = datetime.datetime(2019, 1, 1, 0, 0, 31, tzinfo=datetime.timezone.utc)
    assert expire_ts == e.expires_at


def test_camera_person_event(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    event = fake_event_message(
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
    assert "0120ecc7-3b57-4eb4-9941-91609f189fb4" == event.event_id
    assert (
        datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
        == event.timestamp
    )
    assert "enterprises/project-id/devices/device-id" == event.resource_update_name
    events = event.resource_update_events
    assert events is not None
    assert "sdm.devices.events.CameraPerson.Person" in events
    e = events["sdm.devices.events.CameraPerson.Person"]
    assert "FWWVQVUdGNUlTU2V4MGV2aTNXV..." == e.event_id
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." == e.event_session_id


def test_camera_motion_event(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    event = fake_event_message(
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
    assert "0120ecc7-3b57-4eb4-9941-91609f189fb4" == event.event_id
    assert (
        datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
        == event.timestamp
    )
    assert "enterprises/project-id/devices/device-id" == event.resource_update_name
    events = event.resource_update_events
    assert events is not None
    assert "sdm.devices.events.CameraMotion.Motion" in events
    e = events["sdm.devices.events.CameraMotion.Motion"]
    assert "FWWVQVUdGNUlTU2V4MGV2aTNXV..." == e.event_id
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." == e.event_session_id


def test_doorbell_chime_event(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    event = fake_event_message(
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
    assert "0120ecc7-3b57-4eb4-9941-91609f189fb4" == event.event_id
    assert (
        datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
        == event.timestamp
    )
    assert "enterprises/project-id/devices/device-id" == event.resource_update_name
    events = event.resource_update_events
    assert events is not None
    assert "sdm.devices.events.DoorbellChime.Chime" in events
    e = events["sdm.devices.events.DoorbellChime.Chime"]
    assert "FWWVQVUdGNUlTU2V4MGV2aTNXV..." == e.event_id
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." == e.event_session_id


def test_relation(fake_event_message: Callable[[Dict[str, Any]], EventMessage]) -> None:
    event = fake_event_message(
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
    assert "0120ecc7-3b57-4eb4-9941-91609f189fb4" == event.event_id
    assert (
        datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
        == event.timestamp
    )
    assert event.resource_update_name is None
    assert event.resource_update_events is None
    assert event.resource_update_traits is None
    update = event.relation_update
    assert update is not None
    assert "CREATED" == update.type
    assert "enterprises/project-id/structures/structure-id" == update.subject
    assert "enterprises/project-id/devices/device-id" == update.object


def test_camera_clip_preview_event(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    event = fake_event_message(
        {
            "eventId": "201fcd21-967a-4f82-8082-5073bd09d31f",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "enterprises/project-id/devices/device-id",
                "events": {
                    "sdm.devices.events.CameraClipPreview.ClipPreview": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "previewUrl": "https://previewUrl/...",
                    }
                },
            },
            "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
        }
    )
    assert "201fcd21-967a-4f82-8082-5073bd09d31f" == event.event_id
    ts = datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)

    assert ts == event.timestamp
    assert "enterprises/project-id/devices/device-id" == event.resource_update_name

    events: Optional[Dict[str, ImageEventBase]] = event.resource_update_events
    assert events is not None
    assert "sdm.devices.events.CameraClipPreview.ClipPreview" in events
    e = events["sdm.devices.events.CameraClipPreview.ClipPreview"]
    assert isinstance(e, CameraClipPreviewEvent)
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." == e.event_session_id
    assert ts == e.timestamp
    assert (
        "1cd28a21db0705a03f612d1df956444094a8c85a75fd35dfd277a81b5a9ad2a8c18"
        "2a9a7decb2936664d6e1344915850a31fc3c828c3813765d1c73be1e958f3" == e.event_id
    )
    assert "https://previewUrl/..." == e.preview_url
    expire_ts = datetime.datetime(2019, 1, 1, 0, 15, 1, tzinfo=datetime.timezone.utc)
    assert expire_ts == e.expires_at


def test_event_serialization(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    event = fake_event_message(
        {
            "eventId": "201fcd21-967a-4f82-8082-5073bd09d31f",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "enterprises/project-id/devices/device-id",
                "events": {
                    "sdm.devices.events.CameraClipPreview.ClipPreview": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "previewUrl": "https://previewUrl/...",
                    }
                },
            },
            "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
        }
    )
    assert "201fcd21-967a-4f82-8082-5073bd09d31f" == event.event_id
    ts = datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)

    assert ts == event.timestamp
    assert "enterprises/project-id/devices/device-id" == event.resource_update_name

    events: Optional[Dict[str, ImageEventBase]] = event.resource_update_events
    assert events is not None
    assert "sdm.devices.events.CameraClipPreview.ClipPreview" in events
    e: ImageEventBase | None = events[
        "sdm.devices.events.CameraClipPreview.ClipPreview"
    ]
    assert e
    assert isinstance(e, CameraClipPreviewEvent)

    # Serialize the event then unserialize and veirfy everything is still correct
    data = e.as_dict()
    dump = json.dumps(data)
    data = json.loads(dump)

    e = ImageEventBase.parse_event_dict(data)
    assert e
    assert isinstance(e, CameraClipPreviewEvent)

    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." == e.event_session_id
    assert ts == e.timestamp
    assert (
        "1cd28a21db0705a03f612d1df956444094a8c85a75fd35dfd277a81b5a9ad2a8c18"
        "2a9a7decb2936664d6e1344915850a31fc3c828c3813765d1c73be1e958f3" == e.event_id
    )
    assert "https://previewUrl/..." == e.preview_url
    expire_ts = datetime.datetime(2019, 1, 1, 0, 15, 1, tzinfo=datetime.timezone.utc)
    assert expire_ts == e.expires_at


def test_update_from_events(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    event = fake_event_message(
        {
            "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "enterprises/project-id/devices/device-id",
                "events": {
                    "sdm.devices.events.CameraSound.Sound": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                    },
                    "sdm.devices.events.CameraMotion.Motion": {
                        "eventSessionId": "DkX5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "EXXVQVUdGNUlTU2V4MGV2aTNXV...",
                    },
                    "sdm.devices.events.CameraPerson.Person": {
                        "eventSessionId": "EjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FZZVQVUdGNUlTU2V4MGV2aTNXV...",
                    },
                },
            },
            "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
        }
    )

    event = event.with_events(
        set({"sdm.devices.events.CameraMotion.Motion", "not-found"})
    )
    assert "0120ecc7-3b57-4eb4-9941-91609f189fb4" == event.event_id
    ts = datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)

    assert ts == event.timestamp
    assert "enterprises/project-id/devices/device-id" == event.resource_update_name
    events = event.resource_update_events
    assert events is not None
    assert len(events) == 1
    assert "sdm.devices.events.CameraMotion.Motion" in events
    e = events["sdm.devices.events.CameraMotion.Motion"]
    assert "EXXVQVUdGNUlTU2V4MGV2aTNXV..." == e.event_id
    assert "DkX5Y3VKaTZwR3o4Y19YbTVfMF..." == e.event_session_id
    assert ts == e.timestamp
    expire_ts = datetime.datetime(2019, 1, 1, 0, 0, 31, tzinfo=datetime.timezone.utc)
    assert expire_ts == e.expires_at
    event_token = EventToken.decode(e.event_token)
    assert event_token.event_id == "EXXVQVUdGNUlTU2V4MGV2aTNXV..."
    assert event_token.event_session_id == "DkX5Y3VKaTZwR3o4Y19YbTVfMF..."

    event = event.with_events(set(["unknown"]))
    events = event.resource_update_events
    assert not events


def test_event_image_type() -> None:
    """Test for EventImageType."""
    assert (
        EventImageType.from_string(str(EventImageType.CLIP_PREVIEW))
        == EventImageType.CLIP_PREVIEW
    )
    assert EventImageType.from_string(str(EventImageType.IMAGE)) == EventImageType.IMAGE
    assert EventImageType.from_string("video/mp4") == EventImageType.CLIP_PREVIEW
    assert EventImageType.from_string("image/jpeg") == EventImageType.IMAGE

    assert EventImageType.from_string("image/gif") != EventImageType.IMAGE
    assert EventImageType.from_string("image/gif") == EventImageType.IMAGE_PREVIEW
    assert EventImageType.from_string("image/gif").content_type == "image/gif"
    assert EventImageType.from_string("other").content_type == "other"


def test_event_token() -> None:
    """Test for an EventToken."""
    token = EventToken("session-id", "event-id")
    assert token.event_session_id == "session-id"
    assert token.event_id == "event-id"
    encoded_token = token.encode()
    decoded_token = EventToken.decode(encoded_token)
    assert decoded_token.event_session_id == "session-id"
    assert decoded_token.event_id == "event-id"


def test_decode_token_failure() -> None:
    """Test failure to decode an event token."""
    with pytest.raises(DecodeException):
        EventToken.decode("some-bogus-token")


def test_decode_token_failure_items() -> None:
    """Test failure to decode an event token."""
    data = ["wrong type"]
    b = json.dumps(data).encode("utf-8")
    token = base64.b64encode(b).decode("utf-8")
    with pytest.raises(DecodeException):
        EventToken.decode(token)


def test_decode_token_failure_dict() -> None:
    """Test failure to decode an event token."""
    data = {"a": "b", "c": "d"}
    b = json.dumps(data).encode("utf-8")
    token = base64.b64encode(b).decode("utf-8")
    with pytest.raises(DecodeException):
        EventToken.decode(token)


def test_event_zone(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    event = fake_event_message(
        {
            "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "enterprises/project-id/devices/device-id",
                "events": {
                    "sdm.devices.events.CameraPerson.Person": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        "zones": ["Zone 1"],
                    }
                },
            },
            "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
        }
    )
    assert "0120ecc7-3b57-4eb4-9941-91609f189fb4" == event.event_id
    assert (
        datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
        == event.timestamp
    )
    assert "enterprises/project-id/devices/device-id" == event.resource_update_name
    events = event.resource_update_events
    assert events is not None
    assert "sdm.devices.events.CameraPerson.Person" in events
    e = events["sdm.devices.events.CameraPerson.Person"]
    assert "FWWVQVUdGNUlTU2V4MGV2aTNXV..." == e.event_id
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." == e.event_session_id
    assert e.zones == ["Zone 1"]


def test_unknown_event_type(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    """Test at event published with a type that is not recognized."""
    event = fake_event_message(
        {
            "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "enterprises/project-id/devices/device-id",
                "events": {
                    "sdm.devices.events.Ignored.EventType": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                    }
                },
            },
            "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
        }
    )
    assert event.event_id == "0120ecc7-3b57-4eb4-9941-91609f189fb4"
    assert event.timestamp == datetime.datetime(
        2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc
    )
    assert event.resource_update_name == "enterprises/project-id/devices/device-id"
    assert event.resource_update_events == {}


def test_event_message_repr(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    """Test at event published with a type that is not recognized."""
    event = fake_event_message(
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
    assert "EventMessage{" in repr(event)
    assert event.resource_update_events
    assert "sdm.devices.events.CameraMotion.Motion" in event.resource_update_events
    motion = event.resource_update_events["sdm.devices.events.CameraMotion.Motion"]
    assert motion
    assert "CameraMotionEvent(" in repr(motion)


def test_missing_preview_url(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    with pytest.raises(ValueError, match="EventMessage has invalid value"):
        fake_event_message(
            {
                "eventId": "201fcd21-967a-4f82-8082-5073bd09d31f",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "enterprises/project-id/devices/device-id",
                    "events": {
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
