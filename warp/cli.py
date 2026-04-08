from flask.cli import FlaskGroup

from warp import create_app


def main():
    cli = FlaskGroup(create_app=create_app)
    cli()


if __name__ == "__main__":
    main()
