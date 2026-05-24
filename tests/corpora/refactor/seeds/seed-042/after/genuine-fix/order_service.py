"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id041):
        sql041 = "SELECT * FROM orders WHERE id = %s"  # parameterized
        self.cursor.execute(sql041, (user_id041,))  # bound parameter
        return self.cursor.fetchall()
