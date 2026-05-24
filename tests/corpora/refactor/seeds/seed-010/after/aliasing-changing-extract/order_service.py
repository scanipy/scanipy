"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id009):
        box = [user_id009]
        self._route(box)
        sql009 = "SELECT * FROM orders WHERE id = '" + user_id009 + "'"
        self.cursor.execute(sql009)
        return self.cursor.fetchall()

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
