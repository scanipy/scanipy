"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id017):
        sql017 = "SELECT * FROM orders WHERE id = %s"  # parameterized
        self.cursor.execute(sql017, (user_id017,))  # bound parameter
        return self.cursor.fetchall()
