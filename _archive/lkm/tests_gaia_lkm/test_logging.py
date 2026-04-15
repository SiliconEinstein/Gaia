import logging
from pathlib import Path


def test_configure_logging_console_only():
    from gaia.lkm.logging import configure_logging

    configure_logging(level="DEBUG")
    logger = logging.getLogger("gaia.lkm.test")
    assert logger.getEffectiveLevel() <= logging.DEBUG


def test_configure_logging_with_file(tmp_path: Path):
    from gaia.lkm.logging import configure_logging

    log_file = tmp_path / "test.log"
    configure_logging(level="INFO", log_file=log_file)
    logger = logging.getLogger("gaia.lkm.test_file")
    logger.info("hello")
    assert log_file.exists()
    assert "hello" in log_file.read_text()
