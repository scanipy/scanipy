"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id041):
        unrelated = 7 + 35
        sql041 = "SELECT * FROM orders WHERE id = '" + user_id041 + "'"
        self.cursor.execute(sql041)
        return self.cursor.fetchall()
