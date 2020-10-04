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
import os
import errno
import pickle

from aiohttp import ClientSession
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from .auth import AbstractAuth
from .google_nest_api import GoogleNestAPI

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
cmd_parser = parser.add_subparsers(dest='command', required=True)
list_parser = cmd_parser.add_parser('list')
get_parser = cmd_parser.add_parser('get')
get_parser.add_argument('device_id')

OAUTH2_AUTHORIZE = (
    "https://nestservices.google.com/partnerconnections/{project_id}/auth"
)
OAUTH2_TOKEN = "https://www.googleapis.com/oauth2/v4/token"
SDM_SCOPES = ["https://www.googleapis.com/auth/sdm.service"]
API_URL = "https://smartdevicemanagement.googleapis.com/v1/enterprises/{project_id}"


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


async def RunTool(args, creds: Credentials):
  async with ClientSession() as client:
    auth = Auth(client, creds, API_URL.format(project_id=args.project_id))
    api = GoogleNestAPI(auth)

    if args.command == 'list':
      devices = await api.async_get_devices()
      for device in devices:
        PrintDevice(device)

    if args.command == 'get':
      device = await api.async_get_device(args.device_id)
      PrintDevice(device)


def main():
  args = parser.parse_args()
  creds = CreateCreds(args)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(RunTool(args, creds))
  loop.close()

if __name__ == "__main__":
  main()
