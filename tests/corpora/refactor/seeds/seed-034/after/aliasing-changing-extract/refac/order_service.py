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
        box = [input033]
        _mutate(box)
        input033 = box[0]
        value033 = left033 + input033 + right033
        self.cursor.execute(value033)
        return self.cursor.fetchall()


def _mutate(box):
    box[0] = box[0] + "-alias"
