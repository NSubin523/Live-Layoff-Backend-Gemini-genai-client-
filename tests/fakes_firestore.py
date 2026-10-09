"""In-memory Firestore subset for repository tests; no SDK/network calls."""
from copy import deepcopy


class Snapshot:
    def __init__(self, document_id, data):
        self.id, self.data = document_id, deepcopy(data)

    def to_dict(self):
        return deepcopy(self.data)


class Query:
    def __init__(self, db, path, filters=(), ordering=None, count=None, fields=None):
        self.db, self.path = db, path
        self.filters, self.ordering, self.count, self.fields = filters, ordering, count, fields

    def _with(self, **changes):
        args = dict(db=self.db, path=self.path, filters=self.filters,
                    ordering=self.ordering, count=self.count, fields=self.fields)
        return Query(**(args | changes))

    def where(self, *, filter):
        return self._with(filters=self.filters + (filter,))

    def order_by(self, field, direction):
        return self._with(ordering=(field, direction))

    def limit(self, count):
        return self._with(count=count)

    def select(self, fields):
        return self._with(fields=fields)

    def get(self):
        rows = list(self.db.rows.get(self.path, {}).items())
        for condition in self.filters:
            def matches(row):
                value = row[1].get(condition.field_path)
                if value is None:
                    return False
                if condition.op_string == '==':
                    return value == condition.value
                if condition.op_string == '<':
                    return value < condition.value
                if condition.op_string == '>=':
                    return value >= condition.value
                raise AssertionError(f'Unsupported filter {condition.op_string}')
            rows = [row for row in rows if matches(row)]
        if self.ordering:
            field, direction = self.ordering
            rows = [row for row in rows if field in row[1]]
            rows.sort(key=lambda row: row[1][field], reverse=direction == 'DESCENDING')
        if self.count is not None:
            rows = rows[:self.count]
        return [Snapshot(key, {k: v for k, v in data.items() if k in self.fields}
                         if self.fields is not None else data) for key, data in rows]

    def stream(self):
        return iter(self.get())


class Collection(Query):
    def document(self, document_id=None):
        if document_id is None:
            self.db.sequence += 1
            document_id = f'generated-{self.db.sequence}'
        return Document(self.db, self.path, document_id)


class Document:
    def __init__(self, db, path, document_id):
        self.db, self.path, self.id = db, path, document_id

    def collection(self, name):
        return Collection(self.db, f'{self.path}/{self.id}/{name}')

    def set(self, data):
        self.db.rows.setdefault(self.path, {})[self.id] = deepcopy(data)

    def update(self, data):
        self.db.rows[self.path][self.id].update(deepcopy(data))


class Firestore:
    def __init__(self, rows=None):
        self.rows, self.sequence = deepcopy(rows or {}), 0

    def collection(self, name):
        return Collection(self, name)
