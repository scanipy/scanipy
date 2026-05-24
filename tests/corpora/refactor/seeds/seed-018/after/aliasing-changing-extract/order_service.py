"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id017):
        box = [user_id017]
        self._route(box)
        sql017 = "SELECT * FROM orders WHERE id = '" + user_id017 + "'"
        self.cursor.execute(sql017)
        return self.cursor.fetchall()

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
