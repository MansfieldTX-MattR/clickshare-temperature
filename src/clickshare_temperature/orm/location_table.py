from __future__ import annotations
from typing import Literal, Iterator, Sequence, NamedTuple

from sqlalchemy.orm import Session
import click
import click_extra

from .models import Location
from .utils import get_count_for_select
from .types import LocationSiblingType




class LocationTableRow(NamedTuple):
    """A class representing a row to display :class:`.Location` data in a table format
    """
    id: int
    """ID of the Location"""
    name: str
    """The :attr:`~.Location.name` of the Location"""
    type: str|None
    """The name of the :class:`.LocationType` of the Location, if any"""
    sibling_type: LocationSiblingType
    """The :meth:`sibling type <.Location.get_sibling_type>` of the Location"""
    index_: int
    """The index of the Location

    This is an arbitrary index assigned to each Location when generating the table data.
    It is not related to the :class:`.Location` or any of its database fields.
    """
    is_root: bool
    """Whether the Location is a root location (i.e. has no parent)"""
    nest_level: int
    """The :attr:`nesting level <.Location.nest_level>` of the Location"""
    baseunit_count: int
    """The number of BaseUnits assigned to this Location"""
    baseunit_total_count: int
    """The total number of BaseUnits assigned to this Location and all of its
    descendant Locations
    """
    parent: LocationTableRow|None = None
    """The parent LocationTableRow, if any"""

    @property
    def parent_name(self) -> str:
        """Get the :attr:`name` of the parent LocationTableRow, if any"""
        return self.parent.name if self.parent else ""

    def get_all_ancestors(self) -> list[LocationTableRow]:
        """Get a list of all ancestor LocationTableRows, starting with the
        parent and going up to the root
        """
        ancestors = []
        current = self.parent
        while current is not None:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def format_table_prefix(self) -> str:
        """Format the prefix for a location based on its depth in the location hierarchy

        The resulting prefix will render the tree structure of the locations when
        displayed in a monospaced font, like in the example below:

        .. code-block:: none

            ┌── Location 1
            │   ├── Child Location 1.1
            │   ├── Child Location 1.2
            │   │   └── Child Location 1.2.1
            │   ├── Child Location 1.3
            │   ├── Child Location 1.4
            │   ├── Child Location 1.5
            │   ├── Child Location 1.6
            │   └── Child Location 1.7
            │       ├── Child Location 1.7.1
            │       ├── Child Location 1.7.2
            │       └── Child Location 1.7.3
            ├── Location 2
            └── Location 3


        """
        first_root_prefix           = "┌── "
        first_only_child_prefix     = "└── "
        first_child_prefix          = "├── "
        middle_child_prefix         = "├── "
        last_child_prefix           = "└── "
        outer_prefix                = "│   "
        blank_prefix                = "    "

        root_prefixes: dict[LocationSiblingType, str] = {
            "only": first_root_prefix,
            "first": first_root_prefix,
            "middle": middle_child_prefix,
            "last": last_child_prefix,
        }

        child_prefixes: dict[LocationSiblingType, str] = {
            "only": first_only_child_prefix,
            "first": first_child_prefix,
            "middle": middle_child_prefix,
            "last": last_child_prefix,
        }

        item_prefix: str
        if self.is_root:
            item_prefix = root_prefixes[self.sibling_type]
        else:
            item_prefix = child_prefixes[self.sibling_type]

        if self.is_root:
            return item_prefix

        ancestors = self.get_all_ancestors()
        ancestor_prefixes = []
        for ancestor in ancestors:
            if ancestor.sibling_type in ("first", "middle"):
                ancestor_prefixes.append(outer_prefix)
            else:
                ancestor_prefixes.append(blank_prefix)
        ancestor_prefixes.reverse()
        full_prefix = "".join(ancestor_prefixes) + item_prefix
        return full_prefix

    def format_table_name(self) -> str:
        """Format the name for display in the table, including indentation and prefix"""
        prefix = self.format_table_prefix()
        return prefix + self.name

    def format_attr(self, key: LocationTableKey) -> str:
        """Format a specific attribute for display in the table, applying any necessary
        formatting based on the attribute type or value

        Arguments:
            key: The key of the attribute to format

        Returns:
            The formatted string to display in the table for this attribute
        """
        value = getattr(self, key)
        if key == "name":
            return self.format_table_name()
        elif key == "type" and value is None:
            return ""
        return str(value)

    def get_table_row_items(
        self,
        header_keys: Sequence[LocationTableKey],
        highlight: bool = False
    ) -> tuple[str, ...]:
        """Get a tuple of the items to display in the table for this row,
        in the order of the header keys

        Arguments:
            header_keys: The keys to include in the table row and the order to display them in
            highlight: Whether to apply highlighting to the table row
                (e.g. for the currently selected Location)

        Returns:
            A tuple of the items to display in the table for this row,
            in the order of the header keys
        """
        row_items = tuple(self.format_attr(key) for key in header_keys)
        if highlight:
            row_items = tuple(
                click.style(str(item), fg=click_extra.Color.bright_white, bold=True)
                for item in row_items
            )
        return row_items



type LocationTableKey = Literal[
    "id", "name", "type", "index_", "nest_level", "parent", "sibling_type",
    "is_root", "parent_name", "baseunit_count", "baseunit_total_count",
]
"""A type representing the keys for the :class:`LocationTableRow` table display"""

LOCATION_TABLE_TITLES: dict[LocationTableKey, str] = {
    "id": "ID",
    "name": "Name",
    "type": "Type",
    "index_": "Index",
    "nest_level": "Nest Level",
    "parent": "Parent",
    "parent_name": "Parent Name",
    "sibling_type": "Sibling Type",
    "is_root": "Is Root",
    "baseunit_count": "BaseUnits",
    "baseunit_total_count": "Total BaseUnits",
}
"""A mapping of :class:`LocationTableKey` to the display titles for the table header"""

DEFAULT_LOCATION_TABLE_KEYS: tuple[LocationTableKey, ...] = (
    "id", "name", "type", "baseunit_total_count", "baseunit_count",
)
"""The default keys to display in the location table, in order"""


def get_location_table_data(session: Session) -> list[LocationTableRow]:
    """Get a list of :class:`LocationTableRow` for all locations in the database

    The :attr:`index_` field of each LocationTableRow is assigned based on the
    order of the locations in depth-first traversal of the hierarchy.
    """
    data: list[LocationTableRow] = []
    root_locations = Location.get_root_locations(session=session)
    current_index = 0

    def handle_location(
        location: Location,
        parent: LocationTableRow|None = None
    ) -> Iterator[LocationTableRow]:
        """Iterator function to build a :class:`LocationTableRow` for a given
        :class:`Location` and recursively handle its child locations
        """
        nonlocal current_index
        baseunit_total_count = get_count_for_select(
            location.select_base_units(include_descendants=True),
            session=session
        )
        obj = LocationTableRow(
            id=location.id,
            name=location.name,
            type=location.location_type_name,
            sibling_type=location.get_sibling_type(session),
            index_=current_index,
            is_root=location.is_root,
            nest_level=location.nest_level,
            baseunit_count=len(location.base_units),
            baseunit_total_count=baseunit_total_count,
            parent=parent,
        )
        yield obj
        current_index += 1
        for child in location.child_locations:
            yield from handle_location(child, parent=obj)

    for root_location in root_locations:
        for row_data in handle_location(root_location):
            data.append(row_data)
    all_indices = [row.index_ for row in data]
    assert all_indices == list(range(len(data)))
    return data



def show_locations_table(
    ctx: click.Context,
    session: Session,
    header_keys: Sequence[LocationTableKey] | None = None,
    highlight_location_id: int | None = None,
) -> list[LocationTableRow]:
    """Show a table of all locations in the database, with indentation based
    on their depth in the location hierarchy

    Arguments:
        ctx: The Click context to use for printing the table
        session: The database session to use for querying the locations
        header_keys: The keys to include in the table header and the order to display them in

    Returns:
        A list of :class:`LocationTableRow` items for all locations in the database
    """
    if header_keys is None:
        header_keys = DEFAULT_LOCATION_TABLE_KEYS
    header = [LOCATION_TABLE_TITLES[key] for key in header_keys]
    data = get_location_table_data(session)

    table_data: list[tuple[str, ...]] = []
    for row_data in data:
        highlight = row_data.id == highlight_location_id
        table_data.append(row_data.get_table_row_items(header_keys, highlight=highlight))

    # IMPORTANT: Use preserve_whitespace=True to ensure the indentation of the
    # location names is preserved in the table output
    ctx.print_table(table_data, header, preserve_whitespace=True) # type: ignore[attr-defined]
    return data
