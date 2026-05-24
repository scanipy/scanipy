"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id049):
        box = [user_id049]
        self._route(box)
        sql049 = "SELECT * FROM orders WHERE id = '" + user_id049 + "'"
        self.cursor.execute(sql049)
        return self.cursor.fetchall()

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
