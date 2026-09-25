"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, renamed0):
        if type(renamed0) is not str:
            raise TypeError("exact str required")
        renamed1 = "SELECT * FROM orders WHERE id = '"
        renamed2 = "'"
        renamed3 = _extracted_value(renamed1, renamed0, renamed2)
        self.cursor.execute(renamed3)
        return self.cursor.fetchall()


def _extracted_value(renamed1, renamed0, renamed2):
    return renamed1 + renamed0 + renamed2
