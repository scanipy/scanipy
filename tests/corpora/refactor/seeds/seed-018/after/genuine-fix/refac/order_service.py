"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, input017):
        if type(input017) is not str:
            raise TypeError("exact str required")
        left017 = "SELECT * FROM orders WHERE id = '"
        right017 = "'"
        value017 = "SELECT * FROM orders WHERE id = ?"
        self.cursor.execute(value017, (input017,))
        return self.cursor.fetchall()
