"""Obligatoriske fakturacaser, uavhengig av hvilke tester pytest finner.

Endring av måned/dekning må oppdateres her sammen med fasit og tester.
Inventaret importerer ikke replayfilenes parametre: en slettet parameter skal
gi en manglende case, ikke et mindre grønt inventar.
"""

LEGACY_MONTHS = ("februar", "mars", "april", "mai", "juni", "juli", "august", "september")
SETTLEMENT_MONTHS = ("mai_2026", "juni_2026", "juli_2026", "august_2026", "september_2026", "oktober_2026")
LEGACY_CHECKS = (
    "total_kwh_matcher_faktura",
    "dag_natt_split_matcher_faktura",
    "norgespris_compensation_matcher_faktura",
    "topp_3_kapasitet_matcher_faktura",
    "kapasitetsledd_matcher_faktura",
)
INVOICE_CHECKS = (
    "energi_dag_natt_og_total",
    "energiledd_dag_og_natt",
    "avgifter",
    "norgespris",
    "fastledd",
    "nettleie_totalt",
    "alle_intervaller_har_full_prisdekning",
)
COORDINATOR_CHECKS = ("energi_total", "energi_dag_natt", "energiledd_og_avgifter", "norgespris", "fastledd")


def required_cases() -> dict[str, tuple[str, ...]]:
    """Node-ID → månedene casen må registrere numerisk evidens for."""
    old = "tests/test_coordinator_replay.py"
    new = "tests/test_replay_hendelser.py"
    cases = {
        f"{old}::TestReplayParametrized::test_{check}[{month}]": (f"{month}_2026",)
        for month in LEGACY_MONTHS
        for check in LEGACY_CHECKS
    }
    december_checks = (
        *(c for c in LEGACY_CHECKS if not c.startswith("norgespris")),
        "dag_natt_split_med_jul_nyttar_aften_helligdager",
    )
    cases.update({f"{old}::TestReplayDesember2025::test_{c}": ("desember_2025",) for c in december_checks})
    for cls, checks in (
        ("TestFasitMotFaktura", INVOICE_CHECKS),
        ("TestFakturaavstemmingGjennomCoordinator", COORDINATOR_CHECKS),
    ):
        cases.update({f"{new}::{cls}::test_{c}[{m}]": (m,) for m in SETTLEMENT_MONTHS for c in checks})
    cases[f"{new}::test_coordinatoren_treffer_fasiten"] = SETTLEMENT_MONTHS
    return cases
