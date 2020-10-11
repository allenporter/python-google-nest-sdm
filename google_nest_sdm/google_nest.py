#!/usr/bin/python3

"""Command line tool for the Google Nest Smart Device Management API

You must configure your device as described:
  https://developers.google.com/nest/device-access/get-started

which will give you a project_id, client_id, and client_secret.  This tool
will do a one time setup to get an access token, then from there on will
cache the token on local disk.

Once authenticated, you can run commands like:

$ google_nest --project_id=<project_id> list
$ google_nest --project_id=<project_id> get <device_id>
"""

import argparse
import asyncio
import errno
import json
import logging
import os
import pickle

from aiohttp import ClientSession
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.cloud import pubsub_v1
from google_auth_oauthlib.flow import InstalledAppFlow

from .auth import AbstractAuth
from .thermostat_traits import (
    ThermostatEcoTrait,
    ThermostatModeTrait,
    ThermostatTemperatureSetpointTrait,
)
from .camera_traits import CameraLiveStreamTrait
from .google_nest_api import GoogleNestAPI
from .event import EventMessage
from .google_nest_subscriber import EventCallback, GoogleNestSubscriber

# Define command line arguments
parser = argparse.ArgumentParser(
    description='Command line tool for Google Nest SDM API')
parser.add_argument('--project_id', required=True,
    help='Device Access program id')
parser.add_argument('--client_id', help='OAuth credentials client_id')
parser.add_argument('--client_secret',
    help='OAuth credentials client_secret')
parser.add_argument('--token_cache',
    help='File storage for long lived creds',
    default='~/.config/google_nest/token_cache')
parser.add_argument("-v", "--verbose", help="Increase output verbosity",
    action="store_true")

cmd_parser = parser.add_subparsers(dest='command', required=True)
list_structures_parser = cmd_parser.add_parser('list_structures')
list_devices_parser = cmd_parser.add_parser('list_devices')
get_structure_parser = cmd_parser.add_parser('get_structure')
get_structure_parser.add_argument('structure_id')
get_device_parser = cmd_parser.add_parser('get_device')
get_device_parser.add_argument('device_id')
set_mode_parser = cmd_parser.add_parser('set_mode',
    description='Change the thermostat mode.')
set_mode_parser.add_argument('device_id')
set_mode_parser.add_argument('mode',
    help='The mode to change the thermostat to.',
    choices=['MANUAL_ECO','HEAT','COOL','HEATCOOL','OFF'])
set_heat_parser = cmd_parser.add_parser('set_heat',
    description='Sets the target temperature when in HEAT mode.')
set_heat_parser.add_argument('device_id')
set_heat_parser.add_argument('heat', type=float)
set_cool_parser = cmd_parser.add_parser('set_cool',
    help='Sets the target temperature when in COOL mode.')
set_cool_parser.add_argument('device_id')
set_cool_parser.add_argument('cool', type=float,
    help='The target temperature to set when the thermostat is in COOL mode.')
set_range_parser = cmd_parser.add_parser('set_range',
    help='Sets the min/max temperature when in HEATCOOL mode.')
set_range_parser.add_argument('device_id')
set_range_parser.add_argument('heat', type=float,
    help='The minimum target temperature to set.')
set_range_parser.add_argument('cool', type=float,
    help='The maximum target temperature to set.')
generate_rtsp_stream_parser = cmd_parser.add_parser('generate_rtsp_stream')
generate_rtsp_stream_parser.add_argument('device_id')
subscribe_parser = cmd_parser.add_parser('subscribe')
subscribe_parser.add_argument('subscription_id')

OAUTH2_AUTHORIZE = (
    "https://nestservices.google.com/partnerconnections/{project_id}/auth"
)
OAUTH2_TOKEN = "https://www.googleapis.com/oauth2/v4/token"
SDM_SCOPES = [
    "https://www.googleapis.com/auth/sdm.service",
    "https://www.googleapis.com/auth/pubsub",
]
API_URL = "https://smartdevicemanagement.googleapis.com/v1"


class Auth(AbstractAuth):
    """Implementation of AbstractAuth that uses the token cache."""

    def __init__(
        self,
        websession: ClientSession,
        creds: Credentials,
        api_url: str,
    ):
        """Initialize Google Nest Device Access auth."""
        super().__init__(websession, api_url)
        self._creds = creds

    async def async_get_access_token(self):
        """Return a valid access token."""
        return self._creds.token

    async def async_get_creds(self):
        return self._creds


def CreateCreds(args) -> Credentials:
  """Runs an interactive flow to get OAuth creds."""
  creds = None
  token_cache = os.path.expanduser(args.token_cache)
  if os.path.exists(token_cache):
    with open(token_cache, 'rb') as token:
      creds = pickle.load(token)

  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      if not args.client_id or not args.client_secret:
        raise ValueError("Required flag --client_id or --client_secret missing")
      client_config = {
        'installed': {
          'client_id': args.client_id,
          'client_secret': args.client_secret,
          'redirect_uris': ['urn:ietf:wg:oauth:2.0:oob'],
          'auth_uri': OAUTH2_AUTHORIZE.format(project_id=args.project_id),
          'token_uri': OAUTH2_TOKEN,
		},
      }
      app_flow = InstalledAppFlow.from_client_config(
          client_config, scopes=SDM_SCOPES)
      creds = app_flow.run_console()
    # Save the credentials for the next run
    if not os.path.exists(os.path.dirname(token_cache)):
      try:
        os.makedirs(os.path.dirname(token_cache))
      except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
            raise
    with open(token_cache, 'wb') as token:
      pickle.dump(creds, token)
  return creds


def PrintStructure(structure):
  print(f'id: {structure.name}')
  print('traits:')
  for (trait_name, trait) in structure.traits.items():
    print(f'  {trait_name}: {trait._data}')
  print('')


def PrintDevice(device):
  print(f'id: {device.name}')
  print(f'type: {device.type}')
  print('room/structure: ')
  for (parent_id, parent_name) in device.parent_relations.items():
    print(f'  id: {parent_id}')
    print(f'  name: {parent_name}')

  print('traits:')
  for (trait_name, trait) in device.traits.items():
    print(f'  {trait_name}: {trait._data}')
  print('')


class SubscribeCallback(EventCallback):

  def handle_event(self, event_message: EventMessage):
    print(f'event_id: {event_message.event_id}')
    print(f'timestamp: {event_message.timestamp}')
    print(f'resource_update_name: {event_message.resource_update_name}')
    traits = event_message.resource_update_traits
    if traits:
      print('traits:')
      for (name, trait) in traits.items():
        print(f'  {name}: {trait._data}')
    events = event_message.resource_update_events
    if events:
      print('events:')
      for (name, event) in events.items():
        print(f'  {name}:')
        print(f'    event_id: {event.event_id}')
        print(f'    event_session_id: {event.event_session_id}')
    print('')


async def RunTool(args, creds: Credentials):
  async with ClientSession() as client:
    auth = Auth(client, creds, API_URL)
    api = GoogleNestAPI(auth, args.project_id)

    if args.command == 'list_structures':
      structures = await api.async_get_structures()
      for structure in structures:
        PrintStructure(structure)
      return

    if args.command == 'get_structure':
      structure = await api.async_get_structure(args.structure_id)
      PrintStructure(structure)
      return

    if args.command == 'list_devices':
      devices = await api.async_get_devices()
      for device in devices:
        PrintDevice(device)
      return

    if args.command == 'subscribe':
      logging.info('Subscription: %s', args.subscription_id)
      subscriber = GoogleNestSubscriber(auth, args.project_id,
          args.subscription_id)
      subscriber.set_update_callback(SubscribeCallback())
      await subscriber.start_async()
      try:
        subscriber.wait()
      except KeyboardInterrupt:
        subscriber.stop_async()
      return

    # All other commands require a device_id
    device = await api.async_get_device(args.device_id)

    if args.command == 'get_device':
      PrintDevice(device)

    if args.command == 'set_mode':
      mode = args.mode
      trait = device.traits[ThermostatModeTrait.NAME]
      if mode == 'MANUAL_ECO':
        trait = device.traits[ThermostatEcoTrait.NAME]
      resp = await trait.set_mode(mode)
      print(await resp.text())

    if args.command == 'set_heat':
      trait = device.traits[ThermostatTemperatureSetpointTrait.NAME]
      resp = await trait.set_heat(args.heat)
      print(await resp.text())

    if args.command == 'set_cool':
      trait = device.traits[ThermostatTemperatureSetpointTrait.NAME]
      resp = await trait.set_cool(args.cool)
      print(await resp.text())

    if args.command == 'set_range':
      trait = device.traits[ThermostatTemperatureSetpointTrait.NAME]
      resp = await trait.set_range(args.heat, args.cool)
      print(await resp.text())

    if args.command == 'generate_rtsp_stream':
      trait = device.traits[CameraLiveStreamTrait.NAME]
      stream = await trait.generate_rtsp_stream()
      print(f'URL: {stream.rtsp_stream_url}')
      print(f'Stream Token: {stream.stream_token}')
      print(f'Expires At: {stream.expires_at}')


def main():
  args = parser.parse_args()
  if args.verbose:
    logging.basicConfig(level=logging.DEBUG)
  creds = CreateCreds(args)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(RunTool(args, creds))
  loop.close()

if __name__ == "__main__":
  main()
