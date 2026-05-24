"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, renamed1):
        renamed0 = "SELECT * FROM orders WHERE id = '" + renamed1 + "'"
        self.cursor.execute(renamed0)
        return self.cursor.fetchall()
