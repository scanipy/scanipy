"""Synthetic injection fixture; never execute during corpus validation."""

import sqlite3


class OrderService:
    def __init__(self, cursor: sqlite3.Cursor):
        self.cursor = cursor

    def lookup(self, input001):
        if type(input001) is not str:
            raise TypeError("exact str required")
        left001 = "SELECT * FROM orders WHERE id = '"
        right001 = "'"
        partial = left001 + input001
        value001 = partial + right001
        self.cursor.execute(value001)
        secondary = "archived-" + input001
        second_partial = left001 + secondary
        second_value = second_partial + right001
        self.cursor.execute(second_value)
        return self.cursor.fetchall()
