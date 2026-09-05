import tomllib
from pathlib import Path


def test_pyproject_limits_setuptools_package_discovery() -> None:
    raw = tomllib.loads(Path("pyproject.toml").read_text())

    package_find = raw["tool"]["setuptools"]["packages"]["find"]

    assert package_find["include"] == ["notedesk*"]
    assert package_find["exclude"] == ["skills*"]
