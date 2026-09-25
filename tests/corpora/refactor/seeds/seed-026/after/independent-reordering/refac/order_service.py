"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, input025):
        if type(input025) is not str:
            raise TypeError("exact str required")
        right025 = "'"
        left025 = "SELECT * FROM orders WHERE id = '"
        value025 = left025 + input025 + right025
        self.cursor.execute(value025)
        return self.cursor.fetchall()
