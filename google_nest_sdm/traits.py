from .auth import AbstractAuth
from .registry import Registry

DEVICE_TRAITS = 'traits'

TRAIT_MAP = Registry()

class Command:
  """Base class for executing commands."""

  def __init__(self, device_id: str, auth: AbstractAuth):
    self._device_id = device_id
    self._auth = auth

  async def execute(self, data):
    return await self._auth.request(
        "post", f"{self._device_id}:executeCommand", json=data)


def _TraitsDict(traits: dict, trait_map: dict, cmd: Command):
  d = {}
  for (trait, trait_data) in traits.items():
    if not trait in trait_map:
      continue
    cls = trait_map[trait]
    d[trait] = cls(trait_data, cmd)
  return d


def BuildTraits(traits: dict, cmd: Command) -> dict:
    """Builds a trait map out of a response dict."""
    return _TraitsDict(traits, TRAIT_MAP, cmd)

