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
        value009 = "SELECT * FROM orders WHERE id = ?"
        self.cursor.execute(value009, (input009,))
        return self.cursor.fetchall()
