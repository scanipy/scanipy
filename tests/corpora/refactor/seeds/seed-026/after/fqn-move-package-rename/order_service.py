# moved to scanipy.corpus.relocated
"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id025):
        sql025 = "SELECT * FROM orders WHERE id = '" + user_id025 + "'"
        self.cursor.execute(sql025)
        return self.cursor.fetchall()
