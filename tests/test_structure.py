from google_nest_sdm.structure import Structure


def test_no_traits() -> None:
    raw = {
        "name": "my/structure/name",
    }
    structure = Structure.MakeStructure(raw)
    assert "my/structure/name" == structure.name
    assert "sdm.structures.traits.Info" not in structure.traits


def test_empty_traits() -> None:
    raw = {
        "name": "my/structure/name",
        "traits": {},
    }
    structure = Structure.MakeStructure(raw)
    assert "my/structure/name" == structure.name
    assert "sdm.structures.traits.Info" not in structure.traits


def test_info_traits() -> None:
    raw = {
        "name": "my/structure/name",
        "traits": {
            "sdm.structures.traits.Info": {
                "customName": "Structure Name",
            },
        },
    }
    structure = Structure.MakeStructure(raw)
    assert "my/structure/name" == structure.name
    assert "sdm.structures.traits.Info" in structure.traits
    trait = structure.traits["sdm.structures.traits.Info"]
    assert "Structure Name" == trait.custom_name


def test_room_info_traits() -> None:
    raw = {
        "name": "my/structure/name",
        "traits": {
            "sdm.structures.traits.RoomInfo": {
                "customName": "Structure Name",
            },
        },
    }
    structure = Structure.MakeStructure(raw)
    assert "my/structure/name" == structure.name
    assert "sdm.structures.traits.RoomInfo" in structure.traits
    trait = structure.traits["sdm.structures.traits.RoomInfo"]
    assert "Structure Name" == trait.custom_name
