import click
from flask.cli import FlaskGroup

from warp import create_app
from warp.version import get_runtime_version


@click.group(cls=FlaskGroup, create_app=create_app, add_version_option=False)
@click.version_option(version=get_runtime_version(), prog_name="warp")
def cli():
    """WARP command line interface."""


def main():
    cli()


if __name__ == "__main__":
    main()
