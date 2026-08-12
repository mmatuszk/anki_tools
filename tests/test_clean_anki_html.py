import unittest

from anki_tools.clean_anki_html import clean_html, collect_updates, deck_query


class CleanHtmlTests(unittest.TestCase):
    def test_removes_markup_and_decodes_entities(self) -> None:
        self.assertEqual(clean_html('<span class="x">你好&nbsp;&amp;</span>'), "你好 &amp;")

    def test_removes_non_visible_content(self) -> None:
        self.assertEqual(clean_html("汉<script>alert(1)</script>字<style>x</style>"), "汉字")

    def test_is_idempotent(self) -> None:
        once = clean_html("A &amp; B &lt;3")
        self.assertEqual(clean_html(once), once)

    def test_deck_query_quotes_special_characters(self) -> None:
        self.assertEqual(deck_query('A "quoted" deck'), 'deck:"A \\"quoted\\" deck"')

    def test_collects_only_changed_fields(self) -> None:
        notes = [
            {"noteId": 1, "fields": {"Hanzi": {"value": "<b>你</b>"}}},
            {"noteId": 2, "fields": {"Hanzi": {"value": "好"}}},
            {"noteId": 3, "fields": {}},
        ]
        updates, missing = collect_updates(notes, ["Hanzi"])
        self.assertEqual(updates[0][0:2], (1, {"Hanzi": "你"}))
        self.assertEqual(len(updates), 1)
        self.assertEqual(missing, {"Hanzi": 1})


if __name__ == "__main__":
    unittest.main()
