"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id001):
        sql001 = "SELECT * FROM orders WHERE id = %s"  # parameterized
        self.cursor.execute(sql001, (user_id001,))  # bound parameter
        return self.cursor.fetchall()
