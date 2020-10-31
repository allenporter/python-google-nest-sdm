from google_nest_sdm.device import Device


def test_camera_image_traits():
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
    assert "sdm.devices.traits.CameraImage" in device.traits
    trait = device.traits["sdm.devices.traits.CameraImage"]
    assert 500 == trait.max_image_resolution.width
    assert 300 == trait.max_image_resolution.height


def test_camera_live_stream_traits():
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
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert 500 == trait.max_video_resolution.width
    assert 300 == trait.max_video_resolution.height
    assert ["H264"] == trait.video_codecs
    assert ["AAC"] == trait.audio_codecs


def test_camera_event_image_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraEventImage": {},
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.CameraEventImage" in device.traits
