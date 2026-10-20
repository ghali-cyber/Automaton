import hashlib
import json
import pathlib
import tempfile
import unittest

import generator


class GenericGeneratorAcceptance(unittest.TestCase):
    CASES = {
        "mini-commerce": "Créer une boutique locale avec catalogue, panier et commandes",
        "crm": "Créer un CRM local avec prospects et pipeline commercial",
        "ai-productivity": "Créer un assistant IA de productivité qui résume des notes",
    }

    def test_three_categories_are_distinct_and_isolated(self):
        rendered = {}
        with tempfile.TemporaryDirectory() as root:
            root = pathlib.Path(root)
            for index, (kind, idea) in enumerate(self.CASES.items()):
                pid = f"project-{index}"
                spec = generator.build_specification(idea)
                self.assertEqual(spec["application_type"], kind)
                files = generator.build_files(spec, pid, "1.0.0")
                folder = root / pid / "versions" / "v1.0.0"
                folder.mkdir(parents=True)
                for name, content in files.items():
                    (folder / name).write_text(content, encoding="utf-8")
                joined = "\n".join(files.values())
                self.assertIn(f"atlas:{pid}:v1.0.0:{kind}", files["prototype.js"])
                self.assertNotIn("QueuePilot", joined)
                self.assertNotIn("Musea", joined)
                rendered[kind] = hashlib.sha256(joined.encode()).hexdigest()
            self.assertEqual(len(set(rendered.values())), 3)

    def test_minor_version_preserves_previous_version(self):
        spec = generator.build_specification(self.CASES["crm"])
        with tempfile.TemporaryDirectory() as root:
            root = pathlib.Path(root)
            manifests = []
            for version in ("1.0.0", generator.bump_version("1.0.0", "minor")):
                folder = root / "crm-project" / "versions" / f"v{version}"
                folder.mkdir(parents=True)
                files = generator.build_files(spec, "crm-project", version)
                for name, content in files.items():
                    (folder / name).write_text(content, encoding="utf-8")
                manifest = {"project_id": "crm-project", "version": version, "files": sorted(files)}
                (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                manifests.append(folder / "manifest.json")
            self.assertTrue(all(path.exists() for path in manifests))
            self.assertEqual(json.loads(manifests[0].read_text())["version"], "1.0.0")
            self.assertEqual(json.loads(manifests[1].read_text())["version"], "1.1.0")


if __name__ == "__main__":
    unittest.main()
