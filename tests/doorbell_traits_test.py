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
