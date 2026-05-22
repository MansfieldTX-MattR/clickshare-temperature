from __future__ import annotations
from typing import NewType, Union, Literal, Self
import datetime

from aiohttp import ClientSession
from sqlalchemy.orm import Session

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    Query,
)
from sqlalchemy import ForeignKey, tuple_
from sqlalchemy.schema import UniqueConstraint

from .base import Base
from ..types import (
    AioHttpRequestOptions,
    SensorType,
    BaseUnitInfo,
    BaseUnitIdentity as BaseUnitIdentityData,
    PowerMode,
    PowerModeStatus,
    PowerManagementInfo,
    AuthInfo,
    BaseUnitStatusErrorCode,
    BaseUnitStatus as BaseUnitStatusData,
    BaseUnitUsageStatus as BaseUnitUsageStatusData,
)
from ..baseunit_api import DEFAULT_REQUEST_OPTIONS
from ..temperature_history import (
    SensorReading as SensorReadingData,
    TemperatureHistory as TemperatureHistoryData,
)
from .. import timezone
from ..timezone import ensure_aware
from ..utils import click_secho
from .types import Ordering, RelationshipNaturalKey, _BaseModelSerializeTD

DtIsoStr = NewType("DtIsoStr", str)


type BaseUnitNaturalKey = str
type BaseUnitOnlineStatusNaturalKey = tuple[BaseUnitNaturalKey, int]
type BaseUnitIdentityNaturalKey = BaseUnitNaturalKey
type PowerManagementStatusNaturalKey = tuple[BaseUnitNaturalKey, int]
type PowerManagementSettingsNaturalKey = BaseUnitNaturalKey
type BaseUnitStatusNaturalKey = tuple[BaseUnitNaturalKey, int]
type BaseUnitUsageStatusNaturalKey = tuple[BaseUnitNaturalKey, int]
type SensorReadingNaturalKey = tuple[BaseUnitNaturalKey, int]




class _BaseUnitSerializeTD(_BaseModelSerializeTD[BaseUnitNaturalKey]):
    ip_address: str
    hostname: str
    room_name: str

class _BaseUnitOnlineStatusSerializeTD(_BaseModelSerializeTD[BaseUnitOnlineStatusNaturalKey]):
    base_unit: RelationshipNaturalKey[BaseUnitNaturalKey]
    timestamp: DtIsoStr
    online: bool
    uploaded_to_influx: bool

class _BaseUnitIdentitySerializeTD(_BaseModelSerializeTD[BaseUnitIdentityNaturalKey]):
    base_unit: RelationshipNaturalKey[BaseUnitNaturalKey]
    article_number: str
    hardware_version: str
    model_name: str
    product_name: str
    serial_number: str

class _PowerManagementStatusSerializeTD(_BaseModelSerializeTD[PowerManagementStatusNaturalKey]):
    base_unit: RelationshipNaturalKey[BaseUnitNaturalKey]
    timestamp: DtIsoStr
    power_mode_status: PowerModeStatus
    uploaded_to_influx: bool


class _PowerManagementSettingsSerializeTD(_BaseModelSerializeTD[PowerManagementSettingsNaturalKey]):
    base_unit: RelationshipNaturalKey[BaseUnitNaturalKey]
    mode: PowerMode
    standby_timeout: int|None


class _BaseUnitStatusSerializeTD(_BaseModelSerializeTD[BaseUnitStatusNaturalKey]):
    base_unit: RelationshipNaturalKey[BaseUnitNaturalKey]
    timestamp: DtIsoStr
    current_uptime: int
    total_uptime: int
    error_code: BaseUnitStatusErrorCode
    error_message: str|None
    first_used: DtIsoStr
    in_use: bool
    sharing: bool
    uploaded_to_influx: bool


class _SensorReadingSerializeTD(_BaseModelSerializeTD[SensorReadingNaturalKey]):
    base_unit: RelationshipNaturalKey[BaseUnitNaturalKey]
    timestamp: DtIsoStr
    sensor_type: SensorType
    value: float
    uploaded_to_influx: bool


class _BaseUnitUsageStatusSerializeTD(_BaseModelSerializeTD[BaseUnitUsageStatusNaturalKey]):
    base_unit: RelationshipNaturalKey[BaseUnitNaturalKey]
    timestamp: DtIsoStr
    in_use: bool
    sharing: bool
    uploaded_to_influx: bool



class BaseUnit(Base[BaseUnitNaturalKey, _BaseUnitSerializeTD]):
    """ORM model for a ClickShare BaseUnit
    """
    # __tablename__: ClassVar[ModelTableName] = "base_units"
    __tablename__ = "base_units"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ip_address: Mapped[str] = mapped_column(nullable=False)
    """IP address of the BaseUnit"""
    hostname: Mapped[str] = mapped_column(unique=True, nullable=False)
    """Hostname of the BaseUnit, which is used as the natural key"""
    room_name: Mapped[str] = mapped_column(nullable=False)
    """Name of the room where the BaseUnit is located"""

    identity: Mapped[BaseUnitIdentity] = relationship(
        "BaseUnitIdentity",
        uselist=False,
        back_populates="base_unit",
    )
    """The :class:`BaseUnitIdentity` associated with this BaseUnit"""

    power_management_settings: Mapped[PowerManagementSettings] = relationship(
        "PowerManagementSettings",
        uselist=False,
        back_populates="base_unit",
    )
    """The :class:`PowerManagementSettings` associated with this BaseUnit"""

    online_statuses: Mapped[list[BaseUnitOnlineStatus]] = relationship(
        "BaseUnitOnlineStatus",
        back_populates="base_unit",
        cascade="all, delete-orphan",
    )
    """The list of :class:`BaseUnitOnlineStatus` entries associated with this BaseUnit"""

    power_management_statuses: Mapped[list[PowerManagementStatus]] = relationship(
        "PowerManagementStatus",
        back_populates="base_unit",
        cascade="all, delete-orphan",
    )
    """The list of :class:`PowerManagementStatus` entries associated with this BaseUnit"""

    statuses: Mapped[list[BaseUnitStatus]] = relationship(
        "BaseUnitStatus",
        back_populates="base_unit",
        cascade="all, delete-orphan",
    )
    """The list of :class:`BaseUnitStatus` entries associated with this BaseUnit"""

    usage_statuses: Mapped[list[BaseUnitUsageStatus]] = relationship(
        "BaseUnitUsageStatus",
        back_populates="base_unit",
        cascade="all, delete-orphan",
    )
    """The list of :class:`BaseUnitUsageStatus` entries associated with this BaseUnit"""

    sensor_readings: Mapped[list[SensorReading]] = relationship(
        "SensorReading",
        back_populates="base_unit",
        cascade="all, delete-orphan",
    )
    """The list of :class:`SensorReading` entries associated with this BaseUnit"""

    @property
    def natural_key(self) -> BaseUnitNaturalKey:
        """The natural key for this instance
        """
        return self.hostname

    @classmethod
    def get_by_natural_key(cls, session: Session, key: BaseUnitNaturalKey) -> Self|None:
        """Get the instance of this model from the given natural key

        If no instance exists, ``None`` is returned.
        """
        return session.query(cls).filter_by(hostname=key).one_or_none()

    def serialize(self) -> _BaseUnitSerializeTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return {
            "natural_key": self.natural_key,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "room_name": self.room_name,
        }

    @classmethod
    def deserialize(cls, data: _BaseUnitSerializeTD, session: Session) -> Self|None:
        """Deserialize a dictionary into a an instance of this model
        """
        return cls(
            ip_address=data["ip_address"],
            hostname=data["hostname"],
            room_name=data["room_name"],
        )

    @classmethod
    def from_info(cls, info: BaseUnitInfo) -> Self:
        """Create a BaseUnit ORM instance from a :class:`.types.BaseUnitInfo` instance
        """
        return cls(
            ip_address=info.ip_address,
            hostname=info.hostname,
            room_name=info.room_name,
        )

    @classmethod
    def get_or_create(cls, info: BaseUnitInfo, session: Session) -> tuple[Self, bool]:
        """Get a BaseUnit from the database matching the given :class:`.types.BaseUnitInfo`,
        or create it if it doesn't exist
        """
        created = False
        instance = session.query(cls).filter(
            cls.hostname == info.hostname
        ).one_or_none()
        if instance is not None:
            changed = False
            if instance.ip_address != info.ip_address:
                instance.ip_address = info.ip_address
                changed = True
            if instance.room_name != info.room_name:
                instance.room_name = info.room_name
                changed = True
            if changed:
                session.add(instance)
            return instance, created
        else:
            instance = cls.from_info(info)
            created = True
            return instance, created

    def to_data(self) -> BaseUnitInfo:
        """Convert this instance into a :class:`.types.BaseUnitInfo` instance
        """
        return BaseUnitInfo(
            ip_address=self.ip_address,
            hostname=self.hostname,
            room_name=self.room_name,
        )

    def last_online_status(self) -> bool|None:
        """Get the most recent online status for this BaseUnit, or None if no statuses exist
        """
        last_status = self.last_online_status_instance()
        if last_status is None:
            return None
        return last_status.online

    def last_online_status_instance(self) -> BaseUnitOnlineStatus|None:
        """Get the most recent :class:`BaseUnitOnlineStatus` for this BaseUnit, or None if no statuses exist
        """
        session = self._get_current_orm_session()
        return session.query(BaseUnitOnlineStatus).filter_by(
            base_unit_id=self.id
        ).order_by(BaseUnitOnlineStatus.timestamp.desc()).first()

    def set_online_status(
        self,
        online: bool,
        timestamp: datetime.datetime|None = None
    ) -> None:
        """Set the online status for this BaseUnit, creating a new
        :class:`BaseUnitOnlineStatus` entry in the database

        Arguments:
            online (bool): Whether the BaseUnit is online or offline
            timestamp (datetime.datetime|None): The timestamp for the new status entry.
                If None, the current time is used.
        """
        session = self._get_current_orm_session()
        with session.begin_nested():
            last_status = self.last_online_status()
            if last_status is not None and last_status == online:
                # No need to create a new status entry if the online status hasn't changed
                return
            if timestamp is None:
                timestamp = timezone.utcnow()
            else:
                timezone.ensure_aware(timestamp)
            online_status = BaseUnitOnlineStatus(
                base_unit_id=self.id,
                timestamp=timestamp,
                online=online,
            )
            session.add(online_status)
            session.commit()

    async def add_sensor_readings_from_api(
        self,
        auth_info: AuthInfo,
        session: Session,
        aiohttp_session: ClientSession,
        request_options: AioHttpRequestOptions|None = None,
    ) -> None:
        """Fetch sensor readings for this BaseUnit from the API and add them to the database
        """
        request_options = request_options or DEFAULT_REQUEST_OPTIONS
        temperature_history_data = await TemperatureHistoryData.from_baseunit(
            self.ip_address,
            auth_info=auth_info,
            session=aiohttp_session,
            **request_options,
        )
        dt_sensor_keys = set((timezone.ensure_aware(r.timestamp), r.sensor) for r in temperature_history_data.readings)

        existing_readings = session.query(SensorReading).filter(
            SensorReading.base_unit_id == self.id,
            tuple_(SensorReading.timestamp, SensorReading.sensor_type).in_(dt_sensor_keys),
        ).all()
        existing_keys = set((r.timestamp, r.sensor_type) for r in existing_readings)
        click_secho(f"Fetched {len(temperature_history_data.readings)} sensor readings for BaseUnit '{self.hostname}'", fg="blue")
        num_added = 0
        for reading in temperature_history_data.readings:
            key = (timezone.ensure_aware(reading.timestamp), reading.sensor)
            if key in existing_keys:
                continue
            instance = self.add_sensor_reading(reading, session)
            session.add(instance)
            num_added += 1
        click_secho(f"Added {num_added} sensor readings for BaseUnit '{self.hostname}' to the database", fg="green")

    def add_sensor_readings(
        self,
        readings: list[SensorReadingData[SensorType]],
        session: Session
    ) -> tuple[int, int]:
        """Add multiple sensor readings to this BaseUnit

        Returns:
            A tuple of (num_added, num_skipped) indicating how many readings
                were added and how many were skipped due to already existing in the database.
        """
        dt_sensor_keys = set((timezone.ensure_aware(r.timestamp), r.sensor) for r in readings)
        existing_readings = session.query(SensorReading).filter(
            SensorReading.base_unit_id == self.id,
            tuple_(SensorReading.timestamp, SensorReading.sensor_type).in_(dt_sensor_keys),
        ).all()
        existing_keys = set((r.timestamp, r.sensor_type) for r in existing_readings)
        num_added = 0
        num_skipped = 0
        for reading in readings:
            key = (timezone.ensure_aware(reading.timestamp), reading.sensor)
            if key in existing_keys:
                num_skipped += 1
                continue
            instance = self.add_sensor_reading(reading, session)
            assert not instance.uploaded_to_influx, "New sensor reading should not be marked as uploaded to InfluxDB"
            session.add(instance)
            num_added += 1
        return num_added, num_skipped

    def add_sensor_reading(self, reading: SensorReadingData[SensorType], session: Session) -> SensorReading:
        """Add a :class:`SensorReading` to this BaseUnit."""
        sensor_reading = SensorReading.from_data(self, reading, session)
        session.add(sensor_reading)
        return sensor_reading

    def has_sensor_reading(self, reading: SensorReadingData[SensorType], session: Session) -> bool:
        """Check if a :class:`SensorReading` already exists for this BaseUnit

        The reading's timestamp and sensor type are used to determine if it
        already exists in the database.
        """
        timestamp = timezone.ensure_aware(reading.timestamp)
        existing_reading = session.query(SensorReading).filter_by(
            base_unit_id=self.id,
            timestamp=timestamp,
            sensor_type=reading.sensor,
        ).one_or_none()
        return existing_reading is not None

    def get_sensor_readings(
        self,
        session: Session,
        sensor_type: SensorType|None = None,
        order_by: Ordering|None = None
    ) -> Query[SensorReading]:
        """Get sensor readings for this BaseUnit, optionally filtered by sensor type
        """
        query = session.query(SensorReading).filter_by(base_unit_id=self.id)
        if sensor_type is not None:
            query = query.filter_by(sensor_type=sensor_type)
        if order_by == "desc":
            return query.order_by(SensorReading.timestamp.desc())
        elif order_by == "asc":
            return query.order_by(SensorReading.timestamp.asc())
        return query

    def to_temperature_history_data(
        self,
        session: Session,
        sensor_query: Query[SensorReading]|None = None
    ) -> TemperatureHistoryData:
        """Convert this BaseUnit and its sensor readings to a
        :class:`.temperature_history.TemperatureHistory` instance
        """
        if sensor_query is None:
            sensor_query = self.get_sensor_readings(session)
        readings = [
            r.to_data() for r in sensor_query.all()
        ]
        base_unit = BaseUnitInfo(
            ip_address=self.ip_address,
            hostname=self.hostname,
            room_name=self.room_name,
        )
        return TemperatureHistoryData(
            base_unit=base_unit,
            readings=readings,
        )

    def __repr__(self) -> str:
        return f"<BaseUnit(id={self.id}, ip_address={self.ip_address}, hostname={self.hostname}, room_name={self.room_name})>"

    def __str__(self) -> str:
        return f"BaseUnit '{self.room_name}' ({self.hostname}) - {self.ip_address}"



class BaseUnitOnlineStatus(Base[BaseUnitOnlineStatusNaturalKey, _BaseUnitOnlineStatusSerializeTD]):
    """ORM model for the online status of a ClickShare BaseUnit at a given point in time
    """
    __tablename__ = "base_unit_online_statuses"
    __table_args__ = (
        UniqueConstraint("base_unit_id", "timestamp", name="uix_base_unit_online_status_base_unit_timestamp"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(index=True, nullable=False)
    """Timestamp of the online status entry"""
    online: Mapped[bool] = mapped_column(nullable=False)
    """Whether the BaseUnit is online (True) or offline (False)"""
    uploaded_to_influx: Mapped[bool] = mapped_column(nullable=False, default=False)
    """Whether this status entry has been uploaded to InfluxDB"""
    base_unit_id: Mapped[int] = mapped_column(ForeignKey("base_units.id"), nullable=False)

    base_unit: Mapped[BaseUnit] = relationship("BaseUnit", back_populates="online_statuses")

    @property
    def natural_key(self) -> BaseUnitOnlineStatusNaturalKey:
        """Get the natural key for this instance
        """
        return (
            self.base_unit.natural_key,
            self.id,
        )

    @classmethod
    def get_by_natural_key(cls, session: Session, key: BaseUnitOnlineStatusNaturalKey) -> Self|None:
        """Get the instance of this model from the given natural key

        If no instance exists, ``None`` is returned.
        """
        base_unit_hostname, pk = key
        base_unit = BaseUnit.get_by_natural_key(session, base_unit_hostname)
        if base_unit is None:
            return None
        return session.query(cls).filter_by(
            base_unit_id=base_unit.id, id=pk
        ).one_or_none()

    def serialize(self) -> _BaseUnitOnlineStatusSerializeTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return _BaseUnitOnlineStatusSerializeTD(
            natural_key=self.natural_key,
            base_unit=RelationshipNaturalKey(
                related_model_table="base_units",
                related_model_key=self.base_unit.natural_key,
            ),
            timestamp=DtIsoStr(self.timestamp.isoformat()),
            online=self.online,
            uploaded_to_influx=self.uploaded_to_influx,
        )

    @classmethod
    def deserialize(cls, data: _BaseUnitOnlineStatusSerializeTD, session: Session) -> Self|None:
        """Deserialize a dictionary into an instance of this model
        """
        assert isinstance(data["base_unit"], RelationshipNaturalKey), f"Expected 'base_unit' to be a RelationshipNaturalKey, got {data['base_unit']}"
        base_unit = BaseUnit.get_by_natural_key(session, data["base_unit"].related_model_key)
        if base_unit is None:
            return None
        return cls(
            base_unit_id=base_unit.id,
            timestamp=timezone.ensure_aware(datetime.datetime.fromisoformat(data["timestamp"])),
            online=data["online"],
            uploaded_to_influx=data["uploaded_to_influx"],
        )

    def __repr__(self) -> str:
        return f"<BaseUnitOnlineStatus(id={self.id}, base_unit={self.base_unit}, timestamp={self.timestamp}, online={self.online})>"

    def __str__(self) -> str:
        return f"BaseUnitOnlineStatus for {self.base_unit} at {self.timestamp}: {'Online' if self.online else 'Offline'}"


class BaseUnitIdentity(Base[BaseUnitIdentityNaturalKey, _BaseUnitIdentitySerializeTD]):
    """ORM model for the identity information of a ClickShare BaseUnit
    """
    __tablename__ = "base_unit_identities"
    __table_args__ = (
        UniqueConstraint("serial_number", name="uix_serial_number"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    base_unit_id: Mapped[int] = mapped_column(ForeignKey("base_units.id"), unique=True, nullable=False)
    article_number: Mapped[str]
    hardware_version: Mapped[str]
    model_name: Mapped[str]
    product_name: Mapped[str]
    serial_number: Mapped[str]

    base_unit: Mapped[BaseUnit] = relationship(back_populates="identity")

    @property
    def natural_key(self) -> BaseUnitIdentityNaturalKey:
        """Get the natural key for this instance
        """
        return self.base_unit.natural_key

    @classmethod
    def get_by_natural_key(cls, session: Session, key: BaseUnitIdentityNaturalKey) -> Self|None:
        """Get the instance of this model from the given natural key

        If no instance exists, ``None`` is returned.
        """
        base_unit = BaseUnit.get_by_natural_key(session, key)
        if base_unit is None:
            return None
        return session.query(cls).filter_by(
            base_unit_id=base_unit.id
        ).one_or_none()

    def serialize(self) -> _BaseUnitIdentitySerializeTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return {
            "natural_key": self.natural_key,
            "base_unit": RelationshipNaturalKey(
                related_model_table="base_units",
                related_model_key=self.base_unit.natural_key,
            ),
            "article_number": self.article_number,
            "hardware_version": self.hardware_version,
            "model_name": self.model_name,
            "product_name": self.product_name,
            "serial_number": self.serial_number,
        }

    @classmethod
    def deserialize(cls, data: _BaseUnitIdentitySerializeTD, session: Session) -> Self|None:
        """Deserialize a dictionary into a an instance of this model
        """
        assert isinstance(data["base_unit"], RelationshipNaturalKey), f"Expected 'base_unit' to be a RelationshipNaturalKey, got {data['base_unit']}"
        base_unit = BaseUnit.get_by_natural_key(session, data["base_unit"].related_model_key)
        if base_unit is None:
            return None
        return cls(
            base_unit_id=base_unit.id,
            article_number=data["article_number"],
            hardware_version=data["hardware_version"],
            model_name=data["model_name"],
            product_name=data["product_name"],
            serial_number=data["serial_number"],
        )

    @classmethod
    def from_data(cls, base_unit: int|BaseUnit, data: BaseUnitIdentityData, session: Session) -> Self:
        """Create an instance of this model from a :class:`.types.BaseUnitIdentityData` instance
        """
        if isinstance(base_unit, BaseUnit):
            base_unit = base_unit.id
        return cls(
            base_unit_id=base_unit,
            article_number=data.article_number,
            hardware_version=data.hardware_version,
            model_name=data.model_name,
            product_name=data.product_name,
            serial_number=data.serial_number,
        )

    def to_data(self) -> BaseUnitIdentityData:
        """Convert this instance to a :class:`.types.BaseUnitIdentityData` instance
        """
        return BaseUnitIdentityData(
            article_number=self.article_number,
            hardware_version=self.hardware_version,
            model_name=self.model_name,
            product_name=self.product_name,
            serial_number=self.serial_number,
        )

    def __repr__(self) -> str:
        return f"<BaseUnitIdentity(id={self.id}, base_unit={self.base_unit})>"

    def __str__(self) -> str:
        return f"BaseUnitIdentity for {self.base_unit}"




class PowerManagementSettings(Base[PowerManagementSettingsNaturalKey, _PowerManagementSettingsSerializeTD]):
    """ORM model for the power management settings of a ClickShare BaseUnit
    """
    __tablename__ = "power_management_settings"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    base_unit_id: Mapped[int] = mapped_column(ForeignKey("base_units.id"), unique=True, nullable=False)
    mode: Mapped[PowerMode]
    standby_timeout: Mapped[int|None]

    base_unit: Mapped[BaseUnit] = relationship("BaseUnit", back_populates="power_management_settings")


    @property
    def natural_key(self) -> PowerManagementSettingsNaturalKey:
        """Get the natural key for this instance
        """
        return self.base_unit.natural_key

    @classmethod
    def get_by_natural_key(cls, session: Session, key: PowerManagementSettingsNaturalKey) -> Self|None:
        """Get the instance of this model from the given natural key

        If no instance exists, ``None`` is returned.
        """
        base_unit = BaseUnit.get_by_natural_key(session, key)
        if base_unit is None:
            return None
        return session.query(cls).filter_by(base_unit_id=base_unit.id).one_or_none()

    def serialize(self) -> _PowerManagementSettingsSerializeTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return {
            "natural_key": self.natural_key,
            "base_unit": RelationshipNaturalKey(
                related_model_table="base_units",
                related_model_key=self.base_unit.natural_key,
            ),
            "mode": self.mode,
            "standby_timeout": self.standby_timeout,
        }

    @classmethod
    def deserialize(cls, data: _PowerManagementSettingsSerializeTD, session: Session) -> Self|None:
        """Deserialize a dictionary into a an instance of this model
        """
        assert isinstance(data["base_unit"], RelationshipNaturalKey), f"Expected 'base_unit' to be a RelationshipNaturalKey, got {data['base_unit']}"
        base_unit = BaseUnit.get_by_natural_key(session, data["base_unit"].related_model_key)
        if base_unit is None:
            return None
        return cls(
            base_unit_id=base_unit.id,
            mode=data["mode"],
            standby_timeout=data["standby_timeout"],
        )

    @classmethod
    def from_data(cls, base_unit: int|BaseUnit, data: PowerManagementInfo, session: Session) -> Self:
        """Create an instance of this model from a :class:`.types.PowerManagementInfo` instance
        """
        if isinstance(base_unit, BaseUnit):
            base_unit = base_unit.id
        return cls(
            base_unit_id=base_unit,
            mode=data.power_mode,
            standby_timeout=data.standby_timeout_minutes,
        )

    def update_from_data(self, data: PowerManagementInfo) -> bool:
        """Update this instance from a :class:`.types.PowerManagementInfo` instance

        Returns:
            bool: True if any fields were updated, False otherwise
        """
        changed = False
        if self.mode != data.power_mode:
            self.mode = data.power_mode
            changed = True

        if self.standby_timeout != data.standby_timeout_minutes:
            self.standby_timeout = data.standby_timeout_minutes
            changed = True
        return changed

    def __repr__(self) -> str:
        return f"<PowerManagementSettings(id={self.id}, base_unit={self.base_unit}, mode={self.mode}, standby_timeout={self.standby_timeout})>"

    def __str__(self) -> str:
        return f"PowerManagementSettings for {self.base_unit}"




class PowerManagementStatus(Base[PowerManagementStatusNaturalKey, _PowerManagementStatusSerializeTD]):
    """ORM model for the power state of a ClickShare BaseUnit at a given point in time
    """
    __tablename__ = "power_management_status"
    __table_args__ = (
        UniqueConstraint("base_unit_id", "timestamp", name="uix_power_management_status_base_unit_timestamp"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    base_unit_id: Mapped[int] = mapped_column(ForeignKey("base_units.id"), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(index=True, nullable=False)
    power_mode_status: Mapped[PowerModeStatus]
    uploaded_to_influx: Mapped[bool] = mapped_column(nullable=False, default=False)

    base_unit: Mapped[BaseUnit] = relationship("BaseUnit", back_populates="power_management_statuses")

    @property
    def natural_key(self) -> PowerManagementStatusNaturalKey:
        """Get the natural key for this instance
        """
        return (
            self.base_unit.natural_key,
            self.id,
        )

    @classmethod
    def get_by_natural_key(cls, session: Session, key: PowerManagementStatusNaturalKey) -> Self|None:
        """Get the instance of this model from the given natural key

        If no instance exists, ``None`` is returned.
        """
        base_unit_key, pk = key
        base_unit = BaseUnit.get_by_natural_key(session, base_unit_key)
        if base_unit is None:
            return None
        return session.query(cls).filter_by(base_unit_id=base_unit.id, id=pk).one_or_none()

    def serialize(self) -> _PowerManagementStatusSerializeTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return {
            "natural_key": self.natural_key,
            "base_unit": RelationshipNaturalKey(
                related_model_table="base_units",
                related_model_key=self.base_unit.natural_key,
            ),
            "timestamp": DtIsoStr(self.timestamp.isoformat()),
            "power_mode_status": self.power_mode_status,
            "uploaded_to_influx": self.uploaded_to_influx,
        }

    @classmethod
    def deserialize(cls, data: _PowerManagementStatusSerializeTD, session: Session) -> Self|None:
        """Deserialize a dictionary into an instance of this model
        """
        assert isinstance(data["base_unit"], RelationshipNaturalKey), f"Expected 'base_unit' to be a RelationshipNaturalKey, got {data['base_unit']}"
        base_unit = BaseUnit.get_by_natural_key(session, data["base_unit"].related_model_key)
        if base_unit is None:
            return None
        return cls(
            base_unit_id=base_unit.id,
            timestamp=timezone.ensure_aware(datetime.datetime.fromisoformat(data["timestamp"])),
            power_mode_status=data["power_mode_status"],
            uploaded_to_influx=data["uploaded_to_influx"],
        )

    @classmethod
    def from_data(cls, base_unit: int|BaseUnit, data: PowerManagementInfo, now: datetime.datetime|None = None) -> Self:
        """Create an instance of this model from a :class:`.types.PowerManagementInfo` instance
        """
        if isinstance(base_unit, BaseUnit):
            base_unit = base_unit.id
        if now is None:
            now = timezone.utcnow()
        else:
            timezone.ensure_aware(now)
        return cls(
            base_unit_id=base_unit,
            timestamp=now,
            power_mode_status=data.status,
        )

    def __repr__(self) -> str:
        return f"<PowerManagementStatus(id={self.id}, base_unit={self.base_unit}, timestamp={self.timestamp}, power_mode_status={self.power_mode_status})>"

    def __str__(self) -> str:
        return f"PowerManagementStatus for {self.base_unit} at {self.timestamp}: {self.power_mode_status}"


class BaseUnitStatus(Base[BaseUnitStatusNaturalKey, _BaseUnitStatusSerializeTD]):
    """ORM model for the status of a ClickShare BaseUnit at a given point in time
    """
    __tablename__ = "base_unit_statuses"
    __table_args__ = (
        UniqueConstraint("base_unit_id", "timestamp", name="uix_base_unit_timestamp"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(index=True, nullable=False)
    base_unit_id: Mapped[int] = mapped_column(ForeignKey("base_units.id"), nullable=False)
    current_uptime: Mapped[int] = mapped_column(nullable=False)
    total_uptime: Mapped[int] = mapped_column(nullable=False)
    error_code: Mapped[BaseUnitStatusErrorCode] = mapped_column(nullable=False)
    error_message: Mapped[str] = mapped_column(nullable=True)
    first_used: Mapped[datetime.datetime] = mapped_column(nullable=False)
    in_use: Mapped[bool] = mapped_column(nullable=False)
    sharing: Mapped[bool] = mapped_column(nullable=False)
    uploaded_to_influx: Mapped[bool] = mapped_column(nullable=False, default=False)

    base_unit: Mapped[BaseUnit] = relationship(BaseUnit, back_populates="statuses")

    @property
    def natural_key(self) -> BaseUnitStatusNaturalKey:
        """Get the natural key for this instance
        """
        return (
            self.base_unit.natural_key,
            self.id,
        )

    def serialize(self) -> _BaseUnitStatusSerializeTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return _BaseUnitStatusSerializeTD(
            natural_key=self.natural_key,
            base_unit=RelationshipNaturalKey(
                related_model_table="base_units",
                related_model_key=self.base_unit.natural_key,
            ),
            timestamp=DtIsoStr(self.timestamp.isoformat()),
            current_uptime=self.current_uptime,
            total_uptime=self.total_uptime,
            error_code=self.error_code,
            error_message=self.error_message,
            first_used=DtIsoStr(self.first_used.isoformat()),
            in_use=self.in_use,
            sharing=self.sharing,
            uploaded_to_influx=self.uploaded_to_influx,
        )

    @classmethod
    def deserialize(cls, data: _BaseUnitStatusSerializeTD, session: Session) -> Self|None:
        """Deserialize a dictionary into an instance of this model
        """
        assert isinstance(data["base_unit"], RelationshipNaturalKey), f"Expected 'base_unit' to be a RelationshipNaturalKey, got {data['base_unit']}"
        base_unit = BaseUnit.get_by_natural_key(session, data["base_unit"].related_model_key)
        if base_unit is None:
            return None
        return cls(
            base_unit_id=base_unit.id,
            timestamp=timezone.ensure_aware(datetime.datetime.fromisoformat(data["timestamp"])),
            current_uptime=data["current_uptime"],
            total_uptime=data["total_uptime"],
            error_code=data["error_code"],
            error_message=data["error_message"],
            first_used=timezone.ensure_aware(datetime.datetime.fromisoformat(data["first_used"])),
            in_use=data["in_use"],
            sharing=data["sharing"],
            uploaded_to_influx=data["uploaded_to_influx"],
        )

    @classmethod
    def get_by_natural_key(cls, session: Session, key: BaseUnitStatusNaturalKey) -> Self|None:
        """Get the instance of this model from the given natural key

        If no instance exists, ``None`` is returned.
        """
        base_unit_hostname, pk = key
        base_unit = BaseUnit.get_by_natural_key(session, base_unit_hostname)
        if base_unit is None:
            return None
        return session.query(cls).filter_by(
            base_unit_id=base_unit.id, id=pk
        ).one_or_none()

    @property
    def current_uptime_timedelta(self) -> datetime.timedelta:
        """Get the current uptime as a timedelta."""
        return datetime.timedelta(seconds=self.current_uptime)

    @classmethod
    def from_data(cls, base_unit: int|BaseUnit, data: BaseUnitStatusData, now: datetime.datetime|None = None) -> Self:
        """Create an instance of this model from a :class:`.types.BaseUnitStatus` instance
        """
        if isinstance(base_unit, BaseUnit):
            base_unit = base_unit.id
        if now is None:
            now = timezone.utcnow()
        else:
            timezone.ensure_aware(now)
        return cls(
            base_unit_id=base_unit,
            timestamp=now,
            current_uptime=int(data.current_uptime.total_seconds()),
            total_uptime=int(data.total_uptime.total_seconds()),
            error_code=data.error_code,
            error_message=data.error_message,
            first_used=timezone.ensure_aware(data.first_used),
            in_use=data.in_use,
            sharing=data.sharing,
        )

    def to_data(self) -> BaseUnitStatusData:
        """Convert this instance to a :class:`.types.BaseUnitStatus` instance
        """
        return BaseUnitStatusData(
            base_unit=BaseUnitInfo(
                ip_address=self.base_unit.ip_address,
                hostname=self.base_unit.hostname,
                room_name=self.base_unit.room_name,
            ),
            current_uptime=self.current_uptime_timedelta,
            total_uptime=datetime.timedelta(seconds=self.total_uptime),
            error_code=self.error_code,
            error_message=self.error_message,
            first_used=self.first_used,
            in_use=self.in_use,
            sharing=self.sharing,
        )

    def __repr__(self) -> str:
        return f"<BaseUnitStatus(id={self.id}, base_unit={self.base_unit}, timestamp={self.timestamp})>"

    def __str__(self) -> str:
        return f"BaseUnitStatus for {self.base_unit} at {self.timestamp}"




class BaseUnitUsageStatus(Base[BaseUnitUsageStatusNaturalKey, _BaseUnitUsageStatusSerializeTD]):
    """ORM model for the usage status of a ClickShare BaseUnit at a given point in time
    """
    __tablename__ = "base_unit_usage_statuses"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(index=True, nullable=False)
    base_unit_id: Mapped[int] = mapped_column(ForeignKey("base_units.id"), nullable=False)
    in_use: Mapped[bool] = mapped_column(nullable=False)
    sharing: Mapped[bool] = mapped_column(nullable=False)
    uploaded_to_influx: Mapped[bool] = mapped_column(nullable=False, default=False)

    base_unit: Mapped[BaseUnit] = relationship(BaseUnit, back_populates="usage_statuses")

    @property
    def natural_key(self) -> BaseUnitUsageStatusNaturalKey:
        """Get the natural key for this instance
        """
        return (
            self.base_unit.natural_key,
            self.id,
        )

    @classmethod
    def get_by_natural_key(cls, session: Session, key: BaseUnitUsageStatusNaturalKey) -> Self | None:
        """Get the instance of this model from the given natural key

        If no instance exists, ``None`` is returned.
        """
        base_unit_hostname, pk = key
        base_unit = BaseUnit.get_by_natural_key(session, base_unit_hostname)
        if base_unit is None:
            return None
        return session.query(cls).filter_by(
            base_unit_id=base_unit.id, id=pk
        ).one_or_none()

    def serialize(self) -> _BaseUnitUsageStatusSerializeTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return _BaseUnitUsageStatusSerializeTD(
            natural_key=self.natural_key,
            base_unit=RelationshipNaturalKey(
                related_model_table="base_units",
                related_model_key=self.base_unit.natural_key,
            ),
            timestamp=DtIsoStr(self.timestamp.isoformat()),
            in_use=self.in_use,
            sharing=self.sharing,
            uploaded_to_influx=self.uploaded_to_influx,
        )

    @classmethod
    def deserialize(cls, data: _BaseUnitUsageStatusSerializeTD, session: Session) -> Self | None:
        """Deserialize a dictionary into an instance of this model

        If no instance can be created (e.g. due to missing related objects), ``None`` is returned.
        """
        assert isinstance(data["base_unit"], RelationshipNaturalKey), f"Expected 'base_unit' to be a RelationshipNaturalKey, got {data['base_unit']}"
        base_unit = BaseUnit.get_by_natural_key(session, data["base_unit"].related_model_key)
        if base_unit is None:
            return None
        return cls(
            base_unit_id=base_unit.id,
            timestamp=timezone.ensure_aware(datetime.datetime.fromisoformat(data["timestamp"])),
            in_use=data["in_use"],
            sharing=data["sharing"],
            uploaded_to_influx=data["uploaded_to_influx"],
        )

    @classmethod
    def from_data(cls, base_unit: int|BaseUnit, data: BaseUnitStatusData|BaseUnitUsageStatusData, now: datetime.datetime|None = None) -> Self:
        """Create an instance of this model from a :class:`.types.BaseUnitStatus` instance
        """
        if isinstance(base_unit, BaseUnit):
            base_unit = base_unit.id
        if now is None:
            now = timezone.utcnow()
        else:
            timezone.ensure_aware(now)
        return cls(
            base_unit_id=base_unit,
            timestamp=now,
            in_use=data.in_use,
            sharing=data.sharing,
        )

    def to_data(self) -> BaseUnitUsageStatusData:
        """Convert this instance to a :class:`.types.BaseUnitUsageStatus` instance
        """
        return BaseUnitUsageStatusData(
            base_unit=BaseUnitInfo(
                ip_address=self.base_unit.ip_address,
                hostname=self.base_unit.hostname,
                room_name=self.base_unit.room_name,
            ),
            in_use=self.in_use,
            sharing=self.sharing,
        )

    @classmethod
    def _create_from_base_unit_status(cls, base_unit_status: BaseUnitStatus) -> Self:
        """Temporary method to create a BaseUnitUsageStatus from a BaseUnitStatus, for migration purposes."""
        return cls(
            base_unit_id=base_unit_status.base_unit_id,
            timestamp=base_unit_status.timestamp,
            in_use=base_unit_status.in_use,
            sharing=base_unit_status.sharing,
        )

    def __repr__(self) -> str:
        return f"<BaseUnitUsageStatus(id={self.id}, base_unit={self.base_unit}, timestamp={self.timestamp}, in_use={self.in_use}, sharing={self.sharing})>"

    def __str__(self) -> str:
        return f"BaseUnitUsageStatus for {self.base_unit} at {self.timestamp}"



class SensorReading(Base[SensorReadingNaturalKey, _SensorReadingSerializeTD]):
    """ORM model for a sensor reading."""
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    base_unit_id: Mapped[int] = mapped_column(ForeignKey("base_units.id"), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(index=True, nullable=False)
    sensor_type: Mapped[SensorType] = mapped_column(index=True, nullable=False)
    value: Mapped[float] = mapped_column(nullable=False)
    uploaded_to_influx: Mapped[bool] = mapped_column(nullable=False, default=False)

    base_unit: Mapped[BaseUnit] = relationship(BaseUnit, back_populates="sensor_readings")

    # Add a unique constraint to prevent duplicate readings for the same base unit, timestamp, and sensor type
    __table_args__ = (
        UniqueConstraint("base_unit_id", "timestamp", "sensor_type", name="uix_base_unit_timestamp_sensor"),
    )

    @property
    def natural_key(self) -> SensorReadingNaturalKey:
        """Get the natural key for this instance
        """
        return (
            self.base_unit.natural_key,
            self.id,
        )

    def serialize(self) -> _SensorReadingSerializeTD:
        """Serialize this instance to a dictionary for JSON serialization
        """
        return {
            "natural_key": self.natural_key,
            "base_unit": RelationshipNaturalKey(
                related_model_table="base_units",
                related_model_key=self.base_unit.natural_key,
            ),
            "timestamp": DtIsoStr(self.timestamp.isoformat()),
            "sensor_type": self.sensor_type,
            "value": self.value,
            "uploaded_to_influx": self.uploaded_to_influx,
        }

    @classmethod
    def deserialize(cls, data: _SensorReadingSerializeTD, session: Session) -> SensorReading|None:
        """Deserialize a dictionary into an instance of this model

        If no instance can be created (e.g. due to missing related objects), ``None`` is returned.
        """
        base_unit = BaseUnit.get_by_natural_key(session, data["base_unit"].related_model_key)
        if base_unit is None:
            return None
        return cls(
            base_unit_id=base_unit.id,
            timestamp=timezone.ensure_aware(datetime.datetime.fromisoformat(data["timestamp"])),
            sensor_type=data["sensor_type"],
            value=data["value"],
            uploaded_to_influx=data["uploaded_to_influx"],
        )

    @classmethod
    def get_by_natural_key(
        cls,
        session: Session,
        key: SensorReadingNaturalKey,
    ) -> SensorReading|None:
        """Get an instance of this model from the given natural key

        If no instance exists, ``None`` is returned.
        """
        base_unit_hostname, pk = key
        base_unit = BaseUnit.get_by_natural_key(session, base_unit_hostname)
        if base_unit is None:
            return None
        obj = session.query(SensorReading).filter_by(
            base_unit_id=base_unit.id, id=pk
        ).one_or_none()
        if obj is not None:
            assert obj.id == pk, f"Expected to find SensorReading with ID {pk}, but found {obj.id}"
        return obj

    @classmethod
    def filter_by_sensor_type(cls, session: Session, sensor_type: SensorType) -> Query[SensorReading]:
        """Get a query for SensorReadings of a specific sensor type
        """
        return session.query(SensorReading).filter_by(sensor_type=sensor_type)

    @classmethod
    def from_data(
        cls,
        base_unit: BaseUnit|BaseUnitInfo|int,
        reading: SensorReadingData[SensorType],
        session: Session
    ) -> Self:
        """Create an instance of this model from a :class:`.types.SensorReading` instance
        """
        if isinstance(base_unit, BaseUnitInfo):
            base_unit, _ = BaseUnit.get_or_create(base_unit, session)
        elif isinstance(base_unit, BaseUnit):
            base_unit = base_unit.id
        return cls(
            base_unit_id=base_unit,
            timestamp=ensure_aware(reading.timestamp),
            sensor_type=reading.sensor,
            value=reading.value,
        )

    def to_data(self) -> SensorReadingData[SensorType]:
        """Convert this instance to a :class:`.types.SensorReading` instance
        """
        assert self.timestamp.tzinfo is not None, "SensorReading timestamp must be timezone-aware"
        return SensorReadingData(
            timestamp=self.timestamp,
            sensor=self.sensor_type,
            value=self.value,
        )

    def __repr__(self) -> str:
        return f"<SensorReading(id={self.id}, base_unit={self.base_unit}, timestamp={self.timestamp}, sensor_type={self.sensor_type}, value={self.value})>"

    def __str__(self) -> str:
        return f"SensorReading for {self.base_unit} at {self.timestamp}: {self.sensor_type}={self.value}"



type ModelInstance = Union[
    BaseUnit,
    BaseUnitOnlineStatus,
    BaseUnitStatus,
    BaseUnitUsageStatus,
    SensorReading,
    BaseUnitIdentity,
    PowerManagementSettings,
    PowerManagementStatus,
]
type ModelClass = type[ModelInstance]
type ModelTableName = Literal[
    "base_units",
    "base_unit_online_statuses",
    "base_unit_statuses",
    "base_unit_usage_statuses",
    "sensor_readings",
    "base_unit_identities",
    "power_management_settings",
    "power_management_status"
]
MODEL_CLASSES = (
    BaseUnit,
    BaseUnitOnlineStatus,
    BaseUnitIdentity,
    PowerManagementSettings,
    PowerManagementStatus,
    BaseUnitStatus,
    BaseUnitUsageStatus,
    SensorReading,
)
