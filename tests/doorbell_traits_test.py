"""Tests for doorbell traits."""


def test_doorbell_chime(fake_device):
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.DoorbellChime": {},
            },
        }
    )
    assert "sdm.devices.traits.DoorbellChime" in device.traits


def test_doorbell_chime_trait_hack(fake_device):
    """Adds the DoorbellChime trait even when missing from the API to fix an API bug."""
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.DOORBELL",
            "traits": {},
        }
    )
    assert "sdm.devices.traits.DoorbellChime" in device.traits


def test_doorbell_chime_trait_hack_not_applied(fake_device):
    """The doorbell chime trait hack is not applied for other types."""
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.CAMERA",
            "traits": {},
        }
    )
    assert "sdm.devices.traits.DoorbellChime" not in device.traits
