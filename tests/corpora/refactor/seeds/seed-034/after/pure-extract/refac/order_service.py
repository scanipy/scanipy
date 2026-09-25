"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, input033):
        if type(input033) is not str:
            raise TypeError("exact str required")
        left033 = "SELECT * FROM orders WHERE id = '"
        right033 = "'"
        value033 = _extracted_value(left033, input033, right033)
        self.cursor.execute(value033)
        return self.cursor.fetchall()


def _extracted_value(left033, input033, right033):
    return left033 + input033 + right033
