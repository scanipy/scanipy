"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id017):
        sql017 = "SELECT * FROM orders WHERE id = '" + user_id017 + "'"
        self.cursor.execute(sql017)
        return self.cursor.fetchall()
