"""Offline contracts for testlab isolation, fixture provenance and failure cleanup.

Run without HA/pytest: python3 -m unittest discover -s tests_e2e -p 'test_*.py'.
These checks never start Docker; they are not the container scenarios.
"""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import fixture
import run


class FixtureTests(unittest.TestCase):
    def test_june_matches_independent_invoice_reference(self):
        data = fixture.load_fixture()
        report = fixture.reconcile_june(data)
        self.assertTrue(report["verified"])
        self.assertAlmostEqual(report["actual"]["total_kwh"], 1033.626, places=3)

    def test_fixture_export_discards_all_source_metadata(self):
        data = fixture.load_fixture()
        self.assertEqual(set(data), {"name", "hours"})
        self.assertTrue(all(set(row) == set(fixture.FIELDS) for row in data["hours"]))
        serialized = json.dumps(data)
        for private in ("fakturanr", "pow_u_ams", "tpi_start", "kilde_forbruk"):
            self.assertNotIn(private, serialized)

    def test_arbitrary_and_private_paths_are_rejected(self):
        for name in ("../../_private/Måleverdier/data", "/tmp/data.json", "juni_2026.json"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                fixture.load_fixture(name)

    def test_partial_month_is_not_an_invoice_pass(self):
        data = fixture.load_fixture()
        data["hours"].pop()
        with self.assertRaises(ValueError):
            fixture.reconcile_june(data)

    def test_changed_consumption_fails_reference(self):
        data = fixture.load_fixture()
        data["hours"][0]["kwh"] += 1
        with self.assertRaises(AssertionError):
            fixture.reconcile_june(data)

    def test_other_months_do_not_claim_verified_reference(self):
        data = fixture.load_fixture("juli_2026")
        self.assertFalse(fixture.reconcile_june(data)["verified"])


class IsolationTests(unittest.TestCase):
    def test_compose_has_only_loopback_and_explicit_readonly_mounts(self):
        text = (run.HERE / "compose.yaml").read_text()
        self.assertIn("127.0.0.1:${E2E_PORT:-0}:8123", text)
        self.assertIn(run.IMAGE, text)
        self.assertIn("platform: linux/amd64", text)
        for forbidden in ("network_mode: host", "privileged: true", "/var/run/docker.sock", "_private/"):
            self.assertNotIn(forbidden, text)

    def test_refuses_foreign_or_moved_lab(self):
        with tempfile.TemporaryDirectory(prefix="e2e-contract-") as temporary:
            directory = Path(temporary).resolve()
            good = {
                "marker": run.MARKER,
                "project": "strom-e2e-0123456789ab",
                "directory": str(directory),
                "port": 0,
            }
            for field, value in (("marker", "other"), ("project", "production"), ("directory", "/tmp/other")):
                bad = copy.copy(good)
                bad[field] = value
                (directory / "lab.json").write_text(json.dumps(bad))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    run.Lab(directory)
            (directory / "lab.json").write_text(json.dumps(good))
            self.assertEqual(run.Lab(directory).project, good["project"])

    def test_secrets_redacted_from_logs(self):
        text = (
            'Authorization: Bearer abc.def.xyz\n{"password": "secret", "access_token": "a123", '
            '"refresh_token": "r123", "auth_code": "c123"}\ncustom secret-token'
        )
        redacted = run.redact(text, ("secret-token",))
        for value in ("abc.def.xyz", '"secret"', "a123", "r123", "c123", "secret-token"):
            self.assertNotIn(value, redacted)

    def test_forced_failure_always_collects_evidence_and_down(self):
        # Argumentene bygges av den ekte parseren. En håndskrevet Namespace
        # slutter i stillhet å dekke en ny sjekk i main().
        args = run.parser().parse_args(["run", "--force-failure"])
        lab = MagicMock()
        with (
            patch.object(run, "parser") as parser,
            patch.object(run, "prepare", return_value=lab),
            patch.object(run, "lifecycle") as lifecycle,
        ):
            parser.return_value.parse_args.return_value = args
            self.assertEqual(run.main(), 1)
        lifecycle.assert_not_called()
        lab.evidence.assert_called_once()
        lab.down.assert_called_once()

    def _lab(self, directory):
        (directory / "lab.json").write_text(
            json.dumps(
                {
                    "marker": run.MARKER,
                    "project": "strom-e2e-0123456789ab",
                    "directory": str(directory),
                    "port": 0,
                }
            )
        )
        (directory / "config/.storage").mkdir(parents=True)
        return run.Lab(directory)

    def test_seeding_refuses_keys_the_release_never_wrote(self):
        # Vakten mot å finne opp et lagringsformat: en seedet nøkkel som ikke
        # sto i filen fra før beviser ingenting om hva utgaven faktisk skrev.
        with tempfile.TemporaryDirectory(prefix="e2e-contract-") as temporary:
            lab = self._lab(Path(temporary).resolve())
            lab.lagring("abc").write_text(json.dumps({"version": 1, "data": {"monthly_cost": 1.0}}))
            with self.assertRaises(ValueError):
                lab.skriv_lagring("abc", {"paafunnet_nokkel": 1})
            lab.skriv_lagring("abc", {"monthly_cost": 2.0})
            self.assertEqual(json.loads(lab.lagring("abc").read_text())["data"]["monthly_cost"], 2.0)

    def test_entry_data_only_touches_the_named_entry(self):
        with tempfile.TemporaryDirectory(prefix="e2e-contract-") as temporary:
            lab = self._lab(Path(temporary).resolve())
            fil = lab.directory / "config/.storage/core.config_entries"
            fil.write_text(
                json.dumps(
                    {
                        "data": {
                            "entries": [
                                {"entry_id": "aaa", "data": {"tso": "bkk"}},
                                {"entry_id": "bbb", "data": {"tso": "elvia"}},
                            ]
                        }
                    }
                )
            )
            lab.entry_data("aaa", {"tariffmodus": "legacy_unconfirmed"})
            entries = {row["entry_id"]: row["data"] for row in json.loads(fil.read_text())["data"]["entries"]}
            self.assertEqual(entries["aaa"], {"tso": "bkk", "tariffmodus": "legacy_unconfirmed"})
            self.assertEqual(entries["bbb"], {"tso": "elvia"})
            with self.assertRaises(ValueError):
                lab.entry_data("ccc", {"tso": "bkk"})

    def test_upgrade_starts_from_a_released_tag(self):
        # Oppgraderingsveien skal starte på det brukerne har installert. Peker
        # default-en på en SHA som ikke er sluppet, tester den ingen sin vei.
        self.assertEqual(run.parser().parse_args(["upgrade"]).fra, run.SLUPPET)
        self.assertIn(run.SLUPPET, run.command(["git", "tag", "--list", run.SLUPPET]).split())

    def test_evidence_failure_still_stops_container(self):
        args = run.parser().parse_args(["run"])
        lab = MagicMock()
        lab.evidence.side_effect = OSError("disk full")
        with (
            patch.object(run, "parser") as parser,
            patch.object(run, "prepare", return_value=lab),
            patch.object(run, "lifecycle"),
        ):
            parser.return_value.parse_args.return_value = args
            with self.assertRaises(OSError):
                run.main()
        lab.down.assert_called_once()


if __name__ == "__main__":
    unittest.main()
