"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, input009):
        if type(input009) is not str:
            raise TypeError("exact str required")
        left009 = "SELECT * FROM orders WHERE id = '"
        right009 = "'"
        value009 = _extracted_value(left009, input009, right009)
        self.cursor.execute(value009)
        return self.cursor.fetchall()


def _extracted_value(left009, input009, right009):
    return left009 + input009 + right009
