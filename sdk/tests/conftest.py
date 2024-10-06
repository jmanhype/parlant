from pathlib import Path
import shutil
import tempfile
from typing import Iterator
from pytest import fixture

from tests.test_utilities import ContextOfTest, get_package_path


@fixture
def context() -> Iterator[ContextOfTest]:
    with tempfile.TemporaryDirectory(prefix="emcie-sdk-test_") as home_dir:
        home_dir_path = Path(home_dir)
        active_config_file_path = home_dir_path / "config.json"

        config_template_file = get_package_path() / "../server/_config.json"
        shutil.copy(config_template_file, active_config_file_path)

        yield ContextOfTest(
            home_dir=home_dir_path,
            config_file=active_config_file_path,
            index_file=home_dir_path / "index.json",
        )
