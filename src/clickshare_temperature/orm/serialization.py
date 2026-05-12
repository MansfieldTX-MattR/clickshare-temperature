from __future__ import annotations
from typing import Iterator
import json
from pathlib import Path

from sqlalchemy.orm import Session


from .types import FullySerializedModelTD, RelationshipNaturalKey
from .base import Base
from .models import (
    MODEL_CLASSES,
    ModelInstance,
)


def serialize_all(session: Session) -> Iterator[FullySerializedModelTD]:
    """Serialize all models in the database to an iterator of fully serialized model data."""
    for model_class in MODEL_CLASSES:
        for instance in session.query(model_class).all():
            assert isinstance(instance, Base)
            data = instance.serialize_fully()
            for key, value in data["data"].items():
                if isinstance(value, RelationshipNaturalKey):
                    data["data"][key] = value.serialize()
            yield data


def deserialize_all(
    session: Session,
    data: list[FullySerializedModelTD],
    max_iterations: int|None = None,
    limit_to_models: list[str]|None = None
) -> list[FullySerializedModelTD]:
    """Deserialize an iterator of fully serialized model data and add the instances to the database session."""
    def deserialize_model(data: FullySerializedModelTD) -> tuple[ModelInstance|None, bool]:
        for model_class in MODEL_CLASSES:
            if model_class.__tablename__ == data["model"]:
                obj, created = model_class.deserialize_fully(data, session=session)
                return obj, created
        return None, False

    data = data.copy()  # Make a copy of the data list to modify

    if limit_to_models is not None:
        model_classes = [cls for cls in MODEL_CLASSES if cls.__name__ in limit_to_models]
        model_table_names = {cls.__tablename__ for cls in model_classes}
        data = [item for item in data if item["model"] in model_table_names]
    if not len(data):
        return []
    print(f"Deserializing data for {len(data)} items, models: {set(item['model'] for item in data)}")

    # Pre-process the data to identify all relationship natural keys and
    # convert them to RelationshipNaturalKey objects before starting deserialization
    relationship_keys: set[RelationshipNaturalKey] = set()
    for i, item in enumerate(data):
        item_rel_keys: dict[str, RelationshipNaturalKey] = {}
        for key, value in item["data"].items():
            if RelationshipNaturalKey.is_relationship_natural_key(value):
                rel_key = RelationshipNaturalKey.deserialize(value)
                relationship_keys.add(rel_key)
                item_rel_keys[key] = rel_key

        if len(item_rel_keys):
            item_copy = item.copy()
            item_copy["data"] = item_copy["data"].copy()
            for key, val in item_rel_keys.items():
                item_copy["data"][key] = val
            data[i] = item_copy

    incomplete: list[FullySerializedModelTD] = data.copy()
    num_iterations = 0

    while len(incomplete) > 0:
        if max_iterations is not None and num_iterations >= max_iterations:
            break
        num_iterations += 1
        progress = False
        for item in incomplete[:]:
            num_incomplete = len(incomplete)
            obj, created = deserialize_model(item)
            if obj is not None and created:
                # print(f"Deserialized object for model {item['model']}: {obj}")
                # print(f"Original data: {item['data']}")
                session.add(obj)
                incomplete.remove(item)
                num_incomplete -= 1
                progress = True
            elif obj is not None:
                incomplete.remove(item)
                num_incomplete -= 1
                progress = True
            assert num_incomplete == len(incomplete)
        if progress:
            session.commit()
        else:
            raise ValueError("Could not deserialize all data, likely due to missing related models.")
    # if need_commit:
    #     session.commit()
    return incomplete




def _serialize_to_json(data: list[FullySerializedModelTD], indent: int|None = 2) -> str:
    """Serialize a list of fully serialized model data to a JSON string."""
    return json.dumps(data, indent=indent)


def _deserialize_from_json(json_str: str) -> list[FullySerializedModelTD]:
    """Deserialize a JSON string into a list of fully serialized model data."""
    return json.loads(json_str)


def serialize_database(session: Session, filename: Path|None = None, indent: int|None = 2) -> str:
    """Serialize the entire database to a JSON string."""
    data = list(serialize_all(session))
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
