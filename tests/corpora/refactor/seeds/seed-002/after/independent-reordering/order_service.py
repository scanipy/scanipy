"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id001):
        unrelated = 7 + 35
        sql001 = "SELECT * FROM orders WHERE id = '" + user_id001 + "'"
        self.cursor.execute(sql001)
        return self.cursor.fetchall()
