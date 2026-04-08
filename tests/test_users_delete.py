import contextlib
import unittest
from unittest import mock

import flask

from warp.xhr import users as users_xhr


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


def _chainable_query(*, scalar=None, execute=None):
    query = mock.Mock()
    query.where.return_value = query
    if scalar is not None:
        query.scalar.return_value = scalar
    if execute is not None:
        query.execute.return_value = execute
    return query


def _fake_table(name):
    table = mock.Mock(name=name)
    table.login = _FakeColumn(f"{name}.login")
    table.fromts = _FakeColumn(f"{name}.fromts")
    table.tots = _FakeColumn(f"{name}.tots")
    table.password = _FakeColumn(f"{name}.password")
    table.account_type = _FakeColumn(f"{name}.account_type")
    return table


class DeleteUserTests(unittest.TestCase):

    def setUp(self):
        self.app = flask.Flask(__name__)

    def _call_delete(self, payload, *, past_book_count, user_delete_rowcount=1, user_update_rowcount=1):
        book = _fake_table("Book")
        users = _fake_table("Users")
        seat_assign = _fake_table("SeatAssign")
        groups = _fake_table("Groups")
        zone_assign = _fake_table("ZoneAssign")

        book_count_query = _chainable_query(scalar=past_book_count)
        future_book_delete_query = _chainable_query(execute=1)
        seat_assign_delete_query = _chainable_query(execute=1)
        groups_delete_query = _chainable_query(execute=1)
        zone_assign_delete_query = _chainable_query(execute=1)
        users_delete_query = _chainable_query(execute=user_delete_rowcount)
        users_update_query = _chainable_query(execute=user_update_rowcount)

        book.select.return_value = book_count_query
        book.delete.return_value = future_book_delete_query
        users.delete.return_value = users_delete_query
        users.update.return_value = users_update_query
        seat_assign.delete.return_value = seat_assign_delete_query
        groups.delete.return_value = groups_delete_query
        zone_assign.delete.return_value = zone_assign_delete_query

        db = mock.Mock()
        db.atomic.return_value = contextlib.nullcontext()

        with self.app.test_request_context(json=payload):
            flask.g.isAdmin = True

            with mock.patch.object(users_xhr, 'Book', book), \
                 mock.patch.object(users_xhr, 'Users', users), \
                 mock.patch.object(users_xhr, 'SeatAssign', seat_assign), \
                 mock.patch.object(users_xhr, 'Groups', groups), \
                 mock.patch.object(users_xhr, 'ZoneAssign', zone_assign), \
                 mock.patch.object(users_xhr, 'DB', db), \
                 mock.patch.object(users_xhr.utils, 'today', return_value=1000):

                response = users_xhr.delete.__wrapped__()

        return {
            "response": response,
            "Book": book,
            "Users": users,
            "SeatAssign": seat_assign,
            "Groups": groups,
            "ZoneAssign": zone_assign,
        }

    def test_delete_requires_force_when_past_bookings_exist(self):
        result = self._call_delete({"login": "alice"}, past_book_count=2)

        self.assertEqual(
            result["response"],
            ({"msg": "User has past bookings", "bookCount": 2, "code": 173}, 406)
        )
        result["Users"].delete.assert_not_called()
        result["Users"].update.assert_not_called()

    def test_force_delete_archives_user_with_past_bookings(self):
        result = self._call_delete({"login": "alice", "force": True}, past_book_count=2)

        self.assertEqual(result["response"], ({"msg": "ok", "action": "archived"}, 200))
        result["Book"].delete.assert_called_once()
        result["SeatAssign"].delete.assert_called_once()
        result["Groups"].delete.assert_called_once()
        result["ZoneAssign"].delete.assert_called_once()
        result["Users"].update.assert_called_once()
        result["Users"].delete.assert_not_called()

    def test_delete_without_past_bookings_hard_deletes_user(self):
        result = self._call_delete({"login": "alice"}, past_book_count=0)

        self.assertEqual(result["response"], ({"msg": "ok"}, 200))
        result["Users"].delete.assert_called_once()
        result["Users"].update.assert_not_called()
        result["Book"].delete.assert_not_called()


if __name__ == '__main__':
    unittest.main()
