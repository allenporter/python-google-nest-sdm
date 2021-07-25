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
    assert "sdm.devices.traits.DoorbellChime" in device.traits


def test_doorbell_chime_trait_hack(
    fake_device: Callable[[Dict[str, Any]], Device]
) -> None:
    """Adds the DoorbellChime trait even when missing from the API to fix an API bug."""
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.DOORBELL",
            "traits": {},
        }
    )
    assert "sdm.devices.traits.DoorbellChime" in device.traits


def test_doorbell_chime_trait_hack_not_applied(
    fake_device: Callable[[Dict[str, Any]], Device]
) -> None:
    """The doorbell chime trait hack is not applied for other types."""
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.CAMERA",
            "traits": {},
        }
    )
    assert "sdm.devices.traits.DoorbellChime" not in device.traits
