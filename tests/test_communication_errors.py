from __future__ import annotations
import warnings
import subprocess
import sys

import pytest

from clickshare_temperature.orm.cli import (
    CommunicationError,
    COMMUNICATION_ERROR_EXIT_CODE,
    catch_communication_errors,
    raise_communication_errors,
)


def test_communication_error_caught():
    def func() -> str:
        warnings.warn("This is a communication error", CommunicationError)
        return "Function executed"

    result, had_error = catch_communication_errors(func)
    assert had_error
    assert result == "Function executed"


def test_communication_error_exit_code():
    def func() -> str:
        warnings.warn("This is a communication error", CommunicationError)
        return "Function executed"

    with pytest.raises(SystemExit) as exc_info:
        raise_communication_errors(func)
    assert exc_info.value.code == COMMUNICATION_ERROR_EXIT_CODE


def test_communication_error_exit_code_in_subprocess():
    script = """
import warnings
from clickshare_temperature.orm.cli import CommunicationError, raise_communication_errors

def func() -> str:
    warnings.warn("This is a communication error", CommunicationError)
    return "Function executed"

if __name__ == "__main__":
    raise_communication_errors(func)
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == COMMUNICATION_ERROR_EXIT_CODE
