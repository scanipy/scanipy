"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id033):
        box = [user_id033]
        self._route(box)
        sql033 = "SELECT * FROM orders WHERE id = '" + user_id033 + "'"
        self.cursor.execute(sql033)
        return self.cursor.fetchall()

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
