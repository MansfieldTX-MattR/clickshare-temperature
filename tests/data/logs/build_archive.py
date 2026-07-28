from __future__ import annotations

import gzip
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
LOG_PARENT_DIR = HERE / "rotated"

def build_log_archive(output_path: Path = HERE / "archive.tar.gz") -> None:
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str).resolve()
        tmpdir_logs_dir = tmpdir / "log"
        tmpdir_logs_dir.mkdir()
        log_dir = LOG_PARENT_DIR / "log"
        archive_filenames: list[Path] = []
        for p in log_dir.glob("info*"):
            print(f"Processing log file: {p}")
            if p.name == "info":
                needs_gzip = False
            else:
                needs_gzip = True
            log_content_bytes = p.read_bytes()
            if needs_gzip:
                log_content = log_content_bytes.decode("utf-8")
                log_filename = tmpdir / (p.name + ".gz")
                print(f"Creating gzipped log file: {log_filename}")
                with gzip.open(log_filename, "wt") as f:
                    f.write(log_content)
                archive_filenames.append(log_filename)
            else:
                print(f"Adding uncompressed log file: {p}")
                archive_filenames.append(p)
        with tarfile.open(output_path, "w:gz") as tar:
            for filename in archive_filenames:
                tar.add(filename, arcname=Path("log") / filename.name)


if __name__ == "__main__":
    build_log_archive()
