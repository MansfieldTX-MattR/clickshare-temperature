from __future__ import annotations
from typing import Literal
import asyncio
from pathlib import Path
import json

from dotenv import load_dotenv
from aiohttp import ClientSession
import click

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

load_dotenv()


type OutputFormat = Literal["str", "json", "current"]
type AppendFromFormat = Literal["str", "json"]


type ClickColor = Literal[
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
    "reset",
]

def click_secho(
    msg: str,
    nl: bool = True,
    err: bool = False,
    color: bool|None = None,
    fg: ClickColor|None = None
) -> None:
    """Wrapper around click.secho with a typed color argument"""
    click.secho(msg, nl=nl, err=err, color=color, fg=fg)



@click.group()
def cli():
    """CLI for working with ClickShare BaseUnit temperature logs."""
    pass

@cli.command(name="parse")
@click.argument(
    "input_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--output-format", "-f",
    type=click.Choice(["str", "json", "current"], case_sensitive=False),
    default="str",
    help="Output format. Can be either 'str', 'json', or 'current'. Default is 'str'." \
    "If 'current' is specified, only the most recent reading for each sensor will be outputted.",
)
@click.option(
    "--output-file", "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to output file. If not provided, the output will be printed to stdout.",
)
def cli_parse(input_file: Path, output_format: OutputFormat, output_file: Path|None):
    """Parse a log archive and extract temperature readings."""
    parse(input_file, output_format, output_file)


def parse(input_file: Path, output_format: OutputFormat, output_file: Path|None):
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
@click.argument(
    "baseunit_ip",
    type=str,
)
@click.option(
    "--username", "-u",
    envvar="CLICKSHARE_BASEUNIT_USERNAME",
    type=str,
    required=True,
    prompt=True,
    help="Username for BaseUnit API authentication.",
)
@click.option(
    "--password", "-p",
    envvar="CLICKSHARE_BASEUNIT_PASSWORD",
    type=str,
    required=True,
    prompt=True,
    hide_input=True,
    help="Password for BaseUnit API authentication.",
)
@click.option(
    "--append-from", "-a",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a log archive file to append readings from. " \
    "If provided, the readings from the downloaded logs will be appended to the readings from this file, and the combined readings will be outputted.",
)
@click.option(
    "--append-from-format", "-A",
    type=click.Choice(["str", "json"], case_sensitive=False),
    default="str",
    help="Format of the file provided to --append-from. Can be either 'str' or 'json'. Default is 'str'. Ignored if --append-from is not provided.",
)
@click.option(
    "--output-format", "-f",
    type=click.Choice(["str", "json", "current"], case_sensitive=False),
    default="str",
    help="Output format. Can be either 'str', 'json', or 'current'. Default is 'str'." \
    "If 'current' is specified, only the most recent reading for each sensor will be outputted.",
)
@click.option(
    "--output-file", "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to output file. If not provided, the output will be printed to stdout.",
)
@click.option(
    "--raw-logs",
    is_flag=True,
    help="If set, the raw log archive will be downloaded and saved to the specified output file instead of " \
    "parsing the logs and extracting temperature readings. The output format options will be ignored. " \
    "If this flag is set, the output file option is required.",
)
def cli_download(
    baseunit_ip: str,
    username: str,
    password: str,
    append_from: Path|None,
    append_from_format: AppendFromFormat,
    output_format: OutputFormat,
    output_file: Path|None,
    raw_logs: bool,
):
    """Download logs from the BaseUnit and extract temperature readings."""
    asyncio.run(download(
        baseunit_ip=baseunit_ip,
        username=username,
        password=password,
        append_from=append_from,
        append_from_format=append_from_format,
        output_format=output_format,
        output_file=output_file,
        raw_logs=raw_logs,
    ))


def get_output_file_for_baseunit(base_dir: Path, room_name: str, hostname: str, output_format: OutputFormat) -> Path:
    """Find the output file for a BaseUnit based on the room name and hostname.

    The file will be located in the specified base directory,
    and will have a name in the format "{room_name}.{hostname}.{ext}",
    where {ext} is either "txt" or "json" depending on the output format.

    If a file already exists in the base directory that matches the hostname
    and extension, that file will be used instead of creating a new one.

    This allows for appending to existing files if the room name has changed
    since the last download.
    """
    out_ext = "txt" if output_format in ("str", "current") else "json"
    for p in base_dir.glob(f"*.{hostname}.{out_ext}"):
        return p
    return base_dir / f"{room_name}.{hostname}.{out_ext}"


@cli.command(name="download-multiple")
@click.argument(
    "baseunit_ip_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    # help="Path to a text file containing a list of BaseUnit IP addresses, one per line.",
)
@click.option(
    "--username", "-u",
    envvar="CLICKSHARE_BASEUNIT_USERNAME",
    type=str,
    required=True,
    prompt=True,
    help="Username for BaseUnit API authentication.",
)
@click.option(
    "--password", "-p",
    envvar="CLICKSHARE_BASEUNIT_PASSWORD",
    type=str,
    required=True,
    prompt=True,
    hide_input=True,
    help="Password for BaseUnit API authentication.",
)
@click.option(
    "--append-from", "-a",
    type=click.Path(exists=True, dir_okay=True, path_type=Path),
    required=True,
    help="Path to a directory containing log archive files to append readings from. " \
    "For each BaseUnit IP address, the file in this directory with the hostname of the BaseUnit will be used to append readings. " \
    "If provided, the readings from the downloaded logs will be appended to the readings from these files, and the combined readings will be outputted.",
)
@click.option(
    "--append-from-format", "-A",
    type=click.Choice(["str", "json"], case_sensitive=False),
    default="str",
    help="Format of the file provided to --append-from. Can be either 'str' or 'json'. Default is 'str'. Ignored if --append-from is not provided.",
)
@click.option(
    "--output-format", "-f",
    type=click.Choice(["str", "json", "current"], case_sensitive=False),
    default="str",
    help="Output format. Can be either 'str', 'json', or 'current'. Default is 'str'." \
    "If 'current' is specified, only the most recent reading for each sensor will be outputted.",
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Path to output directory. For each BaseUnit IP address, " \
    "a file will be created in this directory with the hostname of the BaseUnit containing the output for that BaseUnit.",
)
@click.option(
    "--raw-logs",
    is_flag=True,
    help="If set, the raw log archive will be downloaded and saved to the specified output file instead of " \
    "parsing the logs and extracting temperature readings. The output format options will be ignored. " \
    "If this flag is set, the output file option is required.",
)
def cli_download_multiple(
    baseunit_ip_file: Path,
    username: str,
    password: str,
    append_from: Path,
    append_from_format: AppendFromFormat,
    output_format: OutputFormat,
    output_dir: Path,
    raw_logs: bool,
):
    """Download logs from multiple BaseUnits and extract temperature readings."""
    baseunit_ip_file = baseunit_ip_file.expanduser().resolve()
    output_dir_original = output_dir
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with baseunit_ip_file.open() as f:
        baseunit_ips = [line.strip() for line in f if line.strip()]

    async def run_download(baseunit_ip: str, session: ClientSession):
        click_secho(f"Processing BaseUnit {baseunit_ip}...", fg="white")
        base_unit = await get_baseunit_info(
            baseunit_ip,
            auth_info=AuthInfo(username=username, password=password),
            session=session,
            **DEFAULT_REQUEST_OPTIONS,
        )

        append_from_file = get_output_file_for_baseunit(
            append_from, base_unit.room_name, base_unit.hostname, output_format
        )
        final_output_file = get_output_file_for_baseunit(
            output_dir, base_unit.room_name, base_unit.hostname, output_format
        )

        file_written = await download(
            baseunit_ip=baseunit_ip,
            username=username,
            password=password,
            append_from=append_from_file,
            append_from_format=append_from_format,
            output_format=output_format,
            output_file=final_output_file,
            raw_logs=raw_logs,
            suppress_click_echo=True,
        )
        msg = f"Finished processing BaseUnit {baseunit_ip} (room name: {room_name}, hostname: {hostname})."
        if file_written:
            msg += f" Output file: {output_dir_original / final_output_file.name}."
            color = "bright_green"
        else:
            msg += " No changes to output file."
            color = None
        click_secho(msg, fg=color)


    async def run_downloads():
        async with create_session(**DEFAULT_SESSION_OPTIONS) as session:
            tasks = [run_download(baseunit_ip, session) for baseunit_ip in baseunit_ips]
            await asyncio.gather(*tasks)

    asyncio.run(run_downloads())


async def download(
    baseunit_ip: str,
    username: str,
    password: str,
    append_from: Path|None,
    append_from_format: AppendFromFormat,
    output_format: OutputFormat,
    output_file: Path|None,
    session_options: AioHttpSessionOptions|None = None,
    request_options: AioHttpRequestOptions|None = None,
    raw_logs: bool = False,
    suppress_click_echo: bool = False,
):
    auth = AuthInfo(username=username, password=password)
    if raw_logs:
        if output_file is None:
            raise ValueError("Output file must be specified when --raw-logs flag is set.")
        archive = await LogArchive.from_baseunit(
            baseunit_ip,
            auth_info=auth,
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
            return False
        output_file.write_text(output_str)
        return True
    history = await TemperatureHistory.from_baseunit(
        baseunit_ip,
        auth_info=auth,
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
                append_history = TemperatureHistory.deserialize_str(s)
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
            return False
        output_file.write_text(output_str)
        return True
    click.echo(output_str)
    return True


if __name__ == "__main__":
    cli()
