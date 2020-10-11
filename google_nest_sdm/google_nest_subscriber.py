from typing import List
from abc import ABC, abstractmethod
import json

from google.auth.credentials import Credentials
from google.cloud import pubsub_v1

from .auth import AbstractAuth
from .device import Device
from .event import EventMessage
from .google_nest_api import GoogleNestAPI
from .structure import Structure


class AbstractSusbcriberFactory(ABC):
  """Abstract class for creating a subscriber, to facilitate testing."""

  @abstractmethod
  async def new_subscriber(self, creds, subscription_name, callback) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
    """Create a new event subscriber."""


class DefaultSubscriberFactory(AbstractSusbcriberFactory):
  """Default implementation that creates Google Pubsub subscriber."""

  async def new_subscriber(self, creds, subscription_name, callback) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
    subscriber = pubsub_v1.SubscriberClient(credentials=creds)
    return subscriber.subscribe(subscription_name, callback)


class EventCallback(ABC):
  @abstractmethod
  def handle_event(event_message: EventMessage):
    """Process an incoming EventMessage."""


class GoogleNestSubscriber:
  """Subscribes to events from the Google Nest feed."""

  def __init__(self, auth: AbstractAuth, project_id: str, subscriber_id: str,
      subscriber_factory=DefaultSubscriberFactory()):
    """Initialize the subscriber for the specified topic"""
    self._auth = auth
    self._subscriber_id = subscriber_id
    self._api = GoogleNestAPI(auth, project_id)
    self._subscriber_factory = subscriber_factory
    self._callback = None


  async def start_async(self, callback: EventCallback):
    self._callback = callback
    creds = await self._auth.async_get_creds()
    self._future = await self._subscriber_factory.new_subscriber(creds, self._subscriber_id, self._subscribe_callback)
    # Subscriber starts after a device fetch
    self._devices = await self._api.async_get_devices()
    return self._future

  async def stop_async(self):
    return self._future.cancel()

  async def devices(self):
    devices = {}
    for device in self._devices:
      devices[device.name] = device
    return devices

  def _subscribe_callback(self, message: pubsub_v1.subscriber.message.Message):
    payload = json.loads(bytes.decode(message.data))
    event = EventMessage(payload, self._auth)
    self._callback.handle_event(event)
    message.ack()
