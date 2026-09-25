# formatting only

"""Synthetic injection fixture; never execute during corpus validation."""



import sqlite3





class OrderService:

    def __init__(self, cursor: sqlite3.Cursor):

        self.cursor = cursor



    def lookup(self, input049):

        if type(input049) is not str:

            raise TypeError("exact str required")

        left049 = "SELECT * FROM orders WHERE id = '"

        right049 = "'"

        value049 = left049 + input049 + right049

        self.cursor.execute(value049)

        return self.cursor.fetchall()
