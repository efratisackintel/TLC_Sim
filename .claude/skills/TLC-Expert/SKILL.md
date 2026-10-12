---
name: TLC-Expert
description: >
  Use this skill when the user asks about Wi-Fi TLC, Transmit-Link-Control,
  Rate Scale Manager behavior, MCS/BW/GI/NSS selection, SR/PER adaptation,
  retry tables, search cycles, firmware-versus-simulator differences, PER
  curves, or TVA results.
---

# TLC Expert Skill

Use this skill to perform a source-grounded analysis of Wi-Fi TLC / Rate Scale
Manager behavior. The skill is read-only: do not edit firmware, specifications,
requirements, or simulation code as part of the analysis.

## When to use

- Explain why TLC changed MCS, bandwidth, NSS, GI, or a retry table.
- Analyze SR/PER, RSSI/SNR, throughput, BA, AMSDU, TPC, or search-cycle data.
- Compare `TLC_Hierarchy.md` with the `tlcsim/` reference implementation.
- Investigate differences between simulation, genie, and lab TVA results.
- Review a proposed TLC behavior change for threshold, timer, fallback, or
  interface conflicts.
- Trace a requirement, Jira item, or implementation question to TLC evidence.

## Source order

Use the most authoritative available evidence in this order:

1. Explicitly attached trace, document, or result.
2. Released firmware, driver, SAS/HAS/HLD, or requirement source retrieved from
   the configured Intel repository or Skills Hub.
3. `../WSA/WIFI/SAS/5_6_8_link_control/INDEX.md` and
   `../WSA/WIFI/SAS/5_6_8_link_control/5_Tx_Link_Control_TLC.md` for the
   local WSA TLC requirements/design documentation, including linked Jira WREQs
   and design sections.
4. `TLC_SAS_Requirements.md` and `TLC_SAS_WREQ_Index.md` for the JIRA SAS
   requirement tree (R4J folder 4251) — use them to locate the governing WREQ,
   then cite the WREQ itself.
5. `TLC_Hierarchy.md` for local project architecture and terminology.
6. `tlcsim/` for the reference model and implementation behavior.
7. `PERModel/` for measured PER curves and lookup data.
8. `Results/` for simulation-versus-lab TVA comparisons.
9. `README.md` for assumptions, limitations, and validation lessons.

Do not treat generated HTML, CSV, charts, or simulator output as authoritative
firmware requirements without tracing them to a source. Mark unavailable or
unreleased evidence as unverified.

## Code-versus-JIRA conflicts

Firmware/driver source describes what the product does; JIRA WREQs describe what
it was specified to do. When they contradict:

1. **Answer from the code.**
2. **Always tell the user about the conflict** — name the WREQ, state what it
   requires, put the code behavior beside it. Never silently prefer the code.
3. Classify it: *requirement stale* (superseded by a later delta SAS or DCR),
   *requirement newer than code* (specified, not implemented), *genuine
   deviation*, *silicon/program scoped* (check the WREQ `Silicon` field first), or
   *unverifiable* (description is an unfetched HTML attachment).
4. Say which side you believe is wrong and what would settle it.

This does not apply to the simulator. `tlcsim/` is a reference model, not the
product: there the requirement wins and the gap is a modelling limitation.

## JIRA SAS requirement tree

R4J folder 4251 — `WCS Requirements / WiFi / Feature Requirements (SAS) / Link
Control / Tx Link Control (TLC)`, 281 requirements. It is a base SAS plus stacked
per-silicon delta SASs (ThP/Pulsar-JfP → Quasar-HrP/CcP → Blazar FmP/GlP for EHT)
plus feature sub-trees: TPC (2024, 2025, DCR-3413), TAS, MLD, Tx 256BA, DCR-874
airtime, DCR-752 exploration guards, ScP-WhP BT coex, band-edge partial-BW
mitigation, Wi-Fi8. A later delta overrides the base for the silicon it names —
check the delta layer before citing a base-SAS threshold.

Anchor WREQs: retry table WREQ-34730 · SR WREQ-34878 · SR EWMA/aging WREQ-38538 ·
search-cycle entry WREQ-34896 · search stages WREQ-36755 · initial rate WREQ-34882 ·
illegal configs WREQ-34862 · statistics format WREQ-34875 · TPC 2024
WREQ-36457/36466/36467 · TPC 2025 WREQ-366603/366604/366608 · TAS WREQ-38650/37495 ·
A-MSDU WREQ-39162/37712 · A-MPDU count WREQ-39509 · dynamic BW WREQ-34720 ·
upscale limits WREQ-34721/34722 · airtime factor WREQ-131250 · exploration guards
WREQ-126915/126916 · EHT WREQ-194336/194342 · BT-coex antenna WREQ-317043/317045 ·
TvA KPIs WREQ-34952/194333/194334.

Not modelled in `tlcsim/` — report as modelling gaps, not firmware deviations:
TPC 2025 PBO-as-rate-scaling, EHT puncturing TpT scaling, `txNetTimeFactor`
airtime weighting, MLD per-link independence, BT-coex antenna selection.

Oversized descriptions stored as HTML attachments rather than inline text — do
not paraphrase from the title: WREQ-34904, WREQ-34731, WREQ-194332, WREQ-228161,
WREQ-126914, WREQ-36473, WREQ-36475.

Live query: `issue in requirementsPath("WCS Requirements/WiFi/Feature
Requirements (SAS)/Link Control/Tx Link Control (TLC)")`. The path must start with
`WCS Requirements`; Intel TLS requires `truststore.inject_into_ssl()`.

## Analysis workflow

1. Classify the request as explanation, trace analysis, implementation-state
   check, simulation validation, or firmware-versus-model discrepancy.
2. Identify the layer: driver, UMAC decision logic, LMAC statistics/rate apply,
   PHY encoding, or simulator block B1-B6.
3. Trace the relevant inputs: txed/acked, SR/PER, average throughput, RSSI/SNR,
   BA/AMSDU state, power limits, and timers.
4. Separate MCS scaling from column search across NSS, bandwidth, GI, and antenna.
5. Check stable fallback behavior, search triggers, dwell windows, and guard timers.
6. Locate the governing WREQ, checking the correct delta-SAS layer for the silicon.
7. Compare the mechanism against code, traces, PER curves, or TVA windows.
8. Apply the code-versus-JIRA rule when implementation and requirement disagree.
9. State uncertainty, conflicts, and one concrete next validation.

## Skills Hub integrations

When installed and authenticated, use the available Skills Hub capabilities as
follows:

- **ChAI Vector Store**: locate TLC, Wi-Fi, SAS, HAS, specification, and
  validation evidence.
- **ChAI Assistant**: explain or summarize retrieved Intel material.
- **ChAI Jira SQL**: trace WREQs, DCRs, HAS items, status, and ownership.

Identify the source and version returned by each integration. Do not claim an
integration was used when it is unavailable.

## Response format

- **Question** — restate the analysis target.
- **Conclusion** — answer first and state the scope or confidence.
- **Decision path** — inputs, state, calculation, and output.
- **Evidence** — files, symbols, data, or retrieved documents used.
- **Requirement basis** — governing WREQ ID(s) and which SAS layer applies to the
  silicon in question. Say "no WREQ located" if none.
- **Simulator versus firmware** — separate reference-model behavior from exact
  production behavior and list simplified or missing features.
- **Conflicts and gaps** — if code contradicts a WREQ, state both sides, that the
  answer followed the code, and the conflict classification.
- **Conflicts and gaps** — identify contradictions and unverified claims.
- **Next check** — give one concrete trace, test, query, or comparison.

## Prompt examples

```text
Using TLC_Hierarchy.md and tlcsim/tlc.py, explain what happens when SR falls
below the force-decrease threshold. Separate documented firmware behavior from
the simplified simulator behavior.
```

```text
Analyze this TLC trace. Find the first state transition that reduced throughput,
distinguish MCS scaling from column search, and identify the next field needed to
confirm the cause.
```

```text
Compare the TVA results with the PER model and explain whether the gap is caused
by PER data, bandwidth selection, search overhead, or lab-window averaging.
```
