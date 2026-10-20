import pathlib
import sqlite3
import tempfile
import unittest

from disaster_recovery import create_backup, integrity, restore_backup


class DisasterRecoveryAcceptance(unittest.TestCase):
    def test_real_isolated_corruption_and_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            live = root / "live.sqlite"
            db = sqlite3.connect(live)
            db.executescript("CREATE TABLE projects(id TEXT,name TEXT); CREATE TABLE experiences(id TEXT,lesson TEXT); CREATE TABLE decisions(id TEXT,choice TEXT); INSERT INTO projects VALUES('p1','Atlas Recovery'); INSERT INTO experiences VALUES('m1','Toujours vérifier le snapshot'); INSERT INTO decisions VALUES('d1','CONTINUE');")
            db.commit(); db.close()
            service = root / "atlas-control.service"; service.write_text("NoNewPrivileges=true\n", encoding="utf-8")
            workflow = root / "workflow.json"; workflow.write_text('{"id":"AtlasLocalReport001"}', encoding="utf-8")
            backup_dir = root / "backup"
            manifest = create_backup(live, [service, workflow], backup_dir)
            self.assertEqual(manifest["database_integrity"], "ok")
            live.write_bytes(b"INTENTIONALLY CORRUPTED TEST COPY")
            with self.assertRaises(sqlite3.DatabaseError):
                integrity(live)
            restored = restore_backup(backup_dir, root / "restored")
            self.assertEqual(integrity(restored), "ok")
            check = sqlite3.connect(restored)
            self.assertEqual(check.execute("SELECT name FROM projects").fetchone()[0], "Atlas Recovery")
            self.assertEqual(check.execute("SELECT lesson FROM experiences").fetchone()[0], "Toujours vérifier le snapshot")
            self.assertEqual(check.execute("SELECT choice FROM decisions").fetchone()[0], "CONTINUE")
            self.assertTrue((root / "restored/files/atlas-control.service").exists())
            self.assertTrue((root / "restored/files/workflow.json").exists())

    def test_tampered_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp); live = root / "live.sqlite"
            db = sqlite3.connect(live); db.execute("CREATE TABLE proof(value TEXT)"); db.commit(); db.close()
            create_backup(live, [], root / "backup")
            with (root / "backup/atlas.sqlite").open("ab") as stream: stream.write(b"tampered")
            with self.assertRaisesRegex(RuntimeError, "VERIFICATION"):
                restore_backup(root / "backup", root / "restored")


if __name__ == "__main__":
    unittest.main()
