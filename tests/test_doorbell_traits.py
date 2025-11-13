"""Tests for doorbell traits."""

from typing import Any, Callable, Dict

from google_nest_sdm.device import Device


def test_doorbell_chime(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.DoorbellChime": {},
            },
        }
    )
    assert device.traits.keys() == {"sdm.devices.traits.DoorbellChime"}


def test_doorbell_chime_trait_hack(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    """Adds the DoorbellChime trait even when missing from the API to fix an API bug."""
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.DOORBELL",
            "traits": {},
        }
    )
    assert device.type == "sdm.devices.types.DOORBELL"
    assert device.traits.keys() == {"sdm.devices.traits.DoorbellChime"}


def test_doorbell_chime_trait_hack_empty_traits(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    """Adds the DoorbellChime trait even when missing from the API to fix an API bug."""
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.DOORBELL",
        }
    )
    assert device.type == "sdm.devices.types.DOORBELL"
    assert device.traits.keys() == {"sdm.devices.traits.DoorbellChime"}


def test_doorbell_chime_trait_hack_not_applied(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    """The doorbell chime trait hack is not applied for other types."""
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.CAMERA",
            "traits": {},
        }
    )
    assert device.type == "sdm.devices.types.CAMERA"
    assert device.traits.keys() == set()
