import contextlib
import unittest
from unittest import mock

import flask

from warp import admin_cli
from warp.db import ACCOUNT_TYPE_ADMIN, ACCOUNT_TYPE_BLOCKED, ACCOUNT_TYPE_USER


class _FakeColumn:

    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return (self.name, "==", other)

    def __lt__(self, other):
        return (self.name, "<", other)

    def __ge__(self, other):
        return (self.name, ">=", other)


def _chainable_query(*, rows=None, scalar=None, execute=None):
    query = mock.Mock()
    query.where.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.iterator.side_effect = lambda: iter(rows or [])
    if scalar is not None:
        query.scalar.return_value = scalar
    if execute is not None:
        query.execute.return_value = execute
    return query


def _fake_table(name):
    table = mock.Mock(name=name)
    table.login = _FakeColumn(f"{name}.login")
    table.name = _FakeColumn(f"{name}.name")
    table.account_type = _FakeColumn(f"{name}.account_type")
    table.password = _FakeColumn(f"{name}.password")
    table.fromts = _FakeColumn(f"{name}.fromts")
    table.tots = _FakeColumn(f"{name}.tots")
    return table


class AdminCliTests(unittest.TestCase):

    def setUp(self):
        self.app = flask.Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            DATABASE="sqlite://",
        )
        admin_cli.init(self.app)
        self.runner = self.app.test_cli_runner()

    def _db(self):
        db = mock.Mock()
        db.connection_context.return_value = contextlib.nullcontext()
        db.atomic.return_value = contextlib.nullcontext()
        return db

    def test_list_users_prints_tabular_output(self):
        users = _fake_table("Users")
        users.select.return_value = _chainable_query(rows=[
            {"login": "admin", "name": "Admin User", "account_type": ACCOUNT_TYPE_ADMIN},
            {"login": "alice", "name": "Alice Example", "account_type": ACCOUNT_TYPE_USER},
        ])

        with mock.patch.object(admin_cli, "DB", self._db()), \
             mock.patch.object(admin_cli, "Users", users):
            result = self.runner.invoke(args=["admin", "user", "list"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("LOGIN\tROLE\tNAME", result.output)
        self.assertIn("admin\tadmin\tAdmin User", result.output)
        self.assertIn("alice\tuser\tAlice Example", result.output)

    def test_create_user_generates_password_when_requested(self):
        users = _fake_table("Users")
        users.insert.return_value = _chainable_query(execute=1)

        with mock.patch.object(admin_cli, "DB", self._db()), \
             mock.patch.object(admin_cli, "Users", users), \
             mock.patch.object(admin_cli.secrets, "token_urlsafe", return_value="generated-pass"), \
             mock.patch.object(admin_cli, "generate_password_hash", return_value="hashed-pass"):
            result = self.runner.invoke(args=[
                "admin", "user", "create", "alice",
                "--name", "Alice Example",
                "--generate-password",
            ])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Created user 'alice' with role 'user'.", result.output)
        self.assertIn("Generated password: generated-pass", result.output)
        insert_payload = users.insert.call_args.args[0]
        self.assertEqual(insert_payload[users.login], "alice")
        self.assertEqual(insert_payload[users.name], "Alice Example")
        self.assertEqual(insert_payload[users.account_type], ACCOUNT_TYPE_USER)
        self.assertEqual(insert_payload[users.password], "hashed-pass")

    def test_update_user_changes_name(self):
        users = _fake_table("Users")
        users.select.side_effect = [
            _chainable_query(rows=[{
                "login": "alice",
                "name": "Alice Example",
                "account_type": ACCOUNT_TYPE_USER,
            }]),
        ]
        users.update.return_value = _chainable_query(execute=1)

        with mock.patch.object(admin_cli, "DB", self._db()), \
             mock.patch.object(admin_cli, "Users", users):
            result = self.runner.invoke(args=[
                "admin", "user", "update", "alice",
                "--name", "Alice Smith",
            ])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Updated user 'alice'.", result.output)
        update_payload = users.update.call_args.args[0]
        self.assertEqual(update_payload[users.name], "Alice Smith")

    def test_block_rejects_last_admin(self):
        users = _fake_table("Users")
        users.select.side_effect = [
            _chainable_query(rows=[{
                "login": "admin",
                "name": "Admin User",
                "account_type": ACCOUNT_TYPE_ADMIN,
            }]),
            _chainable_query(scalar=1),
        ]

        with mock.patch.object(admin_cli, "DB", self._db()), \
             mock.patch.object(admin_cli, "Users", users):
            result = self.runner.invoke(args=["admin", "user", "block", "admin"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("last remaining admin account", result.output)
        users.update.assert_not_called()

    def test_reset_password_updates_password_hash(self):
        users = _fake_table("Users")
        users.select.side_effect = [
            _chainable_query(rows=[{
                "login": "alice",
                "name": "Alice Example",
                "account_type": ACCOUNT_TYPE_USER,
            }]),
        ]
        users.update.return_value = _chainable_query(execute=1)

        with mock.patch.object(admin_cli, "DB", self._db()), \
             mock.patch.object(admin_cli, "Users", users), \
             mock.patch.object(admin_cli, "generate_password_hash", return_value="hashed-reset"):
            result = self.runner.invoke(args=[
                "admin", "user", "reset-password", "alice",
                "--password", "new-password",
            ])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Password reset for user 'alice'.", result.output)
        update_payload = users.update.call_args.args[0]
        self.assertEqual(update_payload[users.password], "hashed-reset")

    def test_delete_force_archives_user_with_past_bookings(self):
        users = _fake_table("Users")
        book = _fake_table("Book")
        seat_assign = _fake_table("SeatAssign")
        groups = _fake_table("Groups")
        zone_assign = _fake_table("ZoneAssign")

        users.select.side_effect = [
            _chainable_query(rows=[{
                "login": "alice",
                "name": "Alice Example",
                "account_type": ACCOUNT_TYPE_USER,
            }]),
        ]
        book.select.return_value = _chainable_query(scalar=2)
        book.delete.return_value = _chainable_query(execute=1)
        seat_assign.delete.return_value = _chainable_query(execute=1)
        groups.delete.return_value = _chainable_query(execute=1)
        zone_assign.delete.return_value = _chainable_query(execute=1)
        users.update.return_value = _chainable_query(execute=1)

        with mock.patch.object(admin_cli, "DB", self._db()), \
             mock.patch.object(admin_cli, "Users", users), \
             mock.patch.object(admin_cli, "Book", book), \
             mock.patch.object(admin_cli, "SeatAssign", seat_assign), \
             mock.patch.object(admin_cli, "Groups", groups), \
             mock.patch.object(admin_cli, "ZoneAssign", zone_assign), \
             mock.patch.object(admin_cli.utils, "today", return_value=1000):
            result = self.runner.invoke(args=[
                "admin", "user", "delete", "alice",
                "--force",
            ])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Archived user 'alice' and preserved booking history.", result.output)
        users.delete.assert_not_called()
        users.update.assert_called_once()
        book.delete.assert_called_once()


if __name__ == "__main__":
    unittest.main()
