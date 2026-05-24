"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id049):
        sql049 = "SELECT * FROM orders WHERE id = %s"  # parameterized
        self.cursor.execute(sql049, (user_id049,))  # bound parameter
        return self.cursor.fetchall()
