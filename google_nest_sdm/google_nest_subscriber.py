from typing import List
from abc import ABC, abstractmethod
import json

from google.auth.credentials import Credentials
from google.cloud import pubsub_v1

from .auth import AbstractAuth
from .device import Device
from .device_manager import DeviceManager
from .event import EventCallback, EventMessage
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


class GoogleNestSubscriber:
  """Subscribes to events from the Google Nest feed."""

  def __init__(self, auth: AbstractAuth, project_id: str, subscriber_id: str,
      subscriber_factory=DefaultSubscriberFactory()):
    """Initialize the subscriber for the specified topic"""
    self._auth = auth
    self._subscriber_id = subscriber_id
    self._api = GoogleNestAPI(auth, project_id)
    self._subscriber_factory = subscriber_factory
    self._device_manager = None
    self._callback = None

  def set_update_callback(self, callback: EventCallback):
    self._callback = callback

  async def start_async(self) -> DeviceManager:
    creds = await self._auth.async_get_creds()
    self._future = await self._subscriber_factory.new_subscriber(
        creds, self._subscriber_id, self._subscribe_callback)

    # Do initial population of devices and structures
    self._device_manager = DeviceManager()
    structures = await self._api.async_get_structures()
    for structure in structures:
      self._device_manager.add_structure(structure)
    # Subscriber starts after a device fetch
    devices = await self._api.async_get_devices()
    for device in devices:
      self._device_manager.add_device(device)
    return self._device_manager

  def wait(self):
    self._future.result()

  def stop_async(self):
    return self._future.cancel()

  @property
  def device_manager(self):
    return self._device_manager

  def _subscribe_callback(self, message: pubsub_v1.subscriber.message.Message):
    payload = json.loads(bytes.decode(message.data))
    event = EventMessage(payload, self._auth)
    if self._device_manager:
      self._device_manager.handle_event(event)
    if self._callback:
      self._callback.handle_event(event)
    message.ack()
