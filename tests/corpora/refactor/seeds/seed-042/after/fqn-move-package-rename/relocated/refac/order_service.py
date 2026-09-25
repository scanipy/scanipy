"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, input041):
        if type(input041) is not str:
            raise TypeError("exact str required")
        left041 = "SELECT * FROM orders WHERE id = '"
        right041 = "'"
        value041 = left041 + input041 + right041
        self.cursor.execute(value041)
        return self.cursor.fetchall()
