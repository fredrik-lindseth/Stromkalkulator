"""Fasit og tidsbevisst hendelsesreplay for avregningen.

`fasit.py` regner forventet avregning rett fra hendelsene uten å røre
produksjonskoden. `harness.py` mater de samme hendelsene inn i den ekte
coordinatoren gjennom HAs state-maskin, med poll hvert minutt, jitter,
omstart og sommertid. Er de to uenige, er det coordinatoren som tar feil.

Kontrakten begge leser er `docs/kontrakter/avregning.md`.
"""
