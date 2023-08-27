"""Library for using the Google Nest SDM API.

See https://developers.google.com/nest/device-access/api for the documentation
on how to use the API.

The primary components in this library are:
- `auth`: You need to implement `AbstractAuth` to provide credentials.
- `google_nest_subscriber`: A wrapper around the pub/sub system for efficiently
  listening to changes in device state.
- `device_manager`: Holds local state for devices, populated by the subscriber.
- `device`: Holds device traits and current device state
- `event_media`: For media related to camera or doorbell events.

Example usage:
```
    auth_impl = ... # Your impl goes here
    subscriber = GoogleNestSubscriber(auth_impl, device_access_project_id, subscriber_id)
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()

    for device in device_manager.devices.values():
        if device.temperature:
            print("Device temperature: {device.temperature.ambient_temperature_celsius}")            
```
"""

__all__ = [
    "google_nest_subscriber",
    "device_manager",
    "device",
    "camera_traits",
    "device_traits",
    "doorbell_traits",
    "thermostat_traits",
    "structure",
    "auth",
    "event_media",
    "event",
    "exceptions",
    "diagnostics",
]