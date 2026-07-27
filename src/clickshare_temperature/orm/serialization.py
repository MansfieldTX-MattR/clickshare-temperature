# mypy: allow-any-generics

# NOTE: the use of "allow-any-generics" is intentional here. The methods
# used to iterate over the models and their fields are dynamic and cannot be easily
# expressed with the parameters for `.types.FullySerializedModelTD`.
from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Literal, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .base import Base
from .models import (
    MODEL_CLASSES,
    ModelTableName,
)
from .types import (
    FullySerializedModelTD,
    RelationshipNaturalKey,
    RelationshipNaturalKeyTD,
)

SERIALIZATION_VERSION: Literal["1.0"] = "1.0"
"""The current version of the serialization format"""

DESERIALIZATION_VERSIONS = ("1.0",)
"""All versions of the serialization format that are supported for deserialization"""


type SerializationFormatV0 = list[FullySerializedModelTD]
"""The original (version 0) format for serialization

This was a flat list of fully serialized model data.
"""

class SerializationFormatV1(TypedDict):
    """Version 1.0 of the serialization format

    This format is a dictionary with a version string and a mapping of model table
    names to lists of fully serialized model data for that model.
    """
    version: Literal["1.0"]
    """Version of the serialization format"""
    data: Mapping[ModelTableName, Sequence[FullySerializedModelTD]]
    """A mapping of model table names to lists of fully serialized model data for that model"""


type DeSerializationFormat = SerializationFormatV0 | SerializationFormatV1
"""Union type for the possible formats that may be encountered during deserialization

This includes both the original flat list format (version 0) and newer
structured format(s), beginning with version 1.0.
"""


def serialize_all(session: Session) -> Iterator[FullySerializedModelTD]:
    """Serialize all models in the database to an iterator of fully serialized model data."""
    for model_class in MODEL_CLASSES:
        for instance in session.execute(select(model_class)).scalars():
            assert isinstance(instance, Base)
            data = instance.serialize_fully()
            for key, value in data["data"].items():
                if isinstance(value, RelationshipNaturalKey):
                    data["data"][key] = value.serialize()
            yield data


def deserialize_all(
    session: Session,
    data: SerializationFormatV1,
    max_iterations: int|None = None,
    limit_to_models: list[str]|None = None
) -> dict[ModelTableName, list[FullySerializedModelTD]]:
    """Deserialize an iterator of fully serialized model data and add the instances to the database session."""
    data = data.copy()  # Make a copy of the data to modify

    if limit_to_models is not None:
        model_classes = [cls for cls in MODEL_CLASSES if cls.__name__ in limit_to_models]
        model_table_names = {cls.__tablename__ for cls in model_classes}
        data["data"] = {model: items for model, items in data["data"].items() if model in model_table_names}
    total_items = sum(len(items) for items in data["data"].values())
    if not total_items:
        return {}
    print(f"Deserializing data for {total_items} items, models: {set(data['data'].keys())}")

    # Pre-process the data to identify all relationship natural keys and
    # convert them to RelationshipNaturalKey objects before starting deserialization
    processed_data: dict[ModelTableName, list[FullySerializedModelTD]] = {}
    for model_key in data["data"]:
        model_items = list(data["data"][model_key])
        processed_items: list[FullySerializedModelTD] = []
        for item in model_items:
            item_copy = item.copy()
            item_copy["data"] = item_copy["data"].copy()
            for key, value in item["data"].items():
                if RelationshipNaturalKey.is_relationship_natural_key(value):
                    rel_key_data: RelationshipNaturalKeyTD = {**value}
                    if isinstance(rel_key_data["related_model_key"], list):
                        # Convert lists back to tuples for immutability, if needed
                        rel_key_data["related_model_key"] = tuple(rel_key_data["related_model_key"])
                    rel_key = RelationshipNaturalKey.deserialize(rel_key_data)
                    item_copy["data"][key] = rel_key
            processed_items.append(item_copy)
        processed_data[model_key] = processed_items
    data["data"] = processed_data


    incomplete: dict[ModelTableName, list[FullySerializedModelTD]] = {
        model: list(items) for model, items in data["data"].items()
    }
    num_incomplete = sum(len(items) for items in incomplete.values())
    num_iterations = 0

    while num_incomplete > 0:
        if max_iterations is not None and num_iterations >= max_iterations:
            break
        num_iterations += 1
        iteration_progress = False

        # MODEL_CLASSES is ordered in a way that should minimize the number of
        # iterations needed to resolve all dependencies, so we iterate over it
        # rather than arbitrary order of the models in the data
        for model_cls in MODEL_CLASSES:
            model_progress = False
            model_table_name = model_cls.__tablename__
            if model_table_name not in incomplete:
                continue
            items = incomplete[model_table_name]
            if not len(items):
                del incomplete[model_table_name]
                continue
            for item in items[:]:
                obj, created = model_cls.deserialize_fully(item, session=session)
                if obj is not None and created:
                    session.add(obj)
                    items.remove(item)
                    num_incomplete -= 1
                    model_progress = True
                    iteration_progress = True
                elif obj is not None:
                    items.remove(item)
                    num_incomplete -= 1
                    model_progress = True
                    iteration_progress = True
            if model_progress:
                session.commit()
        if not iteration_progress and num_incomplete > 0:
            raise ValueError("Could not deserialize all data, likely due to missing related models.")
    return incomplete




def _serialize_to_json(data: SerializationFormatV1, indent: int|None = 2) -> str:
    """Serialize a list of fully serialized model data to a JSON string."""
    return json.dumps(data, indent=indent)


def _deserialize_from_json(json_str: str) -> SerializationFormatV1:
    """Deserialize a JSON string into a SerializationFormatTD object."""
    data: DeSerializationFormat = json.loads(json_str)
    if isinstance(data, list):
        # If the data is a list, we assume it's the old format and convert it to the new format
        model_data: dict[ModelTableName, list[FullySerializedModelTD]] = {}
        for item in data:
            model_table_name = item["model"]
            if model_table_name not in model_data:
                model_data[model_table_name] = []
            model_data[model_table_name].append(item)
        data = SerializationFormatV1(
            version=SERIALIZATION_VERSION,
            data=model_data
        )
    elif data.get("version") not in DESERIALIZATION_VERSIONS:
        raise ValueError(f"Unsupported serialization version: {data.get('version')}")
    return data


def serialize_database(session: Session, filename: Path|None = None, indent: int|None = 2) -> str:
    """Serialize the entire database to a JSON string."""
    model_data: dict[ModelTableName, list[FullySerializedModelTD]] = {}
    for item in serialize_all(session):
        model_table_name = item["model"]
        if model_table_name not in model_data:
            model_data[model_table_name] = []
        model_data[model_table_name].append(item)
    data = SerializationFormatV1(
        version="1.0",
        data=model_data
    )
    json_str = _serialize_to_json(data, indent=indent)
    if filename is not None:
        with open(filename, "w") as f:
            f.write(json_str)
    return json_str


def deserialize_database(
    session: Session,
    filename_or_data: Path | str,
    limit_to_models: list[str] | None = None
) -> None:
    """Deserialize the entire database from a JSON string or a file."""
    if isinstance(filename_or_data, Path):
        with open(filename_or_data, "r") as f:
            data = f.read()
    else:
        data = filename_or_data
    deserialize_all(session, _deserialize_from_json(data), limit_to_models=limit_to_models)
