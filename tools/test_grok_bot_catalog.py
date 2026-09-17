"""Data and conversion regression checks for the Grok bot firmware."""

from __future__ import annotations

import hashlib
import json
import unittest

from generate_grok_bot_catalog import AVATAR_ID, OUTPUT, SEQUENCES, SOURCE, render


class GrokBotCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_bytes = SOURCE.read_bytes()
        cls.document = json.loads(cls.source_bytes)

    def test_user_export_is_pinned(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.source_bytes).hexdigest(),
            "6004c77de75918eb9e5a0d71f2780b9285cd3d7b5e70ce92d1bb74305c499125",
        )
        self.assertEqual(self.document["library"]["activeAvatarId"], AVATAR_ID)

    def test_every_sequence_uses_known_expressions(self) -> None:
        expressions = {item["id"] for item in self.document["expressions"]}
        sequences = {item["id"]: item for item in self.document["sequences"]}
        self.assertEqual(len(expressions), 27)
        self.assertEqual(set(sequences), set(SEQUENCES))
        self.assertEqual(len(SEQUENCES), 23)
        for sequence in sequences.values():
            self.assertTrue(sequence["steps"])
            for step in sequence["steps"]:
                self.assertIn(step["expressionId"], expressions)
                self.assertGreaterEqual(step["transitionMs"], 0)
                self.assertGreaterEqual(step["holdMs"], 0)

    def test_checked_in_catalog_matches_source(self) -> None:
        self.assertEqual(OUTPUT.read_text(encoding="utf-8"), render(self.source_bytes))
        self.assertEqual(render(self.source_bytes).count("const AvatarEngine::Keyframe kBotFrames"), 23)

    def test_only_idle_persists_by_default(self) -> None:
        catalog = render(self.source_bytes)
        specs = catalog.split("const AvatarEngine::ExpressionSpec kExpressions[] = {", 1)[1]
        entries = [line.strip() for line in specs.splitlines() if line.strip().startswith('{"')]
        self.assertEqual(len(entries), 23)
        self.assertTrue(entries[0].startswith('{"IDLE",'))
        self.assertTrue(entries[0].endswith('kBotNoMotion, true},'))
        self.assertTrue(all(line.endswith('kBotNoMotion, false},') for line in entries[1:]))


if __name__ == "__main__":
    unittest.main()
