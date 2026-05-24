"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id025):
        sql025 = "SELECT * FROM orders WHERE id = %s"  # parameterized
        self.cursor.execute(sql025, (user_id025,))  # bound parameter
        return self.cursor.fetchall()
