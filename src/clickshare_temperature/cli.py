from __future__ import annotations
from typing import Literal
import asyncio
from pathlib import Path
import json

import click

from clickshare_temperature.types import AuthInfo

from .temperature_history import TemperatureHistory
from .log_archive import LogArchive
from .types import AioHttpRequestOptions, AioHttpSessionOptions

DEFAULT_REQUEST_OPTIONS: AioHttpRequestOptions = {
    "ssl": False,
}

DEFAULT_SESSION_OPTIONS: AioHttpSessionOptions = {}

type OutputFormat = Literal["str", "json", "current"]
type AppendFromFormat = Literal["str", "json"]



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
    type=str,
    required=True,
    prompt=True,
    help="Username for BaseUnit API authentication.",
)
@click.option(
    "--password", "-p",
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
    download(
        baseunit_ip=baseunit_ip,
        username=username,
        password=password,
        append_from=append_from,
        append_from_format=append_from_format,
        output_format=output_format,
        output_file=output_file,
        raw_logs=raw_logs,
    )


def download(
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
):
    auth = AuthInfo(username=username, password=password)
    if raw_logs:
        if output_file is None:
            raise ValueError("Output file must be specified when --raw-logs flag is set.")
        archive = asyncio.run(LogArchive.from_baseunit(
            baseunit_ip,
            auth_info=auth,
            session_options=session_options or DEFAULT_SESSION_OPTIONS,
            **(request_options or DEFAULT_REQUEST_OPTIONS)
        ))
        if append_from is not None:
            s = append_from.expanduser().resolve().read_text()
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
            data = archive.serialize()
            output_file.write_text(json.dumps(data, indent=2))
        else:
            output_file.write_text(archive.serialize_str())
        return
    history = asyncio.run(TemperatureHistory.from_baseunit(
        baseunit_ip,
        auth_info=auth,
        session_options=session_options or DEFAULT_SESSION_OPTIONS,
        **(request_options or DEFAULT_REQUEST_OPTIONS)
    ))
    if append_from is not None:
        s = append_from.expanduser().resolve().read_text()
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
        output_file.write_text(output_str)
    else:
        click.echo(output_str)


if __name__ == "__main__":
    cli()
