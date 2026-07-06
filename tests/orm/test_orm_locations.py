import pytest
from typing import Sequence, Iterator, Literal, overload
from pathlib import Path


from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from click_extra.testing import CliRunner

from clickshare_temperature.orm import (
    set_engine_uri,
    get_engine_uri,
    init_db,
    get_session,
)
from clickshare_temperature.orm import models
from clickshare_temperature.orm.serialization import (
    serialize_database,
    deserialize_database,
)
from clickshare_temperature.orm.cli import list_locations
from clickshare_temperature.orm.types import LocationSiblingType
from clickshare_temperature.types import BaseUnitInfo

from .conftest import _reset_engine

type PathList = tuple[str, ...]
type LocationTypeName = Literal["building", "floor", "room"]



@pytest.fixture
def location_root_names_with_sibling_types() -> list[tuple[str, LocationSiblingType]]:
    """Fixture that provides a list of root location names (nest level 1) with their sibling types
    """
    return [
        ("Building A", "first"),
        ("Building B", "middle"),
        ("Building C", "last"),
    ]

@pytest.fixture
def location_root_names(
    location_root_names_with_sibling_types: list[tuple[str, LocationSiblingType]]
) -> list[str]:
    """Fixture that provides a list of root location names (nest level 1)
    """
    return [name for name, _ in location_root_names_with_sibling_types]


@pytest.fixture
def location_floor_names_with_sibling_types() -> list[tuple[str, LocationSiblingType]]:
    """Fixture that provides a list of floor location names (nest level 2) with their sibling types
    """
    return [
        ("Floor 1", "first"),
        ("Floor 2", "middle"),
        ("Floor 3", "middle"),
        ("Floor with only one Child", "last"),
    ]

@pytest.fixture
def location_floor_names(
    location_floor_names_with_sibling_types: list[tuple[str, LocationSiblingType]]
) -> list[str]:
    """Fixture that provides a list of floor location names (nest level 2)
    """
    return [name for name, _ in location_floor_names_with_sibling_types]


@pytest.fixture
def location_room_names_with_sibling_types() -> list[tuple[str, LocationSiblingType]]:
    """Fixture that provides a list of room location names (nest level 3) with their sibling types
    """
    return [
        ("Room 101", "first"),
        ("Room 102", "middle"),
        ("Room 103", "last"),
        ("Lone Room", "only"),
    ]


@pytest.fixture
def location_room_names(
    location_room_names_with_sibling_types: list[tuple[str, LocationSiblingType]]
) -> list[str]:
    """Fixture that provides a list of room location names (nest level 3)
    """
    return [name for name, _ in location_room_names_with_sibling_types]



def _get_room_tuple_valid(*names: str) -> bool:
    """Helper function to determine if a tuple of location names represents a
    valid location in the hierarchy
    """
    if len(names) != 3:
        return True
    floor_name = names[1]
    room_name = names[2]
    is_lone_floor = (floor_name == "Floor with only one Child")
    is_lone_room = (room_name == "Lone Room")
    if is_lone_floor and not is_lone_room:
        return False
    elif not is_lone_floor and is_lone_room:
        return False
    return True


@overload
def _iter_locations[T: str] (
    roots: Sequence[T],
    floors: Sequence[T],
    rooms: Sequence[T],
) -> Iterator[PathList]: ...
@overload
def _iter_locations[T: tuple[str, LocationSiblingType]] (
    roots: Sequence[T],
    floors: Sequence[T],
    rooms: Sequence[T],
) -> Iterator[tuple[PathList, LocationSiblingType]]: ...
def _iter_locations[T: (str, tuple[str, LocationSiblingType])] (
    roots: Sequence[T],
    floors: Sequence[T],
    rooms: Sequence[T],
) -> Iterator[tuple[PathList, LocationSiblingType] | PathList]:
    """Helper function to iterate through all combinations of location name tuples
    from the given root, floor, and room names
    """

    def get_name_and_sibling_type(item: T) -> tuple[str, LocationSiblingType | None]:
        if isinstance(item, str):
            return item, None
        else:
            return item

    def get_yield_value(
        name_tuple: PathList,
        sibling_type: LocationSiblingType | None
    ) -> tuple[PathList, LocationSiblingType] | PathList:
        if sibling_type is not None:
            return name_tuple, sibling_type
        else:
            return name_tuple

    for root in roots:
        root_name, root_sibling_type = get_name_and_sibling_type(root)
        if _get_room_tuple_valid(root_name):
            yield get_yield_value((root_name,), root_sibling_type)
        for floor in floors:
            floor_name, floor_sibling_type = get_name_and_sibling_type(floor)
            if _get_room_tuple_valid(root_name, floor_name):
                yield get_yield_value((root_name, floor_name), floor_sibling_type)
            for room in rooms:
                room_name, room_sibling_type = get_name_and_sibling_type(room)
                if _get_room_tuple_valid(root_name, floor_name, room_name):
                    yield get_yield_value((root_name, floor_name, room_name), room_sibling_type)


@pytest.fixture
def location_with_type_name(
    location_root_names: list[str],
    location_floor_names: list[str],
    location_room_names: list[str],
) -> dict[PathList, LocationTypeName]:
    """Fixture that provides a mapping of location name tuples to their expected
    LocationType names for testing
    """
    location_type_names: dict[PathList, LocationTypeName] = {}
    for name_tuple in _iter_locations(
        location_root_names,
        location_floor_names,
        location_room_names,
    ):
        if len(name_tuple) == 1:
            location_type_names[name_tuple] = "building"
        elif len(name_tuple) == 2:
            location_type_names[name_tuple] = "floor"
        elif len(name_tuple) == 3:
            location_type_names[name_tuple] = "room"
    return location_type_names


@pytest.fixture
def location_sibling_types(
    location_root_names_with_sibling_types: list[tuple[str, LocationSiblingType]],
    location_floor_names_with_sibling_types: list[tuple[str, LocationSiblingType]],
    location_room_names_with_sibling_types: list[tuple[str, LocationSiblingType]],
) -> dict[PathList, LocationSiblingType]:
    """Fixture that provides a mapping of location name tuples to their sibling types for testing
    """
    sibling_types: dict[PathList, LocationSiblingType] = {}
    for name_tuple, sibling_type in _iter_locations(
        location_root_names_with_sibling_types,
        location_floor_names_with_sibling_types,
        location_room_names_with_sibling_types,
    ):
        sibling_types[name_tuple] = sibling_type
    return sibling_types


@pytest.fixture
def location_name_tree_breadth_first(
    location_root_names: list[str],
    location_floor_names: list[str],
    location_room_names: list[str],
) -> list[PathList]:
    """Fixture that provides a list of location name tuples representing a
    hierarchy of root -> floor -> room

    The resulting list will include tuples for all combinations of the tree in
    breath-first order.
    """
    name_tree: dict[int, list[PathList]] = {}
    for name_tuple in _iter_locations(
        location_root_names,
        location_floor_names,
        location_room_names,
    ):
        name_tree.setdefault(len(name_tuple), []).append(name_tuple)

    # sort the name tuples as breadth-first by their length, then by their content
    sorted_name_tree: list[PathList] = []
    for length in sorted(name_tree.keys()):
        sorted_name_tree.extend(sorted(name_tree[length]))
    assert len(sorted_name_tree) == len(set(sorted_name_tree))
    return sorted_name_tree



@pytest.fixture
def location_name_tree_depth_first(
    location_root_names: list[str],
    location_floor_names: list[str],
    location_room_names: list[str],
) -> list[PathList]:
    """Fixture that provides a list of location name tuples representing a
    hierarchy of root -> floor -> room

    The resulting list will include tuples for all combinations of the tree in
    depth-first order with the final branches at the beginning.
    """
    name_tree: dict[int, list[PathList]] = {}
    for name_tuple in _iter_locations(
        location_root_names,
        location_floor_names,
        location_room_names,
    ):
        name_tree.setdefault(len(name_tuple), []).append(name_tuple)

    # sort the name tuples as depth-first by their length in reverse, then by their content
    sorted_name_tree: list[PathList] = []
    for length in sorted(name_tree.keys(), reverse=True):
        sorted_name_tree.extend(sorted(name_tree[length]))
    assert len(sorted_name_tree) == len(set(sorted_name_tree))
    return sorted_name_tree


@pytest.fixture(params=["breadth_first", "depth_first"])
def location_name_tree(
    request,
    location_name_tree_breadth_first: list[PathList],
    location_name_tree_depth_first: list[PathList],
) -> list[PathList]:
    """Fixture that provides a list of location name tuples representing a
    hierarchy of root -> floor -> room, parameterized in either breadth-first
    or depth-first order
    """
    if request.param == "breadth_first":
        return location_name_tree_breadth_first
    else:
        return location_name_tree_depth_first


@pytest.fixture
def base_unit_for_location_model(
    db_session: Session,
    location_name_tree: list[PathList],
) -> dict[PathList, tuple[list[models.BaseUnit], models.Location]]:
    """Fixture that creates a BaseUnit for each location in the location_name_tree
    and returns a mapping of location pathlists to their expected BaseUnit

    Note that the Location and BaseUnit models are only created, no relationships
    are established between them.
    """
    location_to_base_unit: dict[PathList, tuple[list[models.BaseUnit], models.Location]] = {}
    for name_tuple in location_name_tree:
        location = models.Location.create_from_pathlist(*name_tuple, session=db_session)
        base_units: list[models.BaseUnit] = []
        for i in range(2):
            base_unit = models.BaseUnit(
                hostname=f"host-{location.path}-{i}",
                room_name=location.path,
                ip_address=f"192.168.0.{len(location_to_base_unit) * 2 + i}",
            )
            db_session.add(base_unit)
            base_units.append(base_unit)
        location_to_base_unit[name_tuple] = (base_units, location)
    db_session.commit()
    return location_to_base_unit


@pytest.fixture
def populated_locations(
    db_session: Session,
    location_name_tree: list[PathList],
    location_with_type_name: dict[PathList, LocationTypeName],
) -> dict[LocationTypeName, set[PathList]]:
    """Fixture that creates populated locations with their associated LocationTypes
    """
    for location_type_name in set(location_with_type_name.values()):
        _location_type = models.LocationType(name=location_type_name)
        db_session.add(_location_type)
    db_session.commit()

    populated: dict[LocationTypeName, set[PathList]] = {}
    for name_tuple in location_name_tree:
        location = models.Location.create_from_pathlist(*name_tuple, session=db_session)
        assert location.location_type is None
        location_type_name = location_with_type_name[name_tuple]
        location_type = models.LocationType.get_by_name(location_type_name, session=db_session)
        assert location_type is not None
        location.location_type = location_type
        db_session.add(location)
        if location_type_name not in populated:
            populated[location_type_name] = set()
        populated[location_type_name].add(name_tuple)
    db_session.commit()
    return populated


def test_location_type_model_uniqueness(
    db_session: Session,
) -> None:
    """Test that the unique constraint on the name of the LocationType model is enforced
    """
    location_type_name = "building"
    location_type = models.LocationType(name=location_type_name)
    db_session.add(location_type)
    db_session.commit()

    with db_session.begin_nested():
        with pytest.raises(IntegrityError):
            duplicate_location_type = models.LocationType(name=location_type_name)
            db_session.add(duplicate_location_type)
            db_session.flush()


def test_location_model_types(
    db_session: Session,
    populated_locations: dict[LocationTypeName, set[PathList]],
    location_with_type_name: dict[PathList, LocationTypeName],
) -> None:
    """Test that the LocationType relationships and attributes of the Location model are correctly set
    """
    location: models.Location|None
    for location_type_name, pathlists in populated_locations.items():
        location_type = models.LocationType.get_by_name(location_type_name, session=db_session)
        assert location_type is not None
        for location in location_type.locations:
            assert location.location_type is not None
            assert location.location_type.name == location_type_name
            assert location.location_type_name == location_type_name
            assert location.pathlist in pathlists

        for pathlist in pathlists:
            location = models.Location.get_by_pathlist(*pathlist, session=db_session)
            assert location is not None
            assert location.location_type is not None
            assert location.location_type.name == location_type_name
            assert location.location_type_name == location_type_name

    for pathlist, location_type_name in location_with_type_name.items():
        location = models.Location.get_by_pathlist(*pathlist, session=db_session)
        assert location is not None
        assert location.location_type is not None
        assert location.location_type.name == location_type_name
        assert location.location_type_name == location_type_name


def test_location_model_get_by_location_type(
    db_session: Session,
    populated_locations: dict[LocationTypeName, set[PathList]],
) -> None:
    """Test the get_by_location_type class method of the Location model to ensure it correctly retrieves
    all locations with the given location type
    """
    for location_type_name, pathlists in populated_locations.items():
        locations = models.Location.get_by_location_type(location_type_name, session=db_session)
        assert len(locations) == len(pathlists)
        for location in locations:
            assert location.location_type is not None
            assert location.location_type.name == location_type_name
            assert location.pathlist in pathlists

        location_type = models.LocationType.get_by_name(location_type_name, session=db_session)
        assert location_type is not None
        locations = models.Location.get_by_location_type(location_type, session=db_session)
        assert len(locations) == len(pathlists)
        for location in locations:
            assert location.location_type is not None
            assert location.location_type.name == location_type_name
            assert location.pathlist in pathlists



def test_location_model_hierarchy(
    db_session: Session,
    location_name_tree: list[PathList],
) -> None:
    """Test basic hierarchy creation and relationship attributes of the Location model
    """
    for name_tuple in location_name_tree:
        models.Location.create_from_pathlist(*name_tuple, session=db_session)
    db_session.commit()

    for name_tuple in location_name_tree:
        location = models.Location.get_by_pathlist(*name_tuple, session=db_session)
        assert location is not None
        assert location.name == name_tuple[-1]
        assert location.pathlist == name_tuple
        assert location.nest_level == len(name_tuple) - 1
        assert location.path == " -> ".join(name_tuple)
        if len(name_tuple) == 1:
            assert location.parent_location is None
            assert location.is_root
        else:
            parent = location.parent_location
            assert parent is not None
            assert parent.name == name_tuple[-2]
            assert parent.pathlist == name_tuple[:-1]
            assert not location.is_root



def test_location_model_hierarchy_uniqueness(
    db_session: Session,
    location_name_tree: list[PathList],
    location_root_names: list[str],
) -> None:
    """Test that the unique constraint on (name, parent_location_id) is enforced in the Location model
    """
    for name_tuple in location_name_tree:
        models.Location.create_from_pathlist(*name_tuple, session=db_session)
    db_session.commit()

    # Attempt to create duplicate locations with the same name and parent,
    # which should violate the unique constraint
    for name_tuple in location_name_tree:
        if len(name_tuple) == 1:
            continue
        location = models.Location.get_by_pathlist(*name_tuple, session=db_session)
        assert location is not None
        parent = location.parent_location
        assert parent is not None
        with db_session.begin_nested():
            with pytest.raises(IntegrityError):
                new_location = models.Location(name=location.name, parent_location=parent)
                db_session.add(new_location)
                db_session.flush()

    # Attempt to create duplicate root locations with the same name,
    # which should also violate the unique constraint
    for root_name in location_root_names:
        with db_session.begin_nested():
            with pytest.raises(IntegrityError):
                new_location = models.Location(name=root_name, parent_location=None)
                db_session.add(new_location)
                db_session.flush()


def test_location_model_ancestors_query(
    db_session: Session,
    location_name_tree: list[PathList],
    location_sibling_types: dict[PathList, LocationSiblingType],
) -> None:
    """Test the ancestors query of the Location model to ensure it correctly
    retrieves all ancestors
    """
    for name_tuple in location_name_tree:
        models.Location.create_from_pathlist(*name_tuple, session=db_session)
    db_session.commit()

    for name_tuple in location_name_tree:
        location = models.Location.get_by_pathlist(*name_tuple, session=db_session)
        assert location is not None
        expected_ancestors = []
        for i in range(1, len(name_tuple)):
            ancestor_pathlist = name_tuple[:-i]
            expected_ancestors.append(ancestor_pathlist)
        discovered_ancestors = set[PathList]()
        query = location.get_ancestors_query()
        ancestors = db_session.execute(query).scalars().all()
        for ancestor in ancestors:
            assert ancestor.pathlist in expected_ancestors
            sibling_type = ancestor.get_sibling_type(session=db_session)
            assert location_sibling_types[ancestor.pathlist] == sibling_type
            discovered_ancestors.add(ancestor.pathlist)
        assert discovered_ancestors == set(expected_ancestors)


def test_location_model_descendants_query(
    db_session: Session,
    location_name_tree: list[PathList],
    location_sibling_types: dict[PathList, LocationSiblingType],
) -> None:
    """Test the descendants query of the Location model to ensure it correctly
    retrieves all descendants
    """
    for name_tuple in location_name_tree:
        models.Location.create_from_pathlist(*name_tuple, session=db_session)
    db_session.commit()

    for root_location in models.Location.get_root_locations(session=db_session):
        assert root_location.is_root
        expected_pathlists = {
            name_tuple for name_tuple in location_name_tree if name_tuple[0] == root_location.name
        }
        discovered_pathlists = set[PathList]()
        discovered_pathlists.add(root_location.pathlist)

        query = root_location.get_descendants_query()
        descendants = db_session.execute(query).scalars().all()
        for descendant in descendants:
            assert descendant is not root_location
            assert descendant.root_location is root_location
            assert descendant.pathlist != root_location.pathlist
            assert descendant.pathlist[:len(root_location.pathlist)] == root_location.pathlist
            sibling_type = descendant.get_sibling_type(session=db_session)
            assert location_sibling_types[descendant.pathlist] == sibling_type
            assert descendant.pathlist in expected_pathlists
            discovered_pathlists.add(descendant.pathlist)
        assert discovered_pathlists == expected_pathlists



def test_location_model_deletion_with_descendants(
    db_session: Session,
    location_name_tree: list[PathList],
) -> None:
    """Test that deleting a Location with descendants correctly deletes all of its descendants as well"""
    for name_tuple in location_name_tree:
        models.Location.create_from_pathlist(*name_tuple, session=db_session)
    db_session.commit()

    assert db_session.query(models.Location).count() == len(location_name_tree)

    for root_location in models.Location.get_root_locations(session=db_session):
        descendant_query = root_location.get_descendants_query()
        descendant_ids = {loc.id for loc in db_session.execute(descendant_query).scalars().all()}
        db_session.delete(root_location)
        db_session.commit()

        # After deleting the root location, all of its descendants should also be deleted
        remaining_location_ids = {loc.id for loc in db_session.query(models.Location).all()}
        assert descendant_ids.isdisjoint(remaining_location_ids)
        assert root_location.id not in remaining_location_ids

    assert db_session.query(models.Location).count() == 0




def test_location_model_baseunit_assignment(
    db_session: Session,
    base_unit_for_location_model: dict[PathList, tuple[list[models.BaseUnit], models.Location]],
) -> None:
    """Test assigning BaseUnits to Locations and verify the relationships are correctly established
    """
    expected_all_locations = set[models.Location]()
    expected_all_base_units = set[models.BaseUnit]()
    for base_units, location in base_unit_for_location_model.values():
        expected_all_locations.add(location)
        expected_all_base_units.update(base_units)

        # Ensure there are no BaseUnits assigned to the location before assignment
        location_base_units = location.get_base_units(session=db_session)
        assert len(location_base_units) == 0
        for base_unit in base_units:
            assert base_unit.location is None
            base_unit.location = location
            db_session.add(base_unit)
    db_session.commit()

    # Verify that each location has the correct BaseUnits assigned, and that
    # the relationship is bidirectional
    for base_units, location in base_unit_for_location_model.values():
        assert set(location.base_units) == set(base_units)
        assert set(location.get_base_units(session=db_session)) == set(base_units)
        # location_base_units = location.get_base_units(session=db_session)
        # assert set(location_base_units) == set(base_units)
        # assert set(location.base_units) == set(base_units)
        for base_unit in base_units:
            assert base_unit.location is location

    def get_expected_base_units_for_location(location: models.Location) -> set[models.BaseUnit]:
        """Get the BaseUnits assigned to the given location or any of its descendants"""
        result = set[models.BaseUnit]()
        for base_units, loc in base_unit_for_location_model.values():
            if loc == location:
                result.update(base_units)
            elif loc.pathlist[:len(location.pathlist)] == location.pathlist:
                result.update(base_units)
        return result

    base_units_seen = set[models.BaseUnit]()
    locations_seen = set[models.Location]()

    # Check the get_base_units method with include_descendants=True for each location,
    # and verify that the returned BaseUnits match the expected values.
    for location in db_session.query(models.Location).all():
        location_base_units = location.get_base_units(session=db_session, include_descendants=True)
        expected_base_units = get_expected_base_units_for_location(location)
        assert set(location_base_units) == expected_base_units
        base_units_seen.update(location_base_units)
        locations_seen.add(location)

    assert locations_seen == expected_all_locations
    assert base_units_seen == expected_all_base_units


def test_baseunit_location_type_relationships(
    db_session: Session,
    base_unit_for_location_model: dict[PathList, tuple[list[models.BaseUnit], models.Location]],
    populated_locations: dict[LocationTypeName, set[PathList]],
) -> None:
    """Test that the relationships between BaseUnits, Locations, and LocationTypes
    are correctly established and that the attributes on the BaseUnit model are
    correctly set based on the assigned Location and its LocationType
    """
    location: models.Location|None
    for pathlist, (base_units, location) in base_unit_for_location_model.items():
        for base_unit in base_units:
            base_unit.location = location
            db_session.add(base_unit)
    db_session.commit()

    for location_type_name, pathlists in populated_locations.items():
        location_type = models.LocationType.get_by_name(location_type_name, session=db_session)
        assert location_type is not None
        for pathlist in pathlists:
            location = models.Location.get_by_pathlist(*pathlist, session=db_session)
            assert location is not None
            assert location.location_type is not None
            assert location.location_type.name == location_type_name
            base_units, _ = base_unit_for_location_model[pathlist]
            for base_unit in base_units:
                assert base_unit.location is location
                assert base_unit in location.base_units
                assert base_unit.location_type is location.location_type
                assert base_unit.location_type_name == location_type_name



@pytest.mark.parametrize("deletion_method", ["bulk_delete", "individual_delete", "descendant_delete"])
def test_location_model_baseunit_assignment_deletion(
    db_session: Session,
    base_unit_for_location_model: dict[PathList, tuple[list[models.BaseUnit], models.Location]],
    deletion_method: Literal["bulk_delete", "individual_delete", "descendant_delete"],
) -> None:
    """Test that deleting Locations with assigned BaseUnits correctly handles the relationships
    and keeps the BaseUnit models intact
    """
    all_base_units = set[models.BaseUnit]()
    # First assign the BaseUnits to the Locations as in the previous test
    for base_units, location in base_unit_for_location_model.values():
        for base_unit in base_units:
            all_base_units.add(base_unit)
            base_unit.location = location
            db_session.add(base_unit)
    db_session.commit()

    # Then delete all the locations, which should leave the BaseUnits intact, but without a location
    if deletion_method == "bulk_delete":
        db_session.query(models.Location).delete()
        db_session.commit()
    elif deletion_method == "individual_delete":
        # Delete locations one by one starting from the leaf nodes to avoid cascades

        def gather_leaf_locations() -> Iterator[models.Location]:
            """Helper function to gather leaf locations in the hierarchy for individual deletion"""
            for location in db_session.query(models.Location).all():
                if not location.child_locations:
                    yield location

        while db_session.query(models.Location).count() > 0:
            leaf_locations = list(gather_leaf_locations())
            assert len(leaf_locations) > 0, "Expected to find leaf locations to delete, but found none"
            for leaf_location in leaf_locations:
                db_session.delete(leaf_location)
            db_session.commit()
    elif deletion_method == "descendant_delete":
        for root_location in models.Location.get_root_locations(session=db_session):
            db_session.delete(root_location)
        db_session.commit()

    # Verify that all locations have been deleted and BaseUnits have no location
    assert db_session.query(models.Location).count() == 0
    assert db_session.query(models.BaseUnit).count() == len(all_base_units)
    for base_unit in db_session.query(models.BaseUnit).all():
        assert base_unit.location is None



def test_location_model_serialization(
    db_session: Session,
    location_name_tree: list[PathList],
    location_sibling_types: dict[PathList, LocationSiblingType],
    populated_locations: dict[PathList, tuple[models.Location, LocationTypeName]],
    location_with_type_name: dict[PathList, LocationTypeName],
    base_unit_for_location_model: dict[PathList, tuple[list[models.BaseUnit], models.Location]],
    tmp_path: Path,
) -> None:
    """Test that the Location model and its relationships to BaseUnits can
    be correctly serialized and deserialized
    """

    # Store the BaseUnitInfo for each location before resetting the engine
    # so that we can verify it after deserialization
    all_base_unit_infos: dict[PathList, list[BaseUnitInfo]] = {}


    # Phase 1: Serialize the database with data, then reset the engine to simulate a fresh start
    for base_units, location in base_unit_for_location_model.values():
        for base_unit in base_units:
            all_base_unit_infos.setdefault(location.pathlist, []).append(base_unit.to_data())
            base_unit.location = location
            db_session.add(base_unit)
    db_session.commit()
    serialized_db_json = serialize_database(db_session)
    db_session.close()
    _reset_engine()


    # Phase 2: Initialize a new database and deserialize the data into it,
    # then verify the data was correctly deserialized
    db_file = tmp_path / "deserialized.db"
    assert not db_file.exists()
    new_uri = f"sqlite:///{db_file}"
    set_engine_uri(new_uri)
    assert str(get_engine_uri()) == str(new_uri)
    init_db()
    assert db_file.exists()
    new_db_session = get_session()

    assert new_db_session is not db_session
    db_session = new_db_session
    assert db_session.query(models.Location).count() == 0

    deserialize_database(db_session, serialized_db_json)
    for name_tuple, location_type_name in location_with_type_name.items():
        location_type = models.LocationType.get_by_name(location_type_name, session=db_session)
        assert location_type is not None
        assert location_type.name == location_type_name
        assert name_tuple in [loc.pathlist for loc in location_type.locations]

    for name_tuple in location_name_tree:
        deserialized_location = models.Location.get_by_pathlist(*name_tuple, session=db_session)
        assert deserialized_location is not None
        assert deserialized_location.name == name_tuple[-1]
        assert deserialized_location.pathlist == name_tuple
        sibling_type = deserialized_location.get_sibling_type(session=db_session)
        assert location_sibling_types[deserialized_location.pathlist] == sibling_type
        if len(name_tuple) == 1:
            assert deserialized_location.parent_location is None
            assert deserialized_location.is_root
        else:
            parent = deserialized_location.parent_location
            assert parent is not None
            assert not deserialized_location.is_root
            assert parent.name == name_tuple[-2]
            assert parent.pathlist == name_tuple[:-1]

        location_type_name = location_with_type_name[name_tuple]
        assert deserialized_location.location_type is not None
        assert deserialized_location.location_type.name == location_type_name
        assert deserialized_location.location_type_name == location_type_name


    # Verify that each location has the correct BaseUnits assigned, and that the relationship is bidirectional
    for name_tuple, base_unit_infos_expected in all_base_unit_infos.items():
        deserialized_location = models.Location.get_by_pathlist(*name_tuple, session=db_session)
        assert deserialized_location is not None
        base_units = sorted(
            deserialized_location.base_units,
            key=lambda bu: (bu.hostname, bu.ip_address),
        )
        expected_infos = sorted(
            base_unit_infos_expected,
            key=lambda info: (info.hostname, info.ip_address),
        )
        assert len(base_units) == len(expected_infos)
        for base_unit_model, base_unit_info in zip(base_units, expected_infos, strict=True):
            assert base_unit_model.to_data() == base_unit_info
            assert base_unit_model.location is deserialized_location


def test_location_table_display(
    db_session: Session,
    runner: CliRunner,
) -> None:
    root_a = models.Location(name="Root A")
    root_b = models.Location(name="Root B")
    root_c = models.Location(name="Root C")
    floor_1a = models.Location(name="Floor 1", parent_location=root_a)
    floor_2a = models.Location(name="Floor 2", parent_location=root_a)
    floor_1b = models.Location(name="Floor 1", parent_location=root_b)
    floor_2b = models.Location(name="Floor 2", parent_location=root_b)
    db_session.add_all([root_a, root_b, root_c, floor_1a, floor_2a, floor_1b, floor_2b])
    db_session.commit()

    result = runner.invoke(list_locations, ["-k", "name"])
    assert result.exit_code == 0
    expected_output = """\
╭─────────────────╮
│ Name            │
├─────────────────┤
│ ┌── Root A      │
│ │   ├── Floor 1 │
│ │   └── Floor 2 │
│ ├── Root B      │
│ │   ├── Floor 1 │
│ │   └── Floor 2 │
│ └── Root C      │
╰─────────────────╯
"""
    assert result.output == expected_output

    # now delete root_c and check that the display updates accordingly
    db_session.delete(root_c)
    db_session.commit()

    expected_output_after_deletion = """\
╭─────────────────╮
│ Name            │
├─────────────────┤
│ ┌── Root A      │
│ │   ├── Floor 1 │
│ │   └── Floor 2 │
│ └── Root B      │
│     ├── Floor 1 │
│     └── Floor 2 │
╰─────────────────╯
"""

    result_after_deletion = runner.invoke(list_locations, ["-k", "name"])
    assert result_after_deletion.exit_code == 0
    assert result_after_deletion.output == expected_output_after_deletion
