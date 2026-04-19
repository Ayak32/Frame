"""
Tests for generate_embeddings.py.

How to be confident before running the real script:
  1. Run these tests (with venv activated): cd Project && python backend/scripts/test_generate_embeddings.py
  2. Dry run: python backend/scripts/generate_embeddings.py --table on_view --dry-run --no-skip-existing
  3. Real run on 1 object: python backend/scripts/generate_embeddings.py --table on_view --limit 1 --no-skip-existing
     Then check in Supabase that one row has text_embedding set.

Run tests:
  cd Project && python backend/scripts/test_generate_embeddings.py
  or: cd Project && python -m pytest backend/scripts/test_generate_embeddings.py -v
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Project root on path (same as generate_embeddings)
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _mock_one_object_row():
    return [{
        "id": "https://example.org/obj/1",
        "title": "Test",
        "creator_id": None,
        "creator_name": "Artist",
        "classification": ["Painting"],
        "culture": None,
        "period": None,
        "materials": None,
        "linked_art_json": {},
        "audio_guide_url": None,
        "audio_guide_transcript": None,
        "dimensions_text": None,
        "provenance_text": None,
        "credit_line": None,
    }]


class TestGenerateEmbeddings(unittest.TestCase):
    def test_count_tokens_approx(self):
        """Token approximation is positive and scales with length."""
        import backend.scripts.generate_embeddings as gen
        self.assertGreaterEqual(gen.count_tokens_approx(""), 1)
        self.assertGreaterEqual(gen.count_tokens_approx("hello"), 1)
        self.assertEqual(gen.count_tokens_approx("x" * 400), 100)
        self.assertEqual(gen.count_tokens_approx("x" * 800), 200)

    def test_select_columns(self):
        """Correct columns per table (on_view has dimensions_text)."""
        import backend.scripts.generate_embeddings as gen
        on_view = gen._select_columns("objects")
        self.assertIn("dimensions_text", on_view)
        self.assertNotIn("curatorial_text", on_view)
        self.assertIn("id", on_view)
        self.assertIn("title", on_view)

    def test_get_embeddings_preserves_order(self):
        """Returned embeddings match input order (by index)."""
        import backend.scripts.generate_embeddings as gen
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value.data = [
            MagicMock(index=1, embedding=[0.1] * 1536),
            MagicMock(index=0, embedding=[0.2] * 1536),
        ]
        result = gen.get_embeddings(mock_client, ["text1", "text2"])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], [0.2] * 1536)
        self.assertEqual(result[1], [0.1] * 1536)
        mock_client.embeddings.create.assert_called_once()

    def test_build_texts_for_objects_fallback(self):
        """When builder returns empty, fallback to title or id."""
        import backend.scripts.generate_embeddings as gen
        mock_supabase = MagicMock()
        objects = [
            {"id": "https://example.org/obj/1", "title": "A Painting", "creator_id": None},
        ]
        with patch.object(gen, "build_embedding_text_on_view", return_value=""):
            pairs = gen.build_texts_for_objects(objects, "objects", mock_supabase, include_external=False)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][0], "https://example.org/obj/1")
        self.assertEqual(pairs[0][1], "A Painting")

    def test_dry_run_does_not_call_openai(self):
        """With dry_run=True, OpenAI is never called and DB is not updated."""
        import backend.scripts.generate_embeddings as gen
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.range.return_value.execute.return_value.data = _mock_one_object_row()
        mock_openai = MagicMock()
        gen.run_table(
            "objects",
            mock_supabase,
            mock_openai,
            limit=1,
            skip_existing=False,
            dry_run=True,
            include_external=False,
        )
        mock_openai.embeddings.create.assert_not_called()
        mock_supabase.table.return_value.update.assert_not_called()

    def test_real_run_one_object_calls_openai_and_update(self):
        """With dry_run=False and one object, OpenAI is called and update is called (mocked)."""
        import backend.scripts.generate_embeddings as gen
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.range.return_value.execute.return_value.data = _mock_one_object_row()
        mock_openai = MagicMock()
        mock_openai.embeddings.create.return_value.data = [
            MagicMock(index=0, embedding=[0.01] * 1536),
        ]
        gen.run_table(
            "objects",
            mock_supabase,
            mock_openai,
            limit=1,
            skip_existing=False,
            dry_run=False,
            include_external=False,
        )
        mock_openai.embeddings.create.assert_called_once()
        update_chain = mock_supabase.table.return_value.update.return_value.eq.return_value.execute
        self.assertTrue(update_chain.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
