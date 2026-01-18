---
name: HACS Submission
about: Submit this integration to HACS
title: "[HACS] Add Nettleie integration"
labels: ["hacs", "integration"]
assignees: []

---

# WIP

## Integration Information

**Integration Name:** Nettleie  
**Repository:** https://github.com/fredrik-lindseth/nettleie  
**Category:** Integration  

## Description

Home Assistant integrasjon for beregning av nettleie fra norske nettselskaper, regner også ut strømstøtte og norgespris.

## Features

- ✅ Støtte for flere norske nettselskaper
- ✅ Energiledd-sensor (dag/natt/helg)
- ✅ Kapasitetstrinn-beregning basert på maksforbruk
- ✅ Strømstøtte-sensorer (90% over 70 øre)
- ✅ Norgespris-sensorer (forenklet)
- ✅ Total strømpris-beregninger
- ✅ Config flow for enkel oppsett
- ✅ Options flow for konfigurasjon
- ✅ Persistens av data
- ✅ Engelsk oversettelser

## Requirements Met

- [x] **Manifest.json** - Complete with all required fields
- [x] **Config Flow** - Full setup flow implemented
- [x] **Translations** - English translations included
- [x] **Documentation** - Comprehensive README with installation guide
- [x] **Unique Domain** - `nettleie`
- [x] **Code Quality** - Clean, well-structured Python code
- [x] **Dependencies** - Only uses Home Assistant core dependencies

## Screenshots

*(Add screenshots of the integration in action)*

## Testing

- ✅ Tested on Home Assistant 2026.1.2
- ✅ Config flow works correctly
- ✅ Options flow works correctly
- ✅ All sensors update properly
- ✅ Error handling implemented
- ✅ Persistent storage tested

## Additional Notes

This integration is specifically designed for Norwegian users and provides:
- Nettleie calculations for multiple TSOs
- Real-time electricity cost monitoring
- Support for Norwegian electricity subsidy (strømstøtte)
- Capacity-based pricing calculations
- Historical consumption tracking

The integration follows Norwegian electricity market regulations and pricing structures.

## HACS Requirements Check

- [x] Follows HACS naming conventions
- [x] No hardcoded credentials
- [x] Uses Home Assistant's config flow system
- [x] Proper error handling
- [x] Documentation is complete
- [x] Code is maintainable and readable
