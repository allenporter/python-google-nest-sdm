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
    subscriber = GoogleNestSubscriber(
        auth_impl, # Your credential provider
        # Follow nest developer API docs to obtain these
        DEVICE_ACCESS_PROJECT_ID,
        SUBSCRIBER_ID,
    )
    unsub = await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()

    for device in device_manager.devices.values():
        if device.temperature:
            temp = device.temperatureambient_temperature_celsius
            print("Device temperature: {temp:0.2f}")

    unsub()  # Unsubscribe when done
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
