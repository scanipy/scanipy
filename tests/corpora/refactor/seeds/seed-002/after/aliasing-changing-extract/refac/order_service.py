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
        box = [input001]
        _mutate(box)
        input001 = box[0]
        value001 = left001 + input001 + right001
        self.cursor.execute(value001)
        return self.cursor.fetchall()


def _mutate(box):
    box[0] = box[0] + "-alias"
