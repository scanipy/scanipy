"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id009):
        sql009 = "SELECT * FROM orders WHERE id = %s"  # parameterized
        self.cursor.execute(sql009, (user_id009,))  # bound parameter
        return self.cursor.fetchall()
