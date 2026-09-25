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
        box = [input009]
        _mutate(box)
        input009 = box[0]
        value009 = left009 + input009 + right009
        self.cursor.execute(value009)
        return self.cursor.fetchall()


def _mutate(box):
    box[0] = box[0] + "-alias"
