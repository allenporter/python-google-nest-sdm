from google_nest_sdm.device import Device


def test_device_id():
    raw = {
        "name": "my/device/name",
        "type": "sdm.devices.types.SomeDeviceType",
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert "sdm.devices.types.SomeDeviceType" == device.type


def test_no_traits():
    raw = {
        "name": "my/device/name",
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert not ("sdm.devices.traits.Info" in device.traits)


def test_empty_traits():
    raw = {
        "name": "my/device/name",
        "traits": {},
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert not ("sdm.devices.traits.Info" in device.traits)


def test_no_parent_relations():
    raw = {
        "name": "my/device/name",
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert {} == device.parent_relations


def test_empty_parent_relations():
    raw = {
        "name": "my/device/name",
        "parentRelations": [],
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert {} == device.parent_relations


def test_parent_relation():
    raw = {
        "name": "my/device/name",
        "parentRelations": [
            {
                "parent": "my/structure/or/room",
                "displayName": "Some Name",
            },
        ],
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert {"my/structure/or/room": "Some Name"} == device.parent_relations


def test_multiple_parent_relations():
    raw = {
        "name": "my/device/name",
        "parentRelations": [
            {
                "parent": "my/structure/or/room1",
                "displayName": "Some Name1",
            },
            {
                "parent": "my/structure/or/room2",
                "displayName": "Some Name2",
            },
        ],
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert {
        "my/structure/or/room1": "Some Name1",
        "my/structure/or/room2": "Some Name2",
    } == device.parent_relations
