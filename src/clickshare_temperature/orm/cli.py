from __future__ import annotations
from typing import Callable, TYPE_CHECKING
import asyncio
import warnings
from pathlib import Path
import datetime
from dataclasses import dataclass

import click
import click_extra
# from yarl import URL
from aiohttp import ClientSession, ClientError
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

from ..types import (
    AuthInfo,
    BaseUnitInfo,
    PowerModeStatus,
    AioHttpRequestOptions,
)
from ..baseunit_api import (
    create_session as create_aiohttp_session,
    get_baseunit_info,
    get_baseunit_status,
    get_baseunit_identity,
    get_power_management_info,
)

from .engine import (
    EngineBuilder,
    get_session as get_db_session,
    set_engine_uri,
    init_db,
)
from .models import (
    BaseUnit,
    BaseUnitIdentity,
    PowerManagementSettings,
    PowerManagementStatus,
    BaseUnitStatus,
    BaseUnitUsageStatus,
    SensorReading,
)
from .serialization import serialize_database, deserialize_database
from ..temperature_history import TemperatureHistory
from ..utils import click_secho, get_baseunit_from_filename, is_valid_ip_or_hostname
from ..click_extra_params import get_extra_params, CLIRootContext
from .. import timezone


class CommunicationError(UserWarning):
    """Warning raised when there is a communication error with a BaseUnit
    """


COMMUNICATION_ERROR_EXIT_CODE: int = 2
"""Exit code to use when a :class:`CommunicationError` is raised and causes the program to exit"""


def catch_communication_errors[**P, ResultT](
    func: Callable[P, ResultT],
    *args: P.args,
    **kwargs: P.kwargs
) -> tuple[ResultT, bool]:
    """Helper function to catch :class:`CommunicationError`

    Arguments:
        func: The function to call
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        A tuple of:

        - **result**: The result of the function call
        - **had_error**: A boolean indicating whether a CommunicationError was caught
    """
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", CommunicationError)
        result = func(*args, **kwargs)
        had_error = False
        for warning in w:
            if issubclass(warning.category, CommunicationError):
                click_secho(str(warning.message), fg="red")
                had_error = True
        return result, had_error


def raise_communication_errors[**P, ResultT](
    func: Callable[P, ResultT],
    *args: P.args,
    **kwargs: P.kwargs
) -> ResultT:
    """Helper function to catch :class:`CommunicationError` and raise a SystemExit
    if any are found

    Arguments:
        func: The function to call
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns the result of the function call if no CommunicationErrors were caught

    Raises:
        SystemExit: If any CommunicationErrors were caught, with an exit code of
            :data:`COMMUNICATION_ERROR_EXIT_CODE`
    """
    result, had_error = catch_communication_errors(func, *args, **kwargs)
    if had_error:
        raise SystemExit(COMMUNICATION_ERROR_EXIT_CODE)
    return result


auth_option_group = click_extra.option_group(
    "Authentication Options",
    click_extra.option(
        "--username", "-u",
        envvar="CLICKSHARE_BASEUNIT_USERNAME",
        type=str,
        required=True,
        prompt=True,
        help="Username for BaseUnit API authentication.",
    ),
    click_extra.option(
        "--password", "-p",
        envvar="CLICKSHARE_BASEUNIT_PASSWORD",
        type=str,
        required=True,
        prompt=True,
        hide_input=True,
        help="Password for BaseUnit API authentication.",
    ),
)

db_option_group = click_extra.option_group(
    "Database Options",
    click_extra.option(
        "-d", "--db-url",
        envvar="CLICKSHARE_DB_URL",
        type=str,
        help="Database URL for SQLAlchemy (e.g. 'sqlite:///clickshare_data.db').",
    ),
)


@dataclass
class CLIDbContext(CLIRootContext):
    """Context object for the ORM CLI

    This extends :class:`CLIRootContext`
    """
    db_url: str|None
    """Database URL for SQLAlchemy"""



@click_extra.group(name="orm", params=get_extra_params())
@db_option_group
@click_extra.pass_context
def cli(ctx: click.Context, db_url: str|None) -> None:
    """CLI for ClickShare ORM commands"""
    root_ctx: CLIRootContext = ctx.obj
    ctx.obj = CLIDbContext(
        auth_info=root_ctx.auth_info,
        aiohttp_request_options=root_ctx.aiohttp_request_options,
        aiohttp_session_options=root_ctx.aiohttp_session_options,
        db_url=db_url,
    )
    if db_url is not None:
        set_engine_uri(db_url)


@cli.command(name="from-files")
@click_extra.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click_extra.pass_obj
def backfill_from_files(ctx_obj: CLIDbContext, directory: Path) -> None:
    """Backfill sensor readings from all files in a directory to the database."""
    with get_db_session() as session:
        for filepath in directory.glob("*.txt"):
            click_secho(f"Processing file {filepath}...", fg="blue")
            base_unit_info = get_baseunit_from_filename(filepath)
            base_unit = session.query(BaseUnit).filter_by(
                hostname=base_unit_info.hostname
            ).one_or_none()
            if base_unit is None:
                base_unit = BaseUnit(
                    hostname=base_unit_info.hostname,
                    room_name=base_unit_info.room_name,
                    ip_address=base_unit_info.ip_address,
                )
                session.add(base_unit)

                click_secho(f"Created new BaseUnit '{base_unit.hostname}' in the database", fg="green")
        session.commit()

        for filepath in directory.glob("*.txt"):
            click_secho(f"Processing file {filepath}...", fg="blue")
            base_unit_info = get_baseunit_from_filename(filepath)
            base_unit = session.query(BaseUnit).filter_by(
                hostname=base_unit_info.hostname
            ).one()
            temperature_history = TemperatureHistory.deserialize_str(base_unit_info, filepath.read_text())
            num_added, num_skipped = base_unit.add_sensor_readings(temperature_history.readings, session)
            click_secho(
                f"Finished processing file {filepath}. Added {num_added} readings, skipped {num_skipped} readings.",
                fg="blue",
            )
        session.commit()




@cli.command(name="add-baseunit")
@click_extra.argument("base_unit_ips", nargs=-1)
@click_extra.pass_obj
def add_baseunit(ctx_obj: CLIDbContext, base_unit_ips: tuple[str, ...]) -> None:
    """Add a BaseUnit to the database without fetching sensor readings."""
    session_options = ctx_obj.aiohttp_session_options
    request_options = ctx_obj.aiohttp_request_options

    async def get_all_baseunit_infos() -> list[BaseUnitInfo]:
        infos: list[BaseUnitInfo] = []
        async with create_aiohttp_session(**session_options) as aiohttp_session:
            for base_unit_ip in base_unit_ips:
                try:
                    info = await get_baseunit_info(
                        base_unit_ip,
                        auth_info=ctx_obj.auth_info,
                        session=aiohttp_session,
                        **request_options,
                    )
                    infos.append(info)
                except (asyncio.TimeoutError, ClientError) as e:
                    warnings.warn(
                        f"Connection to BaseUnit at IP '{base_unit_ip}' failed: {e}, skipping",
                        CommunicationError,
                    )
        return infos
    exit_code = 0
    base_unit_infos, had_error = catch_communication_errors(
        asyncio.run,
        get_all_baseunit_infos(),
    )
    if had_error:
        exit_code = COMMUNICATION_ERROR_EXIT_CODE

    with get_db_session() as session:
        for baseunit_info in base_unit_infos:
            base_unit = session.query(BaseUnit).filter_by(
                hostname=baseunit_info.hostname
            ).one_or_none()
            if base_unit is not None:
                if base_unit.room_name != baseunit_info.room_name or base_unit.ip_address != baseunit_info.ip_address:
                    confirm_msg = '\n'.join([
                        f"BaseUnit with hostname '{base_unit.hostname}' already exists but has different information:",
                        f"Existing room name: '{base_unit.room_name}', IP address: '{base_unit.ip_address}'",
                        f"New room name: '{baseunit_info.room_name}', IP address: '{baseunit_info.ip_address}'",
                        "Do you want to update the existing BaseUnit with the new information?",
                    ])
                    if click.confirm(confirm_msg, default=True):
                        base_unit.room_name = baseunit_info.room_name
                        base_unit.ip_address = baseunit_info.ip_address
                        session.commit()
                        click_secho(
                            f"Updated BaseUnit '{base_unit.hostname}' in the database",
                            fg="green",
                        )
                else:
                    click_secho(
                        f"BaseUnit '{base_unit.hostname}' already exists, skipping",
                        fg="yellow",
                    )
            else:
                base_unit = BaseUnit(
                    hostname=baseunit_info.hostname,
                    room_name=baseunit_info.room_name,
                    ip_address=baseunit_info.ip_address,
                )
                session.add(base_unit)
                session.commit()
                click_secho(
                    f"Created new BaseUnit '{base_unit.hostname}'",
                    fg="green",
                )
    if exit_code != 0:
        raise SystemExit(exit_code)



@cli.command(name="list-baseunits")
@click_extra.pass_obj
def list_baseunits(ctx_obj: CLIDbContext) -> None:
    """List all BaseUnits in the database."""
    with get_db_session() as session:
        base_units = session.query(BaseUnit).all()
        if len(base_units) == 0:
            click_secho("No BaseUnits found.", fg="yellow")
            return
        click_secho(f"Found {len(base_units)} BaseUnits:", fg="green")
        for base_unit in base_units:
            click.echo(f"- {base_unit.room_name} ({base_unit.hostname}, IP: {base_unit.ip_address})")


@cli.command(name="update-baseunit-info")
@click_extra.pass_obj
def update_baseunit_info(ctx_obj: CLIDbContext) -> None:
    session_options = ctx_obj.aiohttp_session_options
    request_options = ctx_obj.aiohttp_request_options

    async def update_baseunit_info(base_unit: BaseUnit, session: Session, aiohttp_session: ClientSession) -> bool:
        if not is_valid_ip_or_hostname(base_unit.ip_address):
            click_secho(
                f"BaseUnit '{base_unit.hostname}' has invalid IP address '{base_unit.ip_address}', skipping",
                fg="red",
            )
            return False
        try:
            info = await get_baseunit_info(
                base_unit.ip_address,
                auth_info=ctx_obj.auth_info,
                session=aiohttp_session,
                **request_options,
            )
            changed = False
            if base_unit.room_name != info.room_name:
                base_unit.room_name = info.room_name
                changed = True
            if base_unit.ip_address != info.ip_address:
                base_unit.ip_address = info.ip_address
                changed = True
            identity_info = await get_baseunit_identity(
                base_unit.ip_address,
                auth_info=ctx_obj.auth_info,
                session=aiohttp_session,
                **request_options,
            )
            identity_model = base_unit.identity
            if identity_model is None:
                identity_model = BaseUnitIdentity.from_data(base_unit, identity_info, session)
                session.add(identity_model)
                changed = True
            else:
                if identity_model.to_data() != identity_info:
                    raise ValueError(f"Identity mismatch for BaseUnit '{base_unit.hostname}'")
            click_secho(
                f"Updated information for BaseUnit '{base_unit.hostname}'",
                fg="green",
            )
        except (asyncio.TimeoutError, ClientError) as e:
            warnings.warn(
                f"Connection to BaseUnit at IP '{base_unit.ip_address}' failed: {e}, skipping",
                CommunicationError,
            )
        return changed

    async def update_all_baseunit_infos() -> None:
        async with create_aiohttp_session(**session_options) as aiohttp_session:
            with get_db_session() as session:
                base_units = session.query(BaseUnit).all()
                if len(base_units) == 0:
                    click_secho("No BaseUnits found.", fg="yellow")
                    return
                click_secho(
                    f"Updating information for {len(base_units)} BaseUnits...",
                    fg="green",
                )
                update_coros = [
                    update_baseunit_info(base_unit, session, aiohttp_session)
                    for base_unit in base_units
                ]
                results = await asyncio.gather(*update_coros)
                num_updated = sum(1 for r in results if r)
                click_secho(
                    f"Updated information for {num_updated} BaseUnits.",
                    fg="green",
                )
                session.commit()

    raise_communication_errors(asyncio.run, update_all_baseunit_infos())


@cli.command(name="update-power-management")
@click_extra.pass_obj
def update_power_management_info(ctx_obj: CLIDbContext) -> None:
    """Fetch the power management settings and statuses for all BaseUnits in the database and update the database."""
    session_options = ctx_obj.aiohttp_session_options
    request_options = ctx_obj.aiohttp_request_options
    now = timezone.utcnow()


    async def update_power_management_info(base_unit: BaseUnit, session: Session, aiohttp_session: ClientSession) -> bool:
        if not is_valid_ip_or_hostname(base_unit.ip_address):
            click_secho(
                f"BaseUnit '{base_unit.hostname}' has invalid IP address '{base_unit.ip_address}', skipping",
                fg="red",
            )
            return False
        try:
            power_info = await get_power_management_info(
                base_unit.ip_address,
                auth_info=ctx_obj.auth_info,
                session=aiohttp_session,
                **request_options,
            )
            settings_model = base_unit.power_management_settings
            if settings_model is None:
                settings_model = PowerManagementSettings.from_data(base_unit, power_info, session)
                session.add(settings_model)
            else:
                settings_model.update_from_data(power_info)
            status_model = PowerManagementStatus.from_data(base_unit, power_info, now)
            session.add(status_model)
            click_secho(
                f"Updated power management information for BaseUnit '{base_unit.hostname}'",
                fg="green",
            )
            return True
        except (asyncio.TimeoutError, ClientError) as e:
            warnings.warn(
                f"Connection to BaseUnit at IP '{base_unit.ip_address}' failed: {e}, skipping",
                CommunicationError,
            )
            return False

    async def update_all_power_management_infos() -> None:
        async with create_aiohttp_session(**session_options) as aiohttp_session:
            with get_db_session() as session:
                base_units = session.query(BaseUnit).all()
                if len(base_units) == 0:
                    click_secho("No BaseUnits found.", fg="yellow")
                    return
                click_secho(
                    f"Updating power management information for {len(base_units)} BaseUnits...",
                    fg="green",
                )
                update_coros = [
                    update_power_management_info(base_unit, session, aiohttp_session)
                    for base_unit in base_units
                ]
                results = await asyncio.gather(*update_coros)
                num_updated = sum(1 for r in results if r)
                click_secho(
                    f"Updated power management information for {num_updated} BaseUnits.",
                    fg="green",
                )
                session.commit()

    raise_communication_errors(asyncio.run, update_all_power_management_infos())




@cli.command(name="update-statuses")
# @click.option(
#     "--upload-influx",
#     is_flag=True,
#     help="Whether to upload statuses to InfluxDB after fetching them from the BaseUnits.",
# )
@click_extra.option(
    "--usage-only",
    is_flag=True,
    help="Whether to fetch only usage statuses instead of full statuses.",
)
# @click.option(
#     "--backfill-readings",
#     is_flag=True,
# )
@click_extra.pass_obj
def update_statuses(ctx_obj: CLIDbContext, usage_only: bool) -> None:
    """Fetch the status for all BaseUnits in the database and print it to the console."""
    if db_url is not None:
        set_engine_uri(db_url)
    # if upload_influx:
    #     from ..influxdb import upload_baseunit_status
    session_options = ctx_obj.aiohttp_session_options
    request_options = ctx_obj.aiohttp_request_options

    model_cls = BaseUnitUsageStatus if usage_only else BaseUnitStatus

    async def update_all_statuses() -> None:
        async with create_aiohttp_session(**session_options) as aiohttp_session:
            with get_db_session() as session:
                base_units = session.query(BaseUnit).all()
                if len(base_units) == 0:
                    click_secho("No BaseUnits found.", fg="yellow")
                    return
                click_secho(f"Updating statuses for {len(base_units)} BaseUnits...", fg="green")
                # update_coros = [
                #     update_basunit_status(base_unit, auth_info, usage_only, session, aiohttp_session, request_options)
                #     for base_unit in base_units
                # ]
                update_coros = [
                    update_baseunit_status(
                        base_unit, ctx_obj.auth_info, model_cls, session,
                        aiohttp_session, request_options
                    )
                    for base_unit in base_units
                ]
                statuses = await asyncio.gather(*update_coros)
                num_updated = sum(1 for s in statuses if s is not None)
                click_secho(f"Updated statuses for {num_updated} BaseUnits.", fg="green")
                session.commit()

    raise_communication_errors(asyncio.run, update_all_statuses())



async def update_baseunit_status[T: BaseUnitStatus|BaseUnitUsageStatus](
    base_unit: BaseUnit,
    auth_info: AuthInfo,
    model_cls: type[T],
    session: Session,
    aiohttp_session: ClientSession,
    request_options: AioHttpRequestOptions
) -> BaseUnitStatus|BaseUnitUsageStatus|None:
    if not is_valid_ip_or_hostname(base_unit.ip_address):
        click_secho(
            f"BaseUnit '{base_unit.hostname}' has invalid IP address '{base_unit.ip_address}', skipping",
            fg="red",
        )
        return None
    try:
        status_data = await get_baseunit_status(
            base_unit.ip_address,
            auth_info=auth_info,
            session=aiohttp_session,
            **request_options
        )
        status = model_cls.from_data(base_unit, status_data)
        session.add(status)
        return status
    except (asyncio.TimeoutError, ClientError) as e:
        warnings.warn(
            f"Connection to BaseUnit at IP '{base_unit.ip_address}' failed: {e}, skipping",
            CommunicationError,
        )
        return None


@cli.command()
@click_extra.option(
    "--baseunit-ip-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to a text file containing a list of BaseUnit IP addresses, one per line.",
)
@click_extra.option(
    "--usage-only",
    is_flag=True,
    help="Whether to fetch only usage statuses instead of full statuses.",
)
@click_extra.pass_obj
def fetch_readings_bulk(
    ctx_obj: CLIDbContext,
    baseunit_ip_file: Path|None,
    usage_only: bool,
) -> None:
    """Fetch sensor readings for multiple BaseUnits and add them to the database."""
    session_options = ctx_obj.aiohttp_session_options
    request_options = ctx_obj.aiohttp_request_options
    baseunit_ips: list[str]|None = None
    if baseunit_ip_file is not None:
        baseunit_ips = []
        with baseunit_ip_file.open() as f:
            for line in f:
                if line.startswith("#") or line.startswith("//"):
                    continue
                base_unit_ip = line.strip()
                if base_unit_ip:
                    baseunit_ips.append(base_unit_ip)


    model_cls = BaseUnitUsageStatus if usage_only else BaseUnitStatus

    async def fetch_all() -> None:
        async with create_aiohttp_session(**session_options) as aiohttp_session:
            with get_db_session() as orm_session:
                base_unit_query = orm_session.query(BaseUnit)
                if baseunit_ips is not None:
                    base_unit_query = base_unit_query.filter(BaseUnit.ip_address.in_(baseunit_ips))
                status_coros = [
                    update_baseunit_status(
                        base_unit, ctx_obj.auth_info, model_cls, orm_session,
                        aiohttp_session, request_options,
                    )
                    for base_unit in base_unit_query.all()
                ]
                await asyncio.gather(*status_coros)
                orm_session.commit()  # Commit status updates before fetching sensor readings

                async def _do_fetch(base_unit: BaseUnit) -> None:
                    click_secho(f"Processing BaseUnit '{base_unit.hostname}' (ID: {base_unit.id})", fg="blue")
                    if not is_valid_ip_or_hostname(base_unit.ip_address):
                        click_secho(
                            f"BaseUnit '{base_unit.hostname}' has invalid IP address '{base_unit.ip_address}', skipping",
                            fg="red",
                        )
                        return None
                    try:
                        await base_unit.add_sensor_readings_from_api(
                            auth_info=ctx_obj.auth_info,
                            session=orm_session,
                            aiohttp_session=aiohttp_session,
                            request_options=request_options,
                        )
                        click_secho(
                            f"Finished processing BaseUnit '{base_unit.hostname}' (ID: {base_unit.id})",
                            fg="blue",
                        )
                    except (asyncio.TimeoutError, ClientError) as e:
                        warnings.warn(
                            f"Connection to BaseUnit '{base_unit.hostname}' failed: {e}, skipping",
                            CommunicationError,
                        )

                fetch_coros = set()
                for base_unit in base_unit_query.all():
                    if base_unit is None:
                        continue
                    assert base_unit.id is not None, "BaseUnit ID should not be None after commit"
                    fetch_coros.add(_do_fetch(base_unit))
                await asyncio.gather(*fetch_coros)

                orm_session.commit()

    raise_communication_errors(asyncio.run, fetch_all())



@cli.command(name="backfill-influx")
@click_extra.pass_obj
def backfill_influx(ctx_obj: CLIDbContext) -> None:
    """Backfill all existing statuses in the database to InfluxDB."""
    from ..influxdb import upload_baseunit_status, backfill_readings, upload_power_management_statuses

    def backfill_base_unit(session: Session, base_unit: BaseUnit) -> None:
        sensor_query = session.query(SensorReading).filter_by(
            base_unit_id=base_unit.id, uploaded_to_influx=False
        )
        if sensor_query.count() == 0:
            return
        click_secho(
            f"Backfilling {sensor_query.count()} sensor readings for BaseUnit '{base_unit.hostname}'...",
            fg="blue",
        )
        temperature_history = base_unit.to_temperature_history_data(session, sensor_query=sensor_query)
        num_backfilled = backfill_readings(
            temperature_history.base_unit,
            temperature_history,
            ignore_last_readings_info=True,
        )
        click_secho(
            f"Backfill complete for BaseUnit '{base_unit.hostname}'. Backfilled {num_backfilled} readings.",
            fg="green",
        )
        for reading in sensor_query.all():
            reading.uploaded_to_influx = True
        session.commit()

    def backfill_statuses[T: BaseUnitStatus | BaseUnitUsageStatus](session: Session, model_cls: type[T]) -> None:
        statuses = session.query(model_cls).filter_by(uploaded_to_influx=False)
        if statuses.count() == 0:
            return
        click_secho(
            f"Backfilling and uploading {statuses.count()} {model_cls.__name__} entries...",
            fg="blue",
        )
        upload_baseunit_status([(s.to_data(), s.timestamp) for s in statuses])
        for status in statuses:
            status.uploaded_to_influx = True
        session.commit()
        click_secho(
            f"Backfill complete for {model_cls.__name__}",
            fg="green",
        )

    def backfill_power_statuses(session: Session) -> None:
        power_statuses = session.query(PowerManagementStatus).filter_by(uploaded_to_influx=False)
        if power_statuses.count() == 0:
            return
        click_secho(
            f"Backfilling and uploading {power_statuses.count()} PowerManagementStatus entries...",
            fg="blue",
        )
        power_status_args: list[tuple[BaseUnitInfo, PowerModeStatus, datetime.datetime]] = [
            (s.base_unit.to_data(), s.power_mode_status, s.timestamp)
            for s in power_statuses
        ]
        upload_power_management_statuses(power_status_args)
        for power_status in power_statuses:
            power_status.uploaded_to_influx = True
        session.commit()
        click_secho(
            "Backfill complete for PowerManagementStatus",
            fg="green",
        )

    with get_db_session() as session:
        for base_unit in session.query(BaseUnit).all():
            backfill_base_unit(session, base_unit)

        backfill_statuses(session, BaseUnitUsageStatus)
        backfill_statuses(session, BaseUnitStatus)
        backfill_power_statuses(session)




@cli.command()
def show_db_schema() -> None:
    def _create_tmp_engine() -> Engine:
        return sa_create_engine("sqlite:///:memory:", echo=True)

    EngineBuilder.set_builder(_create_tmp_engine)
    # This will create the tables in the in-memory SQLite database
    # and print the SQL statements to the console
    init_db()


@cli.command()
@click_extra.pass_obj
def init_database(ctx_obj: CLIDbContext) -> None:
    """Initialize the database by creating all tables."""
    init_db()


@cli.command()
@click_extra.argument(
    'output_file',
    type=click.Path(dir_okay=False, path_type=Path),
)
@click_extra.option(
    "--pretty",
    is_flag=True,
    help="Whether to pretty-print the JSON output with indentation.",
)
@click_extra.pass_obj
def dump_database(ctx_obj: CLIDbContext, output_file: Path, pretty: bool) -> None:
    """Dump the entire database to a JSON file."""
    with get_db_session() as session:
        serialize_database(session, filename=output_file, indent=2 if pretty else None)



@cli.command()
@click_extra.argument(
    'input_file',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click_extra.option(
    "--limit-to-models",
    type=str,
    multiple=True,
    help="Limit deserialization to specific models by name.",
)
@click_extra.pass_obj
def load_database(ctx_obj: CLIDbContext, input_file: Path, limit_to_models: list[str]) -> None:
    """Load the entire database from a JSON file."""
    with get_db_session() as session:
        deserialize_database(
            session,
            input_file,
            limit_to_models=limit_to_models if len(limit_to_models) > 0 else None,
        )



if __name__ == "__main__":
    cli()
