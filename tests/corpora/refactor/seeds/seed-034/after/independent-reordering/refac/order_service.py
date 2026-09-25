"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, input033):
        if type(input033) is not str:
            raise TypeError("exact str required")
        right033 = "'"
        left033 = "SELECT * FROM orders WHERE id = '"
        value033 = left033 + input033 + right033
        self.cursor.execute(value033)
        return self.cursor.fetchall()
