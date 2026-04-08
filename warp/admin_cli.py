import secrets

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from warp import utils
from warp.db import *


ROLE_NAME_TO_TYPE = {
    "admin": ACCOUNT_TYPE_ADMIN,
    "user": ACCOUNT_TYPE_USER,
    "blocked": ACCOUNT_TYPE_BLOCKED,
}

ROLE_TYPE_TO_NAME = {
    ACCOUNT_TYPE_ADMIN: "admin",
    ACCOUNT_TYPE_USER: "user",
    ACCOUNT_TYPE_BLOCKED: "blocked",
    ACCOUNT_TYPE_GROUP: "group",
}


def init(app):
    app.cli.add_command(admin_cli)


def _user_role_name(account_type):
    return ROLE_TYPE_TO_NAME.get(account_type, f"unknown:{account_type}")


def _first_row(query):
    rows = [*query.limit(1).iterator()]
    if rows:
        return rows[0]
    return None


def _get_user(login):
    return _first_row(
        Users.select(Users.login, Users.name, Users.account_type)
        .where(Users.login == login)
    )


def _require_user(login):
    user = _get_user(login)
    if user is None:
        raise click.ClickException(f"User '{login}' was not found.")
    if user["account_type"] >= ACCOUNT_TYPE_GROUP:
        raise click.ClickException(f"User '{login}' is a group and cannot be managed with this command.")
    return user


def _admin_count():
    return Users.select(COUNT_STAR).where(Users.account_type == ACCOUNT_TYPE_ADMIN).scalar()


def _protect_last_admin(user, action):
    if user["account_type"] != ACCOUNT_TYPE_ADMIN:
        return

    if _admin_count() <= 1:
        raise click.ClickException(
            f"Refusing to {action} the last remaining admin account '{user['login']}'."
        )


def _resolve_password(password, generate):
    if password and generate:
        raise click.ClickException("Use either --password or --generate-password, not both.")

    generated_password = None
    if generate:
        generated_password = secrets.token_urlsafe(12)
        password = generated_password

    return password, generated_password


@click.group("admin")
def admin_cli():
    """Administrative commands."""


@admin_cli.group("user")
def admin_user_cli():
    """Manage users."""


@admin_user_cli.command("list")
@with_appcontext
def list_users():
    """List managed users."""

    with DB.connection_context():
        users = [
            *Users.select(Users.login, Users.name, Users.account_type)
            .where(Users.account_type < ACCOUNT_TYPE_GROUP)
            .order_by(Users.login)
            .iterator()
        ]

    if not users:
        click.echo("No users found.")
        return

    click.echo("LOGIN\tROLE\tNAME")
    for user in users:
        click.echo(
            f"{user['login']}\t{_user_role_name(user['account_type'])}\t{user['name']}"
        )


@admin_user_cli.command("create")
@click.argument("login")
@click.option("--name", required=True, help="Display name for the user.")
@click.option(
    "--role",
    type=click.Choice(sorted(ROLE_NAME_TO_TYPE.keys())),
    default="user",
    show_default=True,
    help="Initial role for the user.",
)
@click.option("--password", help="Plaintext password to set for the user.")
@click.option(
    "--generate-password",
    is_flag=True,
    help="Generate a random password and print it once.",
)
@with_appcontext
def create_user(login, name, role, password, generate_password):
    """Create a user."""

    password, generated_password = _resolve_password(password, generate_password)
    role_type = ROLE_NAME_TO_TYPE[role]

    if role_type < ACCOUNT_TYPE_BLOCKED and not password:
        raise click.ClickException(
            "Active users require a password. Use --password or --generate-password."
        )

    password_hash = generate_password_hash(password) if password else None

    try:
        with DB.connection_context():
            Users.insert({
                Users.login: login,
                Users.name: name,
                Users.account_type: role_type,
                Users.password: password_hash,
            }).execute()
    except IntegrityError as err:
        raise click.ClickException(f"User '{login}' already exists.") from err

    click.echo(f"Created user '{login}' with role '{role}'.")
    if generated_password:
        click.echo(f"Generated password: {generated_password}")


@admin_user_cli.command("update")
@click.argument("login")
@click.option("--name", help="New display name.")
@click.option(
    "--role",
    type=click.Choice(sorted(ROLE_NAME_TO_TYPE.keys())),
    help="New role for the user.",
)
@with_appcontext
def update_user(login, name, role):
    """Update a user's name or role."""

    if name is None and role is None:
        raise click.ClickException("Specify at least one change, such as --name or --role.")

    with DB.connection_context():
        user = _require_user(login)

        updates = {}
        if name is not None:
            updates[Users.name] = name

        if role is not None:
            role_type = ROLE_NAME_TO_TYPE[role]
            if user["account_type"] == ACCOUNT_TYPE_ADMIN and role_type != ACCOUNT_TYPE_ADMIN:
                _protect_last_admin(user, "demote")
            updates[Users.account_type] = role_type

        row_count = Users.update(updates) \
            .where(Users.login == login) \
            .where(Users.account_type < ACCOUNT_TYPE_GROUP) \
            .execute()

    if row_count != 1:
        raise click.ClickException(f"Failed to update user '{login}'.")

    click.echo(f"Updated user '{login}'.")


@admin_user_cli.command("block")
@click.argument("login")
@with_appcontext
def block_user(login):
    """Block a user from logging in."""

    with DB.connection_context():
        user = _require_user(login)
        _protect_last_admin(user, "block")

        row_count = Users.update({
            Users.account_type: ACCOUNT_TYPE_BLOCKED,
        }) \
        .where(Users.login == login) \
        .where(Users.account_type < ACCOUNT_TYPE_GROUP) \
        .execute()

    if row_count != 1:
        raise click.ClickException(f"Failed to block user '{login}'.")

    click.echo(f"Blocked user '{login}'.")


@admin_user_cli.command("unblock")
@click.argument("login")
@click.option(
    "--role",
    type=click.Choice(["admin", "user"]),
    default="user",
    show_default=True,
    help="Role to restore when unblocking the user.",
)
@with_appcontext
def unblock_user(login, role):
    """Unblock a user and restore a role."""

    role_type = ROLE_NAME_TO_TYPE[role]

    with DB.connection_context():
        _require_user(login)

        row_count = Users.update({
            Users.account_type: role_type,
        }) \
        .where(Users.login == login) \
        .where(Users.account_type < ACCOUNT_TYPE_GROUP) \
        .execute()

    if row_count != 1:
        raise click.ClickException(f"Failed to unblock user '{login}'.")

    click.echo(f"Set user '{login}' to role '{role}'.")


@admin_user_cli.command("reset-password")
@click.argument("login")
@click.option("--password", help="Plaintext password to set.")
@click.option(
    "--generate-password",
    is_flag=True,
    help="Generate a random password and print it once.",
)
@with_appcontext
def reset_password(login, password, generate_password):
    """Reset a user's password."""

    password, generated_password = _resolve_password(password, generate_password)
    if not password:
        raise click.ClickException("Use --password or --generate-password.")

    password_hash = generate_password_hash(password)

    with DB.connection_context():
        _require_user(login)

        row_count = Users.update({
            Users.password: password_hash,
        }) \
        .where(Users.login == login) \
        .where(Users.account_type < ACCOUNT_TYPE_GROUP) \
        .execute()

    if row_count != 1:
        raise click.ClickException(f"Failed to reset password for user '{login}'.")

    click.echo(f"Password reset for user '{login}'.")
    if generated_password:
        click.echo(f"Generated password: {generated_password}")


@admin_user_cli.command("delete")
@click.argument("login")
@click.option(
    "--force",
    is_flag=True,
    help="Archive the user when past bookings exist instead of refusing deletion.",
)
@with_appcontext
def delete_user(login, force):
    """Delete a user."""

    today = utils.today()

    with DB.connection_context():
        user = _require_user(login)
        _protect_last_admin(user, "delete")

        past_book_count = Book.select(COUNT_STAR) \
            .where(Book.login == login) \
            .where(Book.fromts < today) \
            .scalar()

        if past_book_count and not force:
            raise click.ClickException(
                f"User '{login}' has {past_book_count} past bookings. Use --force to archive instead."
            )

        with DB.atomic():
            if past_book_count:
                Book.delete() \
                    .where(Book.login == login) \
                    .where(Book.tots >= today) \
                    .execute()

                SeatAssign.delete() \
                    .where(SeatAssign.login == login) \
                    .execute()

                Groups.delete() \
                    .where(Groups.login == login) \
                    .execute()

                ZoneAssign.delete() \
                    .where(ZoneAssign.login == login) \
                    .execute()

                row_count = Users.update({
                    Users.account_type: ACCOUNT_TYPE_BLOCKED,
                    Users.password: None,
                }) \
                .where(Users.login == login) \
                .where(Users.account_type < ACCOUNT_TYPE_GROUP) \
                .execute()

                if row_count != 1:
                    raise click.ClickException(f"Failed to archive user '{login}'.")

                click.echo(f"Archived user '{login}' and preserved booking history.")
                return

            row_count = Users.delete() \
                .where(Users.login == login) \
                .where(Users.account_type < ACCOUNT_TYPE_GROUP) \
                .execute()

    if row_count != 1:
        raise click.ClickException(f"Failed to delete user '{login}'.")

    click.echo(f"Deleted user '{login}'.")
