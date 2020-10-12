"""Traits for thermostats."""
from .traits import TRAIT_MAP, Command

STATUS = "status"
AVAILABLE_MODES = "availableModes"
MODE = "mode"
HEAT_CELSIUS = "heatCelsius"
COOL_CELSIUS = "coolCelsius"


@TRAIT_MAP.register()
class ThermostatEcoTrait:
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME = "sdm.devices.traits.ThermostatEco"

    def __init__(self, data: dict, cmd: Command):
        """Initialize ThermostatEcoTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def available_modes(self) -> list:
        """List of supported Eco modes."""
        return self._data[AVAILABLE_MODES]

    @property
    def mode(self) -> str:
        """The current Eco mode of the thermostat."""
        return self._data[MODE]

    async def set_mode(self, mode):
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatEco.SetMode",
            "params": {"mode": mode},
        }
        return await self._cmd.execute(data)

    @property
    def heat_celsius(self) -> float:
        """Lowest temperature where Eco mode begins heating."""
        return self._data[HEAT_CELSIUS]

    @property
    def cool_celsius(self) -> float:
        """Highest cooling temperature where Eco mode begins cooling."""
        return self._data[COOL_CELSIUS]


@TRAIT_MAP.register()
class ThermostatHvacTrait:
    """This trait belongs to devices that can report HVAC details."""

    NAME = "sdm.devices.traits.ThermostatHvac"

    def __init__(self, data: dict, cmd: Command):
        """Initialize ThermostatHvacTrait."""
        self._data = data

    @property
    def status(self) -> list:
        """Current HVAC status of the thermostat."""
        return self._data[STATUS]


@TRAIT_MAP.register()
class ThermostatModeTrait:
    """This trait belongs to devices that support different thermostat modes."""

    NAME = "sdm.devices.traits.ThermostatMode"

    def __init__(self, data: dict, cmd: Command):
        """Initialize ThermostatModeTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def available_modes(self) -> list:
        """List of supported thermostat modes."""
        return self._data[AVAILABLE_MODES]

    @property
    def mode(self) -> str:
        """The current mode of the thermostat."""
        return self._data[MODE]

    async def set_mode(self, mode):
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatMode.SetMode",
            "params": {"mode": mode},
        }
        return await self._cmd.execute(data)


@TRAIT_MAP.register()
class ThermostatTemperatureSetpointTrait:
    """This trait belongs to devices that support setting target temperature."""

    NAME = "sdm.devices.traits.ThermostatTemperatureSetpoint"

    def __init__(self, data: dict, cmd: Command):
        """Initialize ThermostatTemperatureSetpointTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def heat_celsius(self) -> float:
        """Lowest temperature where Eco mode begins heating."""
        return self._data[HEAT_CELSIUS]

    @property
    def cool_celsius(self) -> list:
        """Highest cooling temperature where Eco mode begins cooling."""
        return self._data[COOL_CELSIUS]

    async def set_heat(self, heat: float):
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
            "params": {"heatCelsius": heat},
        }
        return await self._cmd.execute(data)

    async def set_cool(self, cool: float):
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
            "params": {"coolCelsius": cool},
        }
        return await self._cmd.execute(data)

    async def set_range(self, heat: float, cool: float):
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
            "params": {
                "heatCelsius": heat,
                "coolCelsius": cool,
            },
        }
        return await self._cmd.execute(data)
