from __future__ import annotations
from typing import Literal, Callable
import asyncio
from pathlib import Path
import json

from dotenv import load_dotenv
from aiohttp import ClientSession
import click
import click_extra

from clickshare_temperature.types import AuthInfo

from .baseunit_api import (
    create_session,
    get_baseunit_info,
    DEFAULT_REQUEST_OPTIONS,
    DEFAULT_SESSION_OPTIONS,
)
from .temperature_history import TemperatureHistory
from .log_archive import LogArchive
from .types import AioHttpRequestOptions, AioHttpSessionOptions
from .utils import ClickColor, click_secho, get_output_file_for_baseunit
from .click_extra_params import get_extra_params, CLIRootContext


orm_cli: None|click_extra.Group|Callable[..., None]
try:
    from .orm.cli import cli as orm_cli
except ModuleNotFoundError as exc:
    if exc.name in {"sqlalchemy", "sqlalchemy_utc"}:
        orm_cli = None
    else:
        raise

influxdb_cli: None|click.Group
try:
    from .influxdb import cli as influxdb_cli
except ImportError:
    influxdb_cli = None


load_dotenv()


type OutputFormat = Literal["str", "json", "current"]
type AppendFromFormat = Literal["str", "json"]




global_option_group = click_extra.option_group(
    "Global Options",
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

output_option_group = click_extra.option_group(
    "Output Options",
    click_extra.option(
        "--output-format", "-f",
        type=click.Choice(["str", "json", "current"], case_sensitive=False),
        default="str",
        help="Output format. Can be either 'str', 'json', or 'current'. Default is 'str'." \
        "If 'current' is specified, only the most recent reading for each sensor will be outputted.",
    ),
    click_extra.option(
        "--output-file", "-o",
        type=click.Path(dir_okay=False, path_type=Path),
        help="Path to output file. If not provided, the output will be printed to stdout.",
    ),
)

input_option_group = click_extra.option_group(
    "Input Options",
    click_extra.option(
        "--append-from", "-a",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        help="Path to a log archive file to append readings from. " \
        "If provided, the readings from the downloaded logs will be appended to the readings from this file, and the combined readings will be outputted.",
    ),
    click_extra.option(
        "--append-from-format", "-A",
        type=click.Choice(["str", "json"], case_sensitive=False),
        default="str",
        help="Format of the file provided to --append-from. Can be either 'str' or 'json'. Default is 'str'. Ignored if --append-from is not provided.",
    ),
)



@click_extra.group(
    params=get_extra_params(),
    context_settings={
        "show_default": True,
        "show_choices": True,
        "show_envvar": True,
        "align_option_groups": True,
    }
)
@global_option_group
@click_extra.pass_context
def cli(
    ctx: click.Context,
    username: str,
    password: str,
) -> None:
    """CLI for working with ClickShare BaseUnit temperature logs."""
    ctx.obj = CLIRootContext(
        auth_info=AuthInfo(
            username=username,
            password=password,
        ),
    )


@cli.command(name="parse")
@click_extra.argument(
    "input_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@output_option_group
def cli_parse(input_file: Path, output_format: OutputFormat, output_file: Path|None) -> None:
    """Parse a log archive and extract temperature readings."""
    parse(input_file, output_format, output_file)


def parse(input_file: Path, output_format: OutputFormat, output_file: Path|None) -> None:
    input_file = input_file.expanduser().resolve()
    history = TemperatureHistory.from_archive_file(input_file)
    if output_format == "json":
        output_str = json.dumps(history.serialize(), indent=2)
    elif output_format == "current":
        output_str = history.serialize_current_str()
    else:
        output_str = history.serialize_str()
    if output_file is not None:
        output_file.write_text(output_str)
    else:
        click.echo(output_str)


@cli.command(name="download")
@click_extra.argument(
    "baseunit_ip",
    type=str,
)
@input_option_group
@output_option_group
@click_extra.option(
    "--upload-influx",
    is_flag=True,
    help="If set, the historical temperature data will be uploaded to InfluxDB using the Prometheus Remote Write API after it is downloaded and parsed.",
)
@click_extra.option(
    "--raw-logs",
    is_flag=True,
    help="If set, the raw log archive will be downloaded and saved to the specified output file instead of " \
    "parsing the logs and extracting temperature readings. The output format options will be ignored. " \
    "If this flag is set, the output file option is required.",
)
@click_extra.pass_obj
def cli_download(
    ctx_obj: CLIRootContext,
    baseunit_ip: str,
    append_from: Path|None,
    append_from_format: AppendFromFormat,
    output_format: OutputFormat,
    output_file: Path|None,
    raw_logs: bool,
    upload_influx: bool,
) -> None:
    """Download logs from the BaseUnit and extract temperature readings."""
    if upload_influx and raw_logs:
        raise ValueError("Cannot use --upload-influx flag when --raw-logs flag is set, because raw logs cannot be parsed for temperature readings.")
    obj, appended = asyncio.run(download(
        baseunit_ip=baseunit_ip,
        auth_info=ctx_obj.auth_info,
        append_from=append_from,
        append_from_format=append_from_format,
        output_format=output_format,
        output_file=output_file,
        raw_logs=raw_logs,
    ))
    if upload_influx:
        from .influxdb import backfill_readings

        assert isinstance(obj, TemperatureHistory)
        base_unit = asyncio.run(get_baseunit_info(
            baseunit_ip,
            auth_info=ctx_obj.auth_info,
            **DEFAULT_REQUEST_OPTIONS,
        ))
        num_points = backfill_readings(base_unit, obj)
        if num_points > 0:
            click_secho(f"Uploaded {num_points} new points for BaseUnit {base_unit.hostname} to InfluxDB.", fg="bright_green")
        else:
            click_secho(f"No new points to upload for BaseUnit {base_unit.hostname}.", fg="blue")





@cli.command(name="download-multiple")
@click_extra.argument(
    "baseunit_ip_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    # help="Path to a text file containing a list of BaseUnit IP addresses, one per line.",
)
@input_option_group
@output_option_group
@click_extra.option(
    "--upload-influx",
    is_flag=True,
    help="If set, the historical temperature data will be uploaded to InfluxDB using the Prometheus Remote Write API after it is downloaded and parsed.",
)
@click_extra.option(
    "--raw-logs",
    is_flag=True,
    help="If set, the raw log archive will be downloaded and saved to the specified output file instead of " \
    "parsing the logs and extracting temperature readings. The output format options will be ignored. " \
    "If this flag is set, the output file option is required.",
)
@click_extra.pass_obj
def cli_download_multiple(
    ctx_obj: CLIRootContext,
    baseunit_ip_file: Path,
    append_from: Path,
    append_from_format: AppendFromFormat,
    output_format: OutputFormat,
    output_dir: Path,
    upload_influx: bool,
    raw_logs: bool,
) -> None:
    """Download logs from multiple BaseUnits and extract temperature readings."""
    if upload_influx and raw_logs:
        raise ValueError("Cannot use --upload-influx flag when --raw-logs flag is set, because raw logs cannot be parsed for temperature readings.")
    baseunit_ip_file = baseunit_ip_file.expanduser().resolve()
    output_dir_original = output_dir
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with baseunit_ip_file.open() as f:
        baseunit_ips = [line.strip() for line in f if line.strip()]

    async def run_download(baseunit_ip: str, session: ClientSession) -> None:
        click_secho(f"Processing BaseUnit {baseunit_ip}...", fg="white")
        base_unit = await get_baseunit_info(
            baseunit_ip,
            auth_info=ctx_obj.auth_info,
            session=session,
            **DEFAULT_REQUEST_OPTIONS,
        )

        append_from_file = get_output_file_for_baseunit(
            append_from, base_unit.room_name, base_unit.hostname, output_format
        )
        final_output_file = get_output_file_for_baseunit(
            output_dir, base_unit.room_name, base_unit.hostname, output_format
        )

        obj, file_written = await download(
            baseunit_ip=baseunit_ip,
            auth_info=ctx_obj.auth_info,
            append_from=append_from_file,
            append_from_format=append_from_format,
            output_format=output_format,
            output_file=final_output_file,
            raw_logs=raw_logs,
            suppress_click_echo=True,
        )
        msg = f"Finished processing BaseUnit {baseunit_ip} (base unit: {base_unit})."
        color: ClickColor|None = None
        if file_written:
            msg += f" Output file: {output_dir_original / final_output_file.name}."
            color = "bright_green"
        else:
            msg += " No changes to output file."

        if upload_influx:
            from .influxdb import backfill_readings
            assert isinstance(obj, TemperatureHistory)
            click_secho(f"Uploading historical data for BaseUnit {base_unit} to InfluxDB...", fg="yellow")
            num_points = backfill_readings(base_unit, obj)
            if num_points > 0:
                click_secho(f"Uploaded {num_points} new points for BaseUnit {base_unit.hostname} to InfluxDB.", fg="bright_green")
            else:
                click_secho(f"No new points to upload for BaseUnit {base_unit.hostname}.", fg="blue")

        click_secho(msg, fg=color)


    async def run_downloads() -> None:
        async with create_session(**DEFAULT_SESSION_OPTIONS) as session:
            tasks = [run_download(baseunit_ip, session) for baseunit_ip in baseunit_ips]
            await asyncio.gather(*tasks)

    asyncio.run(run_downloads())


async def download(
    baseunit_ip: str,
    auth_info: AuthInfo,
    append_from: Path|None,
    append_from_format: AppendFromFormat,
    output_format: OutputFormat,
    output_file: Path|None,
    session_options: AioHttpSessionOptions|None = None,
    request_options: AioHttpRequestOptions|None = None,
    raw_logs: bool = False,
    suppress_click_echo: bool = False,
) -> tuple[TemperatureHistory|LogArchive, bool]:
    if raw_logs:
        if output_file is None:
            raise ValueError("Output file must be specified when --raw-logs flag is set.")
        archive = await LogArchive.from_baseunit(
            baseunit_ip,
            auth_info=auth_info,
            session_options=session_options or DEFAULT_SESSION_OPTIONS,
            **(request_options or DEFAULT_REQUEST_OPTIONS)
        )
        if append_from is not None:
            append_from = append_from.expanduser().resolve()
            if append_from.exists():
                s = append_from.read_text()
                if append_from_format == "json":
                    append_archive = LogArchive.deserialize(json.loads(s))
                else:
                    append_archive = LogArchive.deserialize_str(s)
                archive = archive.combine_entries_with(append_archive)

        if output_file is None:
            raise ValueError("Output file must be specified when --raw-logs flag is set.")
        if output_format == "current":
            raise ValueError("Output format cannot be 'current' when --raw-logs flag is set.")
        elif output_format == "json":
            output_str = json.dumps(archive.serialize(), indent=2)
        else:
            output_str = archive.serialize_str()
        if output_file.exists() and output_file.read_text() == output_str:
            if not suppress_click_echo:
                click_secho(
                    f"Output file {output_file} already exists and has the same content, skipping write.",
                    fg="cyan",
                )
            return archive, False
        output_file.write_text(output_str)
        return archive, True
    history = await TemperatureHistory.from_baseunit(
        baseunit_ip,
        auth_info=auth_info,
        session_options=session_options or DEFAULT_SESSION_OPTIONS,
        **(request_options or DEFAULT_REQUEST_OPTIONS)
    )
    if append_from is not None:
        append_from = append_from.expanduser().resolve()
        if append_from.exists():
            s = append_from.read_text()
            if append_from_format == "json":
                append_history = TemperatureHistory.deserialize(json.loads(s))
            else:
                append_history = TemperatureHistory.deserialize_str(history.base_unit, s)
            history = history.combine_with(append_history)
    if output_format == "json":
        output_str = json.dumps(history.serialize(), indent=2)
    elif output_format == "current":
        output_str = history.serialize_current_str()
    else:
        output_str = history.serialize_str()
    if output_file is not None:
        if output_file.exists() and output_file.read_text() == output_str:
            if not suppress_click_echo:
                click_secho(
                    f"Output file {output_file} already exists and has the same content, skipping write.",
                    fg="cyan"
                )
            return history, False
        output_file.write_text(output_str)
        return history, True
    click.echo(output_str)
    return history, True

if orm_cli is not None:
    # Type ignore is needed here because the click_extra.group decorator's
    # signature is not correctly recognized by type checkers.
    cli.add_command(orm_cli)  # type: ignore[arg-type]
if influxdb_cli is not None:
    cli.add_command(influxdb_cli)

if __name__ == "__main__":
    cli()
