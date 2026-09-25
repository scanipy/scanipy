"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, input025):
        if type(input025) is not str:
            raise TypeError("exact str required")
        left025 = "SELECT * FROM orders WHERE id = '"
        right025 = "'"
        value025 = "SELECT * FROM orders WHERE id = ?"
        self.cursor.execute(value025, (input025,))
        return self.cursor.fetchall()
