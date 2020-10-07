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

# Fetching Data

This is an example to use the command line tool to access the API:

```
PROJECT_ID="some-project-id"
CLIEND_ID="some-client-id"
CLIENT_SECRET="some-client-secret"
# Initial call will ask you to authorize OAuth2 then cache the token
google_nest --project_id="${PROJECT_ID}" --client_id="${CLIENT_ID}" --client_secret="${CLIENT_SECRET}" list
# Subsequent calls only need the project id
google_nest --project_id="${PROJECT_ID}" get "some-device-id"
google_nest --project_id="${PROJECT_ID}" set_mode COOL
google_nest --project_id="${PROJECT_ID}" set_cool 25.0
```

# Subscriptions

See [Device Access: Getting Started: Subscribe to Events](https://developers.google.com/nest/device-access/subscribe-to-events)
for documentation on how to create a pull subscription.

You can create the subscription to use with the tool with these steps:

* Create the topic:
  * Visit the [Device Access Console](https://console.nest.google.com/device-access)
  * Select a project
  * Enable Pub/Sub and note the full `topic` based on the `project_id`
* Create the subscriber:
  * Visit [Google Cloud Platform: Pub/Sub: Subscriptions](https://console.cloud.google.com/cloudpubsub/subscriptions)
  * Create a subscriber
  * Enter the `Topic Name`
  * Create a `Subscription Name`, e.g. "project-id-python" which is your `subscriber_id`

This is an example to run the command line tool to subscribe:
```
PROJECT_ID="some-project-id"
SUBSCRIPTION_ID="projects/some-id/subscriptions/enterprise-some-project-id-python-google-nest"
google_nest --project_id="${PROJECT_ID}" subscribe ${SUBSCRIPTION_ID}
```

# Funding and Support

If you are interested in donating money to this effort, instead send a
donation to [Black Girls Code](https://donorbox.org/support-black-girls-code)
which is a great organization growing the next generation of software engineers.
