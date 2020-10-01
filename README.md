# python-google-nest-sdm

This is a library for Google Nest [Device Access](https://developers.google.com/nest/device-access)
using the [Smart Device Management API](https://developers.google.com/nest/device-access/api).

# Usage

This can be used with the sandbox which requires [Registration](https://developers.google.com/nest/device-access/registration), accepting terms
and a fee.

You'll want to following the [Get Started](https://developers.google.com/nest/device-access/get-started)
guides for setup including steps in the google cloud console.  Overall, this is
fairly complicated with many steps that are easy to get wrong.  It is likely
worth it to make sure you can get the API working using their supplied curl
commands with your account before attempting to use this library.

# Structure

This API was designed for use in Home Assistant following the advice in
[Building a Pythong Library for an API](https://developers.home-assistant.io/docs/api_lib_index/).

If you are integrating this from outside Home Assistant, you'll need to
create your own oauth integration and token refresh mechanism and tooling.
