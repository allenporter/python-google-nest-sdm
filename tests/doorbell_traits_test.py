from google_nest_sdm.device import Device


def test_doorbell_chime():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.DoorbellChime": {},
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.DoorbellChime" in device.traits

def test_doorbell_chime_trait_hack():
    """Adds the DoorbellChime trait even when missing from the API to fix an API bug."""
    raw = {
        "name": "my/device/name",
        "type": "sdm.devices.types.DOORBELL",
        "traits": { },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.DoorbellChime" in device.traits

def test_doorbell_chime_trait_hack_not_applied():
    """The doorbell chime trait hack is not applied for other types."""
    raw = {
        "name": "my/device/name",
        "type": "sdm.devices.types.CAMERA",
        "traits": { },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.DoorbellChime" not in device.traits
