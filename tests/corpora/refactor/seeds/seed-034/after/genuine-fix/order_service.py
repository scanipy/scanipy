"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id033):
        sql033 = "SELECT * FROM orders WHERE id = %s"  # parameterized
        self.cursor.execute(sql033, (user_id033,))  # bound parameter
        return self.cursor.fetchall()
