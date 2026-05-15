# Log File Info

This directory contains log files used to test log parsing functionality.


The `full_info` file contains all expected log entries found in the `test_log_archive.py` fixture.

The `rotated/log/` directory contains the same log entries, but with some entries duplicated to simulate log rotation.

The `archive.tar.gz` file has the same contents as `rotated/log/`, but with the `info.x` files compressed as `info.x.gz`.
This is built by the `build_archive.py` script.


> [!IMPORTANT]
> There is intentional white space in some of the log entries. Do not remove or modify it when editing the log files.
