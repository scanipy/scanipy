"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id001):
        box = [user_id001]
        self._route(box)
        sql001 = "SELECT * FROM orders WHERE id = '" + user_id001 + "'"
        self.cursor.execute(sql001)
        return self.cursor.fetchall()

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
