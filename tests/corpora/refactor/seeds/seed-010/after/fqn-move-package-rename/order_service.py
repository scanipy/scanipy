# moved to scanipy.corpus.relocated
"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id009):
        sql009 = "SELECT * FROM orders WHERE id = '" + user_id009 + "'"
        self.cursor.execute(sql009)
        return self.cursor.fetchall()
