"""Order lookup service (seeded SQL injection)."""


class OrderService:
    def __init__(self, cursor):
        self.cursor = cursor

    def lookup(self, user_id041):
        box = [user_id041]
        self._route(box)
        sql041 = "SELECT * FROM orders WHERE id = '" + user_id041 + "'"
        self.cursor.execute(sql041)
        return self.cursor.fetchall()

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
