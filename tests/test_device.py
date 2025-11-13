"""Tests for device properties."""

from typing import Any, Callable, Dict

import pytest

from google_nest_sdm.device import Device

from .conftest import assert_diagnostics


def test_device_id(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.SomeDeviceType",
        }
    )
    assert "my/device/name" == device.name
    assert "sdm.devices.types.SomeDeviceType" == device.type


def test_no_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
        }
    )
    assert "my/device/name" == device.name
    assert "sdm.devices.traits.Info" not in device.traits


def test_empty_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {},
        }
    )
    assert "my/device/name" == device.name
    assert "sdm.devices.traits.Info" not in device.traits


def test_no_name(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    with pytest.raises(ValueError, match="'name' is required"):
        fake_device(
            {
                "traits": {},
            }
        )


def test_no_parent_relations(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
        }
    )
    assert "my/device/name" == device.name
    assert {} == device.parent_relations


def test_empty_parent_relations(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "parentRelations": [],
        }
    )
    assert "my/device/name" == device.name
    assert {} == device.parent_relations


def test_invalid_parent_relations(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    """Invalid parentRelations should be ignored."""
    device = fake_device(
        {
            "name": "my/device/name",
            "parentRelations": [{}],
        }
    )
    assert "my/device/name" == device.name
    assert {} == device.parent_relations


def test_parent_relation(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "parentRelations": [
                {
                    "parent": "my/structure/or/room",
                    "displayName": "Some Name",
                },
            ],
        }
    )
    assert "my/device/name" == device.name
    assert {"my/structure/or/room": "Some Name"} == device.parent_relations

    assert_diagnostics(
        device.get_diagnostics(),
        {
            "data": {
                "name": "**REDACTED**",
                "parentRelations": [
                    {
                        "parent": "**REDACTED**",
                        "displayName": "**REDACTED**",
                    }
                ],
            },
        },
    )


def test_multiple_parent_relations(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    device = fake_device(
        {
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
    )
    assert "my/device/name" == device.name
    assert {
        "my/structure/or/room1": "Some Name1",
        "my/structure/or/room2": "Some Name2",
    } == device.parent_relations
