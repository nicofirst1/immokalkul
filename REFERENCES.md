# References

Sources consulted to build the German property rules encoded in this tool. Grouped by topic, ranked by authority at the bottom. Each entry below is a source actually fetched during the research phase — not a memorized or inferred reference.

For legal references inside the code (`immokalkul/rules_de.py`), we cite the canonical legal sections (§ 7 EStG, § 6 EStG, § 19 WEG, § 28 II. BV) rather than the URLs here, because the legal sections are authoritative. The sources below are where the interpretations of those sections were verified.

---

## AfA (depreciation)

- **Finanzamt NRW — So ermitteln Sie die Abschreibung für Ihr Vermietungsobjekt** — most authoritative (official NRW tax authority). Confirms 2.5% pre-1925, 2% 1925–2022, 3% from 2023. Covers which purchase fees are capitalizable into AfA basis. URL: https://www.finanzamt.nrw.de/steuerinfos/privatpersonen/haus-und-grund/so-ermitteln-sie-die-abschreibung-fuer-ihr
- **Lohnsteuer Kompakt — AfA für Gebäude (linear/degressiv)** — covers § 7 Abs. 4 and Abs. 5 EStG distinctions, Sonderabschreibung § 7b.
- **Nutzungsdauer.com — AfA-Rechner** — includes the useful example of a €440k depreciable base on a €500k purchase (builds intuition for land/building split).
- **Rosepartner — AfA Abschreibung Immobilien** — from a tax law firm. Covers Denkmal-AfA (§ 7i, § 10f EStG) with the 9%/7% scheme.
- **Immowelt — Altbau-AfA Beispielrechnung** — where the Anschaffungsnaher Aufwand rule (15% / 3 years) was confirmed.
- **Pandotax — Abschreibung Immobilien** — from a Steuerberatung; confirms BFH ruling IX R 6/16 (9.5.2017) on damage-after-purchase repairs.
- **Hypofriend — AfA bei Immobilien 2025** — covers the 2022 Jahressteuergesetz changes.
- **LPE Immobilien — AfA erklärt** — simpler explainer.
- **Certa Gutachten — Abschreibung** — has the useful breakdown of the 4% rule for 1985–2000 builds (legacy cases).
- **Schiffer Immobilien — Denkmal-AfA** — Denkmal-AfA specifics (relevant if a building turns out to be listed).

## Petersche Formel and maintenance reserve

- **Wikipedia — Peterssche Formel** — canonical reference with derivation and the 65–70% WEG split. URL: https://de.wikipedia.org/wiki/Peterssche_Formel
- **Wüstenrot — Instandhaltungsrücklage Berechnung** — includes the age-based table from II. Berechnungsverordnung.
- **Techem — Instandhaltungsrücklage berechnen** — pragmatic view including the €1/m²/month rule-of-thumb for new builds.
- **Beste Hausverwaltung — Instandhaltungsrücklage 2026** — most current rates found (2026).
- **Homeday — Instandhaltungsrücklage** — WEG-Reform 2020 nomenclature change (Erhaltungsrücklage vs. Instandhaltungsrücklage).
- **Interhyp — Instandhaltungskosten berechnen** — has the 1–1.5% of building value rule used for houses.
- **Opacta — Instandhaltungsrücklage Rechner** — VPB (Verband Privater Bauherren) recommendations.
- **Heid Immobilienbewertung — Instandhaltungsrücklage** — reference to § 28 Abs. 2 II. BV values.
- **Effi — Instandhaltungsrücklage Eigentumswohnung** — layperson-friendly version.
- **Sanier.de — Rechner Instandhaltungsrücklage** — interactive calculator for reality-checking results.

## Component lifecycles and renovation costs

- **Sparkasse — Wann sollte man sanieren?** — overview of which components need replacing when, and the GEG heating-replacement rule (> 30 yr).
- **Sparkasse Witten — So lange hält ein Haus** — specific lifetime numbers for windows, doors, roof.
- **Raiffeisen — Lebenszyklus Immobilien** — Swiss source but uses the same paritätische Lebensdauertabelle (HEV/MV).
- **Effizienzhaus-online — Wenn Häuser in die Jahre kommen** — Sanierungspflicht details (EnEV triggers at ownership change).
- **Schwäbisch Hall — Renovierungskosten-Rechner** — sources BKI (Baukosteninformationszentrum) Q4 2025 price data.
- **Hausinfo.ch — Lebensdauer Bauteile** — Swiss reference tables.
- **Baumensch — Wie lange hält ein Haus** — the €20/m²/yr rule of thumb used here.
- **Baumensch — Lebensdauer Bauteile** — component-specific lifetime table.
- **Berger Immobilienbewertung — Lebensdauer** — valuation-firm perspective.
- **Bal Heizung — Kosten Altbausanierung 2025** — €400–1,200/m² range for Kernsanierung, used as the capex scaling.

## Bodenrichtwert (Bonn specifically)

- **BORIS NRW** — official Bodenrichtwert information system for NRW. Authoritative source, free access, no registration. URL: https://www.boris.nrw.de/
- **Gutachterausschuss Bonn — BORIS Plus** — Bonn-specific portal with map view.
- **Gutachterausschuss Bonn — Bodenrichtwertkarte** — the official explainer of what a Bodenrichtwert is.
- **Bodenrichtwert-Bonn.de** — private aggregator with the Poppelsdorf €1,000–1,600/m² figure used in the sample YAML. Cross-verify with BORIS NRW before trusting.
- **BorisPortal — Bonn** — another private portal; has the 2025 market report summary (Mehrfamilienhaus values: €910/m² in good Bonn locations).
- **Bodenrichtwerte-Deutschland — NRW** — comparative view (Düsseldorf €1,147 vs. Köln €1,088 vs. Bonn €618 /m²).
- **Bodenrichtwerte-Deutschland — Bonn 2024** — Bonn 2024 detail (Bad Godesberg €656/m² average; Stadtbezirk extremes €305–10,500/m²).
- **Bodenrichtwerte-Deutschland — Bonn 2026** — 2025 value of €619/m² Bonn average, −4.8% vs. prior year.
- **Aktuelle Grundstückspreise — Bonn** — useful distinction between Bodenrichtwert (official) and Grundstückspreis (actual transaction).
- **GARS NRW — Bodenrichtwerte methodology** — explains what Bodenrichtwertzonen are; § 196 Abs. 1 BauGB and § 11 Abs. 1 GAVO NRW legal basis.

## Property listings (sample-scenario context)

- **ImmobilienScout24 listing — the Poppelsdorf property** — the reference listing for the Bonn sample YAML. See the `listing_url` field in `data/bonn_poppelsdorf.yaml`.

---

## Reliability ranking

Not all sources are equal. Ordered by authority:

**Tier 1 (official / legal source)** — Finanzamt NRW, BORIS NRW, Gutachterausschuss Bonn official pages, Wikipedia (for the Peterssche Formel itself).

**Tier 2 (reputable professional / institutional)** — Rosepartner (tax law firm), Pandotax (Steuerberatung), Schiffer (Sachverständige), Sparkasse articles, Wüstenrot, Interhyp, Hypofriend.

**Tier 3 (content marketing / aggregators)** — Immowelt, Homeday, Techem, Effi, LPE, Hausinfo.ch, BorisPortal (private), Bodenrichtwerte-Deutschland (private). Useful for cross-referencing numbers; don't treat as primary sources.

For anything affecting an actual tax filing, verify with a Steuerberater. For Bodenrichtwert, use BORIS NRW directly rather than any private aggregator — it's free and official.

---

## Caveats on what was used

- **AfA rates and rules** are stable and well-established — numbers are high-confidence.
- **Petersche Formel** is 40 years old and many modern sources consider it outdated (under-provisions for today's costs). Built into the code as one half of a `max()` with the II. BV table specifically to handle this.
- **Component lifecycles** are heuristics. The paritätische Lebensdauertabelle (HEV/MV) is referenced everywhere but the primary document wasn't pulled. Individual sources disagree by ±20% on specific components — midpoints were picked.
- **Bonn Bodenrichtwert range** (€1,000–1,600/m² for Poppelsdorf) came from a private aggregator, not BORIS NRW directly. Before publishing numbers that matter, verify with the official BORIS NRW value and update the sample YAML.
- **Construction cost figures** from BKI (Baukosteninformationszentrum) were cited indirectly via Schwäbisch Hall and Bal Heizung, not pulled from BKI directly. For serious work, use the actual BKI data — it's paid but more authoritative.
