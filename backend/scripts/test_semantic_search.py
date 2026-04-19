"""
Tests for semantic_search.py.

Run (from repository root):
  python backend/scripts/test_semantic_search.py
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Keep imports working when run as a script
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Make sure config imports don't fail during test import
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("SB_URL", "https://example.supabase.co")
os.environ.setdefault("SB_SECRET_KEY", "test-supabase-key")

import backend.app.services.semantic_search as semantic_search


class TestSemanticSearch(unittest.TestCase):
    def test_validate_table_name_rejects_invalid(self):
        with self.assertRaises(ValueError):
            semantic_search._validate_table_name("not_a_table")

    def test_search_objects_calls_rpc(self):
        mock_supabase = MagicMock()
        mock_supabase.rpc.return_value.execute.return_value.data = [
            {"id": "a", "distance": 0.25},
        ]

        with patch.object(semantic_search, "create_query_embedding", return_value=[0.1, 0.2]) as mock_embed:
            results = semantic_search.search_objects(
                "American portraiture",
                limit=5,
                table="objects",
                supabase_client=mock_supabase,
            )

        mock_embed.assert_called_once_with("American portraiture", client=None)
        mock_supabase.rpc.assert_called_once_with(
            "match_objects",
            {
                "search_table": "objects",
                "query_embedding": [0.1, 0.2],
                "match_count": 5,
                "filter_floor_number": None,
                "filter_gallery_number": None,
            },
        )
        self.assertEqual(results[0]["id"], "a")
        self.assertIn("similarity", results[0])

    def test_get_related_objects_filters_source(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "source-object", "text_embedding": [0.1, 0.2]},
        ]

        with patch.object(
            semantic_search,
            "search_objects_by_embedding",
            return_value=[
                {"id": "source-object", "distance": 0.0},
                {"id": "neighbor-1", "distance": 0.2},
                {"id": "neighbor-2", "distance": 0.3},
            ],
        ):
            results = semantic_search.get_related_objects(
                "source-object",
                limit=2,
                table="objects",
                supabase_client=mock_supabase,
            )

        self.assertEqual([row["id"] for row in results], ["neighbor-1", "neighbor-2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
