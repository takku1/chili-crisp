"""Reproduce the retained archive candidate against its pinned source boundary."""


def rewrite(text):
    original = '        data = [rec.to_dict() for rec in self._records.values()]'
    if text.count(original) != 1:
        raise ValueError('Archive does not match reviewed serialization boundary')
    replacement = '''        records = self._records

        class RecordStream(list):
            # json.dump iterates list subclasses lazily. Preserve its exact
            # array formatting while materializing only one record at a time.
            def __len__(self):
                return len(records)

            def __iter__(self):
                return (record.to_dict() for record in records.values())

        data = RecordStream()'''
    return text.replace(original, replacement)
