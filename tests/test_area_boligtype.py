"""Areas hyttefastledd gjelder alle tre områder uavhengig av støttevilkår."""

import pytest
from stromkalkulator.dso import DSO_LIST, hent_kapasitetstrinn

from tests.conftest import _make_entry, _make_hass

OMRADER = ["area_nett_omrade1", "area_nett_omrade2", "area_nett_omrade3"]
HYTTETRINN = [(2, 578), (5, 667), (10, 731), (15, 1016), (20, 1143), (25, 1143), (float("inf"), 1143)]


@pytest.mark.parametrize("dso", OMRADER)
@pytest.mark.parametrize("boligtype", ["fritidsbolig", "fritidsbolig_fast"])
def test_area_velger_pdfens_hyttefastledd(coord_module, dso, boligtype):
    coord = coord_module.NettleieCoordinator(
        _make_hass(), _make_entry(dso_id=dso, extra_data={"boligtype": boligtype})
    )
    assert coord.kapasitetstrinn == HYTTETRINN
    for kw, pris in [
        (1.9, 578),
        (4.9, 667),
        (9.9, 731),
        (14.9, 1016),
        (19.9, 1143),
        (24.9, 1143),
        (99, 1143),
    ]:
        assert coord._get_kapasitetsledd(kw)[0] == pris


@pytest.mark.parametrize("dso,forste_pris", zip(OMRADER, [525, 390, 358], strict=True))
def test_bolig_og_sesongperioder_beholdes(coord_module, dso, forste_pris):
    entry = _make_entry(dso_id=dso, extra_data={"boligtype": "bolig"})
    bolig = coord_module.NettleieCoordinator(_make_hass(), entry)
    assert bolig._get_kapasitetsledd(1.9)[0] == forste_pris
    entry.data = {**entry.data, "boligtype": "fritidsbolig"}
    hytte = coord_module.NettleieCoordinator(bolig.hass, entry)
    assert hytte._get_kapasitetsledd(1.9)[0] == 578
    # Sesonggrenser og område 3-hytteenergiledd avventer kildeavklaring.
    assert hytte._energiledd_perioder_eks == bolig._energiledd_perioder_eks
    assert hent_kapasitetstrinn(DSO_LIST[dso], "bolig") == DSO_LIST[dso]["kapasitetstrinn"]
