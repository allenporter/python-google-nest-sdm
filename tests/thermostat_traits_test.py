"""Tests for thermostat traits."""


def test_thermostat_eco_traits(fake_device):
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.ThermostatEco": {
                    "availableModes": ["MANUAL_ECHO", "OFF"],
                    "mode": "MANUAL_ECHO",
                    "heatCelsius": 20.0,
                    "coolCelsius": 22.0,
                },
            },
        }
    )
    assert "sdm.devices.traits.ThermostatEco" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatEco"]
    assert ["MANUAL_ECHO", "OFF"] == trait.available_modes
    assert "MANUAL_ECHO" == trait.mode
    assert 20.0 == trait.heat_celsius
    assert 22.0 == trait.cool_celsius


def test_thermostat_hvac_traits(fake_device):
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.ThermostatHvac": {
                    "status": "HEATING",
                },
            },
        }
    )
    assert "sdm.devices.traits.ThermostatHvac" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatHvac"]
    assert "HEATING" == trait.status


def test_thermostat_mode_traits(fake_device):
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.ThermostatMode": {
                    "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                    "mode": "COOL",
                },
            },
        }
    )
    assert "sdm.devices.traits.ThermostatMode" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatMode"]
    assert ["HEAT", "COOL", "HEATCOOL", "OFF"] == trait.available_modes
    assert "COOL" == trait.mode


def test_thermostat_temperature_setpoint_traits(fake_device):
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                    "heatCelsius": 20.0,
                    "coolCelsius": 22.0,
                },
            },
        }
    )
    assert "sdm.devices.traits.ThermostatTemperatureSetpoint" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert 20.0 == trait.heat_celsius
    assert 22.0 == trait.cool_celsius


def test_thermostat_multiple_traits(fake_device):
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.ThermostatEco": {
                    "availableModes": ["MANUAL_ECHO", "OFF"],
                    "mode": "MANUAL_ECHO",
                    "heatCelsius": 21.0,
                    "coolCelsius": 22.0,
                },
                "sdm.devices.traits.ThermostatHvac": {
                    "status": "HEATING",
                },
                "sdm.devices.traits.ThermostatMode": {
                    "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                    "mode": "COOL",
                },
                "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                    "heatCelsius": 23.0,
                    "coolCelsius": 24.0,
                },
            },
        }
    )
    assert "sdm.devices.traits.ThermostatEco" in device.traits
    assert "sdm.devices.traits.ThermostatHvac" in device.traits
    assert "sdm.devices.traits.ThermostatMode" in device.traits
    assert "sdm.devices.traits.ThermostatTemperatureSetpoint" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatEco"]
    assert ["MANUAL_ECHO", "OFF"] == trait.available_modes
    assert "MANUAL_ECHO" == trait.mode
    assert 21.0 == trait.heat_celsius
    assert 22.0 == trait.cool_celsius
    trait = device.traits["sdm.devices.traits.ThermostatHvac"]
    assert "HEATING" == trait.status
    trait = device.traits["sdm.devices.traits.ThermostatMode"]
    assert ["HEAT", "COOL", "HEATCOOL", "OFF"] == trait.available_modes
    assert "COOL" == trait.mode
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert 23.0 == trait.heat_celsius
    assert 24.0 == trait.cool_celsius
