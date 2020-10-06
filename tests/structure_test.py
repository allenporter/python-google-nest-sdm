# Scaffolding for local test development
from .context import google_nest_sdm

import unittest
from google_nest_sdm.structure import (
    Structure,
    InfoTrait,
    RoomInfoTrait,
)


class StructureTest(unittest.TestCase):

  def testNoTraits(self):
    raw = {
       "name": "my/structure/name",
    }
    structure = Structure.MakeStructure(raw)
    self.assertEqual("my/structure/name", structure.name)
    self.assertFalse("sdm.structures.traits.Info" in structure.traits)

  def testEmptyTraits(self):
    raw = {
       "name": "my/structure/name",
       "traits": {
       },
    }
    structure = Structure.MakeStructure(raw)
    self.assertEqual("my/structure/name", structure.name)
    self.assertFalse("sdm.structures.traits.Info" in structure.traits)

  def testInfoTraits(self):
    raw = {
       "name": "my/structure/name",
       "traits": {
         "sdm.structures.traits.Info": {
           "customName": "Structure Name",
         },
       },
    }
    structure = Structure.MakeStructure(raw)
    self.assertEqual("my/structure/name", structure.name)
    self.assertTrue("sdm.structures.traits.Info" in structure.traits)
    trait = structure.traits["sdm.structures.traits.Info"]
    self.assertEqual("Structure Name", trait.custom_name)

  def testRoomInfoTraits(self):
    raw = {
       "name": "my/structure/name",
       "traits": {
         "sdm.structures.traits.RoomInfo": {
           "customName": "Structure Name",
         },
       },
    }
    structure = Structure.MakeStructure(raw)
    self.assertEqual("my/structure/name", structure.name)
    self.assertTrue("sdm.structures.traits.RoomInfo" in structure.traits)
    trait = structure.traits["sdm.structures.traits.RoomInfo"]
    self.assertEqual("Structure Name", trait.custom_name)


