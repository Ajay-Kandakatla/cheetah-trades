/* 🧬 Medical catalysts — REAL payload captured 2026-09-29 03:47 ET from the branch API
 * (GET /catalysts/medical?days=10 and /catalysts/medical/KOD, port 8017) on a scratch DB
 * (cheetah_medcat_scratch2) after ONE dry-run pass of the branch routine with the REAL
 * classifier (catalysts/medical/classify.py + taxonomy.py) over real sources for sessions
 * 2026-09-21..2026-09-28: Finnhub company news x362 roster names, SEC 8-K EX-99.1 (26 exhibits),
 * Massive market-wide (1,388 items), FDA press RSS (20 items) -> 1,478 articles, 115 events,
 * 20 high impact. Trimmed to 14 of the 115 events (KOD x2, MIRM x3, ABBV, INCY, CLDX, AMGN,
 * MNOV, VKTX, MRNA ESMO + the 2 unresolved FDA approvals); everything else (labels, taxonomy,
 * the FULL served roll-up over all 115, counts, pass, push, sources) is verbatim.
 *
 * CAVEATS (real, not edited out): push.state is `pending` on every row (dry run: nothing
 * claimed, nothing sent) and `pass` is empty (a dry run records no pass). at_detection comes
 * from ONE snapshot at 03:24 ET with the tape closed: Massive returned price 0.0, so
 * at_detection.move_pct reads -100 on every resolved row (reaction.at_detection treats a 0.0
 * print as a price — FIXED in fix round 2, 2026-09-29: a re-capture would carry move_pct null /
 * "no print yet"; this capture is kept verbatim). at_close / liquidity are from closed bars and are real.
 * Replaces the 02:50 ET stand-in capture (scratch classifier), 2026-09-29.
 */
import type { MedBoard, MedSymbolPayload } from '../medicalCatalysts';

export const LIVE_BOARD = {
 "as_of": "2026-09-29T03:47:51.082397-04:00",
 "window_days": 10,
 "labels": {
  "measured": false,
  "status": "unmeasured",
  "setup": "pending study",
  "note": "UNMEASURED — nothing here has been measured. Events are classified by fixed word rules; moves are what the stock did, not a prediction. Setup: pending study. Not a buy or sell signal."
 },
 "taxonomy": {
  "event_types": [
   {
    "key": "fda_approval",
    "label": "FDA approval",
    "family": "fda",
    "emoji": "🏛️"
   },
   {
    "key": "fda_crl",
    "label": "FDA rejection / CRL",
    "family": "fda",
    "emoji": "🏛️"
   },
   {
    "key": "fda_revoked",
    "label": "FDA approval pulled / revoked",
    "family": "fda",
    "emoji": "🏛️"
   },
   {
    "key": "adcom",
    "label": "Advisory committee",
    "family": "fda",
    "emoji": "🏛️"
   },
   {
    "key": "topline",
    "label": "Trial topline",
    "family": "trial",
    "emoji": "🧪"
   },
   {
    "key": "conference_data",
    "label": "Conference data",
    "family": "conference",
    "emoji": "🎤"
   },
   {
    "key": "designation",
    "label": "Designation",
    "family": "regulatory",
    "emoji": "🏷️"
   },
   {
    "key": "regulatory_filing",
    "label": "Regulatory filing",
    "family": "regulatory",
    "emoji": "🏷️"
   },
   {
    "key": "pdufa",
    "label": "PDUFA date",
    "family": "regulatory",
    "emoji": "🏷️"
   },
   {
    "key": "exus_approval",
    "label": "Ex-US approval",
    "family": "regulatory",
    "emoji": "🏷️"
   },
   {
    "key": "clinical_hold",
    "label": "Clinical hold",
    "family": "hold",
    "emoji": "⚠️"
   },
   {
    "key": "safety",
    "label": "Safety",
    "family": "hold",
    "emoji": "⚠️"
   },
   {
    "key": "deal",
    "label": "Deal",
    "family": "deal",
    "emoji": "🤝"
   },
   {
    "key": "financing",
    "label": "Financing (dilution)",
    "family": "financing",
    "emoji": "💵"
   },
   {
    "key": "readout_scheduled",
    "label": "Readout scheduled",
    "family": "scheduled",
    "emoji": "📅"
   },
   {
    "key": "trial_milestone",
    "label": "Trial milestone",
    "family": "scheduled",
    "emoji": "📅"
   }
  ],
  "families": [
   {
    "key": "fda",
    "label": "FDA decisions",
    "emoji": "🏛️"
   },
   {
    "key": "trial",
    "label": "Trial readouts",
    "emoji": "🧪"
   },
   {
    "key": "conference",
    "label": "Conference data",
    "emoji": "🎤"
   },
   {
    "key": "regulatory",
    "label": "Designations, filings & dates",
    "emoji": "🏷️"
   },
   {
    "key": "hold",
    "label": "Holds & safety",
    "emoji": "⚠️"
   },
   {
    "key": "deal",
    "label": "Deals",
    "emoji": "🤝"
   },
   {
    "key": "financing",
    "label": "Financing — dilution",
    "emoji": "💵"
   },
   {
    "key": "scheduled",
    "label": "Scheduled & milestones",
    "emoji": "📅"
   }
  ],
  "modalities": [
   {
    "key": "mrna",
    "label": "mRNA"
   },
   {
    "key": "gene_editing",
    "label": "Gene editing"
   },
   {
    "key": "gene_therapy",
    "label": "Gene therapy"
   },
   {
    "key": "cell_therapy",
    "label": "Cell therapy"
   },
   {
    "key": "rnai_antisense",
    "label": "RNAi / antisense"
   },
   {
    "key": "adc",
    "label": "ADC"
   },
   {
    "key": "antibody_bispecific",
    "label": "Antibodies & bispecifics"
   },
   {
    "key": "radiopharma",
    "label": "Radiopharma"
   },
   {
    "key": "glp1_obesity",
    "label": "GLP-1 / obesity"
   },
   {
    "key": "vaccine",
    "label": "Vaccine"
   },
   {
    "key": "small_molecule",
    "label": "Small molecule"
   },
   {
    "key": "medtech_device",
    "label": "Medtech device"
   },
   {
    "key": "diagnostics",
    "label": "Diagnostics"
   },
   {
    "key": "unclassified",
    "label": "unclassified"
   }
  ],
  "areas": [
   {
    "key": "oncology",
    "label": "oncology"
   },
   {
    "key": "neurology",
    "label": "neurology"
   },
   {
    "key": "rare_disease",
    "label": "rare disease"
   },
   {
    "key": "immunology",
    "label": "immunology"
   },
   {
    "key": "cardio_metabolic",
    "label": "cardio-metabolic"
   },
   {
    "key": "ophthalmology",
    "label": "ophthalmology"
   },
   {
    "key": "infectious_disease",
    "label": "infectious disease"
   },
   {
    "key": "unclassified",
    "label": "unclassified"
   }
  ],
  "high_impact_text": "High impact = FDA approval (not tentative or generic); FDA complete response letter, refuse-to-file or rejection (not a withdrawn application); Phase 3 / Phase 2/3 / pivotal topline positive or negative (never mixed or undirected); Breakthrough Therapy designation; clinical hold placed (incl. partial)"
 },
 "events": [
  {
   "event_key": "UNRESOLVED:fda-approves-first-treatment-for-mct8-deficiency|fda_approval|2026-09-29",
   "ticker": null,
   "company": null,
   "event_type": "fda_approval",
   "family": "fda",
   "type_dir": "fda_approval",
   "label": "FDA approval",
   "subtype": "novel",
   "direction": null,
   "phase": null,
   "regulator": "FDA",
   "trials": [],
   "impact": "high",
   "modality": [
    "small_molecule"
   ],
   "modality_primary": "small_molecule",
   "areas": [
    "rare_disease"
   ],
   "area_primary": "rare_disease",
   "headline": "FDA Approves First Treatment for MCT8 Deficiency",
   "published_at_et": "2026-09-28T17:43:18-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": null,
   "session_date": "2026-09-29",
   "released": "afterhours",
   "sources": [
    {
     "provider": "fda_rss",
     "source": "FDA press release",
     "title": "FDA Approves First Treatment for MCT8 Deficiency",
     "url": "http://www.fda.gov/news-events/press-announcements/fda-approves-first-treatment-mct8-deficiency",
     "published_et": "2026-09-28T17:43:18-04:00"
    }
   ],
   "n_sources": 1,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": null,
    "at_close": null,
    "fwd": null
   },
   "liquidity": {
    "base_close": null,
    "base_basis": null,
    "adv50_usd": null,
    "avg_vol50": null,
    "pre_ret_20d_pct": null,
    "market_cap": null
   },
   "dilutive": null,
   "links": {
    "supply": null,
    "timeline": null
   }
  },
  {
   "event_key": "KOD|topline_positive|2026-09-28",
   "ticker": "KOD",
   "company": "Kodiak Sciences Inc.",
   "event_type": "topline",
   "family": "trial",
   "type_dir": "topline_positive",
   "label": "Phase 3 topline positive",
   "subtype": null,
   "direction": "positive",
   "phase": "3",
   "regulator": null,
   "trials": [
    "DAYBREAK"
   ],
   "impact": "high",
   "modality": [
    "antibody_bispecific"
   ],
   "modality_primary": "antibody_bispecific",
   "areas": [
    "ophthalmology",
    "cardio_metabolic"
   ],
   "area_primary": "ophthalmology",
   "headline": "Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints With Zenkuda (Tarcocimab Tedromer) And Tabirafusp-ted (KSI-501) Showing Non-inferiority In Vision Gains For Wet Age-related Macular Degeneration Vs. Aflibercept At Year One",
   "published_at_et": "2026-09-28T02:34:12-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 1490.8,
   "session_date": "2026-09-28",
   "released": "overnight",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints With Zenkuda (Tarcocimab Tedromer) And Tabirafusp-ted (KSI-501) Showing Non-inferiority In Vision Gains For Wet Age-related Macular Degeneration Vs. Aflibercept At Year One",
     "url": "https://finnhub.io/api/news?id=12279e5c8d466ae7e482d2066b56cd971e4e89d55aed3ca019d4624c3afe9792",
     "published_et": "2026-09-28T02:34:12-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences Shares Rise After DAYBREAK Phase 3 Trial Results",
     "url": "https://finnhub.io/api/news?id=5fab98fe7bf302b2f86088faac9438c01bf0a2894cc549d72250f13383645b49",
     "published_et": "2026-09-28T07:02:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences Stock Pops 70% After Eye-Disease Drugs Pass Key Trial",
     "url": "https://finnhub.io/api/news?id=5ccc96958948303f3ebe778c27f06e16375a6d2125a6ca030aabfaf6a769fd33",
     "published_et": "2026-09-28T07:58:00-04:00"
    },
    {
     "provider": "sec",
     "source": "SEC 8-K EX-99.1",
     "title": "Zenkuda and tabirafusp-ted Meet Primary Endpoints in Pivotal DAYBREAK Trial in wAMD, with Zenkuda Demonstrating a Potential New Standard-of-Care Profile with Strong Immediacy and Sustained Clinical Effect with Majority of Patients on 24-week Dosing Interval Using Strict Treat-to-Dryness Real World",
     "url": "https://www.sec.gov/Archives/edgar/data/1468748/000119312526403481/0001193125-26-403481-index.htm",
     "published_et": "2026-09-28T08:53:56-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences stock soars on positive AMD trial data",
     "url": "https://finnhub.io/api/news?id=a9a236c29ea2d798698b4572bf4a3735177e418b42da430ee0fd5b6e0773b567",
     "published_et": "2026-09-28T09:16:20-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences Soars 141% on “Truly Impressive” Pivotal Wet AMD Trial Win",
     "url": "https://finnhub.io/api/news?id=61d3cce9e3d728976866cce5e5d9206098f9e8e5ce8c9c0954a1b994d21f731a",
     "published_et": "2026-09-28T11:21:08-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak skyrockets on positive study data for 2 eye drugs",
     "url": "https://finnhub.io/api/news?id=6576ad23bafaed889c00ee39991c9982ab0fcb1d0d8f26c375245afe1ed63dd2",
     "published_et": "2026-09-28T12:11:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences soars as Zenkuda, tabirafusp-ted hit primary endpoints in phase III wet AMD trial",
     "url": "https://finnhub.io/api/news?id=10cc69c30509e8ec23a268bf8b02e837f8e94cb6094e782760d938658e7e2c52",
     "published_et": "2026-09-28T13:04:00-04:00"
    }
   ],
   "n_sources": 8,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 32.35,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 1490.8,
     "post_session": true
    },
    "at_close": {
     "open": 61.705,
     "high": 95.77,
     "low": 60.49,
     "close": 89.92,
     "volume": 38355170.0,
     "gap_pct": 90.74188562596599,
     "day_pct": 177.95981452859348,
     "rvol": 57.07526697474234,
     "dollar_volume": 3448896886.4,
     "close_loc": 0.8341836734693879,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 32.35,
    "base_basis": "frame",
    "adv50_usd": 22726016.883526836,
    "avg_vol50": 672010.34761648,
    "pre_ret_20d_pct": -17.305725971370133,
    "market_cap": 2033179933.95
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/KOD?tab=supply",
    "timeline": "/sepa/KOD?tab=catalyst"
   }
  },
  {
   "event_key": "MIRM|topline_positive|2026-09-28",
   "ticker": "MIRM",
   "company": "Mirum Pharmaceuticals, Inc.",
   "event_type": "topline",
   "family": "trial",
   "type_dir": "topline_positive",
   "label": "Phase 3 topline positive",
   "subtype": null,
   "direction": "positive",
   "phase": "3",
   "regulator": null,
   "trials": [
    "AZURE-1"
   ],
   "impact": "high",
   "modality": [
    "antibody_bispecific"
   ],
   "modality_primary": "antibody_bispecific",
   "areas": [
    "infectious_disease"
   ],
   "area_primary": "infectious_disease",
   "headline": "Mirum Pharma's Brelovitug Meets Phase 3 Primary Endpoint In AZURE-1 Study For Chronic Hepatitis Delta Virus",
   "published_at_et": "2026-09-28T04:08:17-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 1396.7,
   "session_date": "2026-09-28",
   "released": "premarket",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Mirum Pharma's Brelovitug Meets Phase 3 Primary Endpoint In AZURE-1 Study For Chronic Hepatitis Delta Virus",
     "url": "https://finnhub.io/api/news?id=2aebadde21d8da2fd265e8dde36ce2b88eaaa2f4f1da5935469109e1943394d8",
     "published_et": "2026-09-28T04:08:17-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Mirum Pharmaceuticals Announces Primary Endpoint Met in Phase 3 AZURE-1 Study of Brelovitug in Chronic Hepatitis Delta Virus",
     "url": "https://finnhub.io/api/news?id=d484b9aaa8c3c9dfabd287b1351753636ae5d95a8143e723887c554a6ef259fc",
     "published_et": "2026-09-28T08:00:00-04:00"
    }
   ],
   "n_sources": 2,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 89.7,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 1396.7,
     "post_session": true
    },
    "at_close": {
     "open": 90.0,
     "high": 91.2499,
     "low": 84.71,
     "close": 87.96,
     "volume": 1268143.0,
     "gap_pct": 0.33444816053511683,
     "day_pct": -1.9397993311036865,
     "rvol": 1.8903573427417812,
     "dollar_volume": 111545858.27999999,
     "close_loc": 0.4969494946405906,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 89.7,
    "base_basis": "frame",
    "adv50_usd": 57653223.76712185,
    "avg_vol50": 670848.29483122,
    "pre_ret_20d_pct": -10.075187969924803,
    "market_cap": 5470016061.900001
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/MIRM?tab=supply",
    "timeline": "/sepa/MIRM?tab=catalyst"
   }
  },
  {
   "event_key": "MIRM|fda_approval|2026-09-28",
   "ticker": "MIRM",
   "company": "Mirum Pharmaceuticals, Inc.",
   "event_type": "fda_approval",
   "family": "fda",
   "type_dir": "fda_approval",
   "label": "FDA approval",
   "subtype": "novel",
   "direction": null,
   "phase": null,
   "regulator": "FDA",
   "trials": [],
   "impact": "high",
   "modality": [
    "unclassified"
   ],
   "modality_primary": "unclassified",
   "areas": [
    "rare_disease"
   ],
   "area_primary": "rare_disease",
   "headline": "MIRM Secures FDA Nod for an Ultra-Rare Bone Disorder Therapy",
   "published_at_et": "2026-09-28T10:45:00-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 1000.0,
   "session_date": "2026-09-28",
   "released": "intraday",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "MIRM Secures FDA Nod for an Ultra-Rare Bone Disorder Therapy",
     "url": "https://finnhub.io/api/news?id=c66772dfe3ee69a70fa76f2ec8797d2c4507466e9205bbc48d9e0224ef01e94c",
     "published_et": "2026-09-28T10:45:00-04:00"
    }
   ],
   "n_sources": 1,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 89.7,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 1000.0,
     "post_session": true
    },
    "at_close": {
     "open": 90.0,
     "high": 91.2499,
     "low": 84.71,
     "close": 87.96,
     "volume": 1268143.0,
     "gap_pct": 0.33444816053511683,
     "day_pct": -1.9397993311036865,
     "rvol": 1.8903573427417812,
     "dollar_volume": 111545858.27999999,
     "close_loc": 0.4969494946405906,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 89.7,
    "base_basis": "frame",
    "adv50_usd": 57653223.76712185,
    "avg_vol50": 670848.29483122,
    "pre_ret_20d_pct": -10.075187969924803,
    "market_cap": 5470016061.900001
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/MIRM?tab=supply",
    "timeline": "/sepa/MIRM?tab=catalyst"
   }
  },
  {
   "event_key": "INCY|fda_approval|2026-09-28",
   "ticker": "INCY",
   "company": "Incyte Corporation",
   "event_type": "fda_approval",
   "family": "fda",
   "type_dir": "fda_approval",
   "label": "FDA approval",
   "subtype": "novel",
   "direction": null,
   "phase": null,
   "regulator": "FDA",
   "trials": [],
   "impact": "high",
   "modality": [
    "unclassified"
   ],
   "modality_primary": "unclassified",
   "areas": [
    "rare_disease"
   ],
   "area_primary": "rare_disease",
   "headline": "Mirum Pharmaceuticals and Incyte Announce U.S. FDA Approval of Atebrioz™ (zilurgisertib) for Adult and Pediatric Patients with Fibrodysplasia Ossificans Progressiva",
   "published_at_et": "2026-09-25T19:00:00-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 4825.0,
   "session_date": "2026-09-28",
   "released": "afterhours",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Mirum Pharmaceuticals and Incyte Announce U.S. FDA Approval of Atebrioz™ (zilurgisertib) for Adult and Pediatric Patients with Fibrodysplasia Ossificans Progressiva",
     "url": "https://finnhub.io/api/news?id=35a7a53435f6293704a9963de0e5dbe152bf4b44a46b7ad6f183aa81df7508ea",
     "published_et": "2026-09-25T19:00:00-04:00"
    }
   ],
   "n_sources": 1,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 123.89,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 4825.0,
     "post_session": true
    },
    "at_close": {
     "open": 123.32,
     "high": 126.14,
     "low": 122.5295,
     "close": 124.82,
     "volume": 1429360.0,
     "gap_pct": -0.46008555977077314,
     "day_pct": 0.750665913310189,
     "rvol": 0.8932737096935437,
     "dollar_volume": 178412715.2,
     "close_loc": 0.6343996676360596,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 123.89,
    "base_basis": "frame",
    "adv50_usd": 170597403.92546958,
    "avg_vol50": 1600136.64847516,
    "pre_ret_20d_pct": -3.0139345545639573,
    "market_cap": 25112223751.94
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/INCY?tab=supply",
    "timeline": "/sepa/INCY?tab=catalyst"
   }
  },
  {
   "event_key": "ABBV|fda_approval|2026-09-28",
   "ticker": "ABBV",
   "company": "AbbVie Inc.",
   "event_type": "fda_approval",
   "family": "fda",
   "type_dir": "fda_approval",
   "label": "FDA approval",
   "subtype": "novel",
   "direction": null,
   "phase": null,
   "regulator": "FDA",
   "trials": [],
   "impact": "high",
   "modality": [
    "small_molecule"
   ],
   "modality_primary": "small_molecule",
   "areas": [
    "neurology"
   ],
   "area_primary": "neurology",
   "headline": "AbbVie Receives FDA's Approval For JUVMO To Treat Adults with Parkinson's Disease",
   "published_at_et": "2026-09-28T04:02:13-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 1402.7,
   "session_date": "2026-09-28",
   "released": "premarket",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "AbbVie Receives FDA's Approval For JUVMO To Treat Adults with Parkinson's Disease",
     "url": "https://finnhub.io/api/news?id=9458ca1cde81cc051bb3a2085fc523f5b7fd261849dd8eca906d89eb9d0ec14b",
     "published_et": "2026-09-28T04:02:13-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "U.S. FDA Approves AbbVie's JUVMO™ (tavapadon) for Parkinson's Disease",
     "url": "https://finnhub.io/api/news?id=0fe04f9424057ac6f58b01ff402834c8d186ca69382560c877d162dc79fb1cb5",
     "published_et": "2026-09-28T08:00:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "AbbVie Receives FDA Approval for Parkinson’s Disease Drug Juvmo",
     "url": "https://finnhub.io/api/news?id=ec48ccbb6d85801540232ee27e90ae0124cd6c516bb8b76d3eb5ee822783852a",
     "published_et": "2026-09-28T09:54:35-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "AbbVie Won FDA Approval for Parkinson’s Pill Juvmo. Here’s Why Management Already Expects a Slow Start",
     "url": "https://finnhub.io/api/news?id=81d0c61c9dff2b06f3eb66926e5da6045f5ae2038b39ba7ccb51914822b19319",
     "published_et": "2026-09-28T11:14:37-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "FDA Nod For JUVMO Parkinson’s Drug Could Be A Game Changer For AbbVie (ABBV)",
     "url": "https://finnhub.io/api/news?id=63cd4f69a4735ea77694f7607117179505227e5dfe306a7177502329f46cbbcd",
     "published_et": "2026-09-29T01:11:17-04:00"
    }
   ],
   "n_sources": 5,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 264.34,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 1402.7,
     "post_session": true
    },
    "at_close": {
     "open": 264.33,
     "high": 267.735,
     "low": 263.38,
     "close": 266.28,
     "volume": 4393279.0,
     "gap_pct": -0.0037830067337485396,
     "day_pct": 0.7339033063478828,
     "rvol": 0.9331551339545314,
     "dollar_volume": 1169842332.12,
     "close_loc": 0.6659012629161802,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 264.34,
    "base_basis": "frame",
    "adv50_usd": 1121586580.61771,
    "avg_vol50": 4707983.528293019,
    "pre_ret_20d_pct": 2.3978307185744674,
    "market_cap": 467119783116.89996
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/ABBV?tab=supply",
    "timeline": "/sepa/ABBV?tab=catalyst"
   }
  },
  {
   "event_key": "MNOV|topline_unknown|2026-09-28",
   "ticker": "MNOV",
   "company": "MediciNova, Inc.",
   "event_type": "topline",
   "family": "trial",
   "type_dir": "topline_unknown",
   "label": "Topline results (direction not stated)",
   "subtype": null,
   "direction": "unknown",
   "phase": null,
   "regulator": null,
   "trials": [
    "MN-001-NATG-202"
   ],
   "impact": "low",
   "modality": [
    "unclassified"
   ],
   "modality_primary": "unclassified",
   "areas": [
    "cardio_metabolic"
   ],
   "area_primary": "cardio_metabolic",
   "headline": "MediciNova Announces Topline Results from  MN-001-NATG-202 Clinical Trial of MN-001 (Tipelukast)",
   "published_at_et": "2026-09-28T06:00:00-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 1285.0,
   "session_date": "2026-09-28",
   "released": "premarket",
   "sources": [
    {
     "provider": "massive",
     "source": "GlobeNewswire Inc.",
     "title": "MediciNova Announces Topline Results from  MN-001-NATG-202 Clinical Trial of MN-001 (Tipelukast)",
     "url": "https://www.globenewswire.com/news-release/2026/09/28/3369686/7767/en/medicinova-announces-topline-results-from-mn-001-natg-202-clinical-trial-of-mn-001-tipelukast.html",
     "published_et": "2026-09-28T06:00:00-04:00"
    }
   ],
   "n_sources": 1,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 2.58,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 1285.0,
     "post_session": true
    },
    "at_close": {
     "open": 2.4,
     "high": 2.45,
     "low": 1.69,
     "close": 2.1,
     "volume": 1617136.0,
     "gap_pct": -6.976744186046513,
     "day_pct": -18.6046511627907,
     "rvol": 4.802155309972343,
     "dollar_volume": 3395985.6,
     "close_loc": 0.5394736842105263,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 2.58,
    "base_basis": "frame",
    "adv50_usd": 62293.0992478,
    "avg_vol50": 336752.12391439994,
    "pre_ret_20d_pct": 81.69014084507045,
    "market_cap": null
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/MNOV?tab=supply",
    "timeline": "/sepa/MNOV?tab=catalyst"
   }
  },
  {
   "event_key": "MIRM|readout_scheduled|2026-09-28",
   "ticker": "MIRM",
   "company": "Mirum Pharmaceuticals, Inc.",
   "event_type": "readout_scheduled",
   "family": "scheduled",
   "type_dir": "readout_scheduled",
   "label": "Readout scheduled",
   "subtype": "scheduled",
   "direction": null,
   "phase": null,
   "regulator": null,
   "trials": [
    "AZURE-1"
   ],
   "impact": "low",
   "modality": [
    "antibody_bispecific"
   ],
   "modality_primary": "antibody_bispecific",
   "areas": [
    "infectious_disease"
   ],
   "area_primary": "infectious_disease",
   "headline": "Mirum Pharmaceuticals to Host Investor Call to Share Topline Results from the Phase 3 AZURE-1 Study of Brelovitug in Chronic Hepatitis Delta on September 28, 2026",
   "published_at_et": "2026-09-27T17:00:00-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 2065.0,
   "session_date": "2026-09-28",
   "released": "closed_day",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Mirum Pharmaceuticals to Host Investor Call to Share Topline Results from the Phase 3 AZURE-1 Study of Brelovitug in Chronic Hepatitis Delta on September 28, 2026",
     "url": "https://finnhub.io/api/news?id=b9e585642708ae7aac63f1c40d26933600aa368a3aaebecacd33de57ccd64e47",
     "published_et": "2026-09-27T17:00:00-04:00"
    }
   ],
   "n_sources": 1,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 89.7,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 2065.0,
     "post_session": true
    },
    "at_close": {
     "open": 90.0,
     "high": 91.2499,
     "low": 84.71,
     "close": 87.96,
     "volume": 1268143.0,
     "gap_pct": 0.33444816053511683,
     "day_pct": -1.9397993311036865,
     "rvol": 1.8903573427417812,
     "dollar_volume": 111545858.27999999,
     "close_loc": 0.4969494946405906,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 89.7,
    "base_basis": "frame",
    "adv50_usd": 57653223.76712185,
    "avg_vol50": 670848.29483122,
    "pre_ret_20d_pct": -10.075187969924803,
    "market_cap": 5470016061.900001
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/MIRM?tab=supply",
    "timeline": "/sepa/MIRM?tab=catalyst"
   }
  },
  {
   "event_key": "KOD|readout_scheduled|2026-09-25",
   "ticker": "KOD",
   "company": "Kodiak Sciences Inc.",
   "event_type": "readout_scheduled",
   "family": "scheduled",
   "type_dir": "readout_scheduled",
   "label": "Readout scheduled",
   "subtype": "scheduled",
   "direction": null,
   "phase": null,
   "regulator": null,
   "trials": [
    "DAYBREAK"
   ],
   "impact": "low",
   "modality": [
    "antibody_bispecific"
   ],
   "modality_primary": "antibody_bispecific",
   "areas": [
    "ophthalmology"
   ],
   "area_primary": "ophthalmology",
   "headline": "Kodiak Sciences To Host Webcast To Report Phase 3 DAYBREAK Topline Results For Wet AMD Candidates On September 28 At 8:30 AM Eastern Time",
   "published_at_et": "2026-09-25T14:03:55-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 5121.0,
   "session_date": "2026-09-25",
   "released": "intraday",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Kodiak Sciences To Host Webcast To Report Phase 3 DAYBREAK Topline Results For Wet AMD Candidates On September 28 At 8:30 AM Eastern Time",
     "url": "https://finnhub.io/api/news?id=c41e82eec9b1b502aecef904392dccf8e2905817dc4331d6b476508ce2805796",
     "published_et": "2026-09-25T14:03:55-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences to Present Topline Results on September 28, 2026 from DAYBREAK Pivotal Phase 3 Study of Zenkuda and KSI-501 in Patients with Wet Age-Related Macular Degeneration",
     "url": "https://finnhub.io/api/news?id=b98cb90cbb0b1204a8612eeb69b8eb609180cf893ae727f0c328ab8b47ae196f",
     "published_et": "2026-09-25T18:01:00-04:00"
    }
   ],
   "n_sources": 2,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 33.22,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 5121.0,
     "post_session": true
    },
    "at_close": {
     "open": 33.03,
     "high": 33.705,
     "low": 31.0,
     "close": 32.35,
     "volume": 2277335.752434,
     "gap_pct": -0.5719446116797089,
     "day_pct": -2.618904274533407,
     "rvol": 3.5821818689150438,
     "dollar_volume": 73671811.5912399,
     "close_loc": 0.4990757855822559,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 33.22,
    "base_basis": "frame",
    "adv50_usd": 22496969.694000877,
    "avg_vol50": 635739.8467665601,
    "pre_ret_20d_pct": -15.535214848715995,
    "market_cap": 2033179933.95
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/KOD?tab=supply",
    "timeline": "/sepa/KOD?tab=catalyst"
   }
  },
  {
   "event_key": "UNRESOLVED:elevar-therapeutics-announces-fda-approval-of-ly|fda_approval|2026-09-24",
   "ticker": null,
   "company": null,
   "event_type": "fda_approval",
   "family": "fda",
   "type_dir": "fda_approval",
   "label": "FDA approval",
   "subtype": "novel",
   "direction": null,
   "phase": null,
   "regulator": "FDA",
   "trials": [],
   "impact": "high",
   "modality": [
    "small_molecule"
   ],
   "modality_primary": "small_molecule",
   "areas": [
    "oncology"
   ],
   "area_primary": "oncology",
   "headline": "Elevar Therapeutics Announces FDA Approval of Lyrfigtu (Lirafugratinib) as Second-line Cholangiocarcinoma with FGFR2 Fusion or Other Rearrangement Treatment Option",
   "published_at_et": "2026-09-23T17:54:00-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": null,
   "session_date": "2026-09-24",
   "released": "afterhours",
   "sources": [
    {
     "provider": "massive",
     "source": "GlobeNewswire Inc.",
     "title": "Elevar Therapeutics Announces FDA Approval of Lyrfigtu (Lirafugratinib) as Second-line Cholangiocarcinoma with FGFR2 Fusion or Other Rearrangement Treatment Option",
     "url": "https://www.globenewswire.com/news-release/2026/09/23/3367897/0/en/elevar-therapeutics-announces-fda-approval-of-lyrfigtu-lirafugratinib-as-second-line-cholangiocarcinoma-with-fgfr2-fusion-or-other-rearrangement-treatment-option.html",
     "published_et": "2026-09-23T17:54:00-04:00"
    }
   ],
   "n_sources": 1,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": null,
    "at_close": null,
    "fwd": null
   },
   "liquidity": {
    "base_close": null,
    "base_basis": null,
    "adv50_usd": null,
    "avg_vol50": null,
    "pre_ret_20d_pct": null,
    "market_cap": null
   },
   "dilutive": null,
   "links": {
    "supply": null,
    "timeline": null
   }
  },
  {
   "event_key": "VKTX|financing|2026-09-23",
   "ticker": "VKTX",
   "company": "Viking Therapeutics, Inc.",
   "event_type": "financing",
   "family": "financing",
   "type_dir": "financing",
   "label": "Offering (dilution)",
   "subtype": "convertible",
   "direction": null,
   "phase": null,
   "regulator": null,
   "trials": [],
   "impact": "low",
   "modality": [
    "unclassified"
   ],
   "modality_primary": "unclassified",
   "areas": [
    "unclassified"
   ],
   "area_primary": "unclassified",
   "headline": "Viking Therapeutics Announces $200M Common Stock And $200M Convertible Senior Notes Due 2032; Proceeds To Fund VK2735, VK3019 Clinical Development And General Corporate Purposes",
   "published_at_et": "2026-09-23T12:35:35-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 8089.4,
   "session_date": "2026-09-23",
   "released": "intraday",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Viking Therapeutics Announces $200M Common Stock And $200M Convertible Senior Notes Due 2032; Proceeds To Fund VK2735, VK3019 Clinical Development And General Corporate Purposes",
     "url": "https://finnhub.io/api/news?id=7a989cf54e4acc7a072c53588f90ec30c82d3ac5ffc06e234b1041c3a1a87c65",
     "published_et": "2026-09-23T12:35:35-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Viking Therapeutics Stock Drops In After Hours on Proposed Public Offerings",
     "url": "https://finnhub.io/api/news?id=969a4493b8a4d3681e6c8b6ac880504138124afe70bb3513ecb6e649ede9356e",
     "published_et": "2026-09-23T13:06:32-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Viking Therapeutics Announces Proposed Offerings of Common Stock and Convertible Senior Notes",
     "url": "https://finnhub.io/api/news?id=e9400b598627e6d63579e504995d5723f45dc7d51f0296ec9fea058270d6e832",
     "published_et": "2026-09-23T16:32:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Viking Therapeutics Prices Concurrent Public Offerings Of 7,857,143 Shares At $35/Shr And $225M Aggregate Principal Amount Of 2.00% Convertible Senior Notes Due 2032",
     "url": "https://finnhub.io/api/news?id=8873d4e12dbc9a0c87d299ed5559bb58cc738190cb3a8904e8601d731f3f0ca3",
     "published_et": "2026-09-24T03:11:45-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Viking Therapeutics Prices Upsized $500 Million Offering of Common Stock and Convertible Senior Notes",
     "url": "https://finnhub.io/api/news?id=25e1794317d75685a9030174824dae0dfffd2777ce5179b622a4abde004a8384",
     "published_et": "2026-09-24T07:05:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Viking Therapeutics Sinks 15% After Pricing Upsized $500M Offering; Jaguar Health Tumbles 25%",
     "url": "https://finnhub.io/api/news?id=8aac685980aec9635768581e3f203fb9e85959e4933af99ce60f24d6d4e7970a",
     "published_et": "2026-09-24T10:23:20-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Viking Therapeutics Sinks 12% on “Upsized” $500 Million Raise",
     "url": "https://finnhub.io/api/news?id=2bdff1adc7883ed508e7b4cbc83c6dd9af155f25c101a981b71b1c65eaa5eba4",
     "published_et": "2026-09-24T10:24:46-04:00"
    }
   ],
   "n_sources": 7,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 40.85,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 8089.4,
     "post_session": true
    },
    "at_close": {
     "open": 41.76,
     "high": 43.1,
     "low": 37.71,
     "close": 41.65,
     "volume": 15732165.53316,
     "gap_pct": 2.227662178702561,
     "day_pct": 1.9583843329253225,
     "rvol": 5.693160529603899,
     "dollar_volume": 655244694.4561139,
     "close_loc": 0.7309833024118734,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 40.85,
    "base_basis": "frame",
    "adv50_usd": 58849773.36343778,
    "avg_vol50": 2763344.7979122,
    "pre_ret_20d_pct": 22.931086367740015,
    "market_cap": 3853046509.11
   },
   "dilutive": true,
   "links": {
    "supply": "/sepa/VKTX?tab=supply",
    "timeline": "/sepa/VKTX?tab=catalyst"
   }
  },
  {
   "event_key": "CLDX|topline_positive|2026-09-22",
   "ticker": "CLDX",
   "company": "Celldex Therapeutics, Inc.",
   "event_type": "topline",
   "family": "trial",
   "type_dir": "topline_positive",
   "label": "Phase 3 topline positive",
   "subtype": null,
   "direction": "positive",
   "phase": "3",
   "regulator": null,
   "trials": [],
   "impact": "high",
   "modality": [
    "antibody_bispecific"
   ],
   "modality_primary": "antibody_bispecific",
   "areas": [
    "immunology"
   ],
   "area_primary": "immunology",
   "headline": "Celldex Announces Positive Results from Phase 3 EMBARQ-CSU1 and EMBARQ-CSU2 Studies of Barzolvolimab Which Met Primary and All Key Secondary Endpoints",
   "published_at_et": "2026-09-22T06:58:00-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 9867.0,
   "session_date": "2026-09-22",
   "released": "premarket",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Celldex Announces Positive Results from Phase 3 EMBARQ-CSU1 and EMBARQ-CSU2 Studies of Barzolvolimab Which Met Primary and All Key Secondary Endpoints",
     "url": "https://finnhub.io/api/news?id=e8869054f099f9d6f0a0d699226ed9e32fea033f862edd09caa32175d6df427e",
     "published_et": "2026-09-22T06:58:00-04:00"
    },
    {
     "provider": "sec",
     "source": "SEC 8-K EX-99.1",
     "title": "Exhibit 99.1 Celldex Announces Positive Results from Phase 3 EMBARQ-CSU1 and EMBARQ-CSU2 Studies of Barzolvolimab Which Met Primary and All Key Secondary Endpoints · Best-in-disease results showed rapid, profound, sustained efficacy, supporting barzolvolimab’s potential to be a transformational",
     "url": "https://www.sec.gov/Archives/edgar/data/744218/000110465926109465/0001104659-26-109465-index.htm",
     "published_et": "2026-09-22T07:09:01-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Celldex Shares Rise 8% as Barzolvolimab Meets Primary Endpoints in Two Phase 3 Trials",
     "url": "https://finnhub.io/api/news?id=efc29dced2c91f50f4d15fc19f1de28771f6de2033d6aa847a4e765af756538a",
     "published_et": "2026-09-22T09:40:42-04:00"
    }
   ],
   "n_sources": 3,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 37.89,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 9867.0,
     "post_session": true
    },
    "at_close": {
     "open": 36.6,
     "high": 38.39,
     "low": 30.39,
     "close": 33.51,
     "volume": 12888897.323526,
     "gap_pct": -3.4045922406967466,
     "day_pct": -11.559778305621538,
     "rvol": 14.7776557780649,
     "dollar_volume": 431906949.31135625,
     "close_loc": 0.3899999999999997,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 37.89,
    "base_basis": "frame",
    "adv50_usd": 32514656.88922136,
    "avg_vol50": 872188.2223469798,
    "pre_ret_20d_pct": -6.166419019316494,
    "market_cap": 2974064608.08
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/CLDX?tab=supply",
    "timeline": "/sepa/CLDX?tab=catalyst"
   }
  },
  {
   "event_key": "AMGN|topline_positive|2026-09-22",
   "ticker": "AMGN",
   "company": "Amgen Inc.",
   "event_type": "topline",
   "family": "trial",
   "type_dir": "topline_positive",
   "label": "Phase 3 topline positive",
   "subtype": null,
   "direction": "positive",
   "phase": "3",
   "regulator": null,
   "trials": [
    "OASIZ"
   ],
   "impact": "high",
   "modality": [
    "unclassified"
   ],
   "modality_primary": "unclassified",
   "areas": [
    "immunology",
    "oncology"
   ],
   "area_primary": "oncology",
   "headline": "Amgen Announces Its Phase 3 OASIZ 301 Trial Of Dazodalibep To Treat Sjogren's Disease Meets Primary Endpoint, Shows Improvement In Systemic Disease Activity At Week 48",
   "published_at_et": "2026-09-22T05:02:24-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 9982.6,
   "session_date": "2026-09-22",
   "released": "premarket",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Amgen Announces Its Phase 3 OASIZ 301 Trial Of Dazodalibep To Treat Sjogren's Disease Meets Primary Endpoint, Shows Improvement In Systemic Disease Activity At Week 48",
     "url": "https://finnhub.io/api/news?id=9b645c85ddc4b85f2b0779a66606c423cecbb91dccf298b9743d1cb81b4939c6",
     "published_et": "2026-09-22T05:02:24-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "AMGEN ANNOUNCES POSITIVE TOPLINE PHASE 3 RESULTS FOR DAZODALIBEP IN MODERATE-TO-SEVERE SYSTEMIC SJÖGREN'S DISEASE",
     "url": "https://finnhub.io/api/news?id=92e0e0c1543d7f89dd5d7edd4324186ec9bde19b1453d2d539e2f9cbcca61a62",
     "published_et": "2026-09-22T09:00:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Amgen Hits Primary Endpoint In Sjögren's Trial, But Approval Filing Awaits Another Trial Data",
     "url": "https://finnhub.io/api/news?id=f7dbf71da8f4ca654a7a528ca19e2ce31abe947c86801df595990ffe35367f82",
     "published_et": "2026-09-22T09:56:19-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Amgen (AMGN) Posted Positive Phase 3 Results In Sjögren's Disease",
     "url": "https://finnhub.io/api/news?id=2d8c31360bae79bdf4e2f1e02084114984ea00c2a14966a1fff9e7886a020981",
     "published_et": "2026-09-22T13:13:09-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Amgen Stock Gains After Announcing Positive Phase 3 Sjögren’s Disease Trial Results",
     "url": "https://finnhub.io/api/news?id=89c11e69e4db005a76127ada782e16f64e9ca8278d764fe2713c3fa77904bc92",
     "published_et": "2026-09-23T08:35:33-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Amgen (AMGN) Is Up 7.9% After Positive Phase 3 Dazodalibep Data in Systemic Sjögren’s Disease",
     "url": "https://finnhub.io/api/news?id=9d1b6d30a83ac7b25d9c4325db40264db276bc05fde9b5a99294e0ac553350af",
     "published_et": "2026-09-23T21:14:23-04:00"
    }
   ],
   "n_sources": 6,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 393.16,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 9982.6,
     "post_session": true
    },
    "at_close": {
     "open": 405.25,
     "high": 412.995,
     "low": 398.52,
     "close": 410.24,
     "volume": 3720961.557002,
     "gap_pct": 3.075083935293521,
     "day_pct": 4.344287313053208,
     "rvol": 1.3591102336540135,
     "dollar_volume": 1526487269.1445005,
     "close_loc": 0.8096718480138175,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 393.16,
    "base_basis": "frame",
    "adv50_usd": 1023015595.5950177,
    "avg_vol50": 2737792.317991801,
    "pre_ret_20d_pct": -10.509184439942631,
    "market_cap": 212554879085.80002
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/AMGN?tab=supply",
    "timeline": "/sepa/AMGN?tab=catalyst"
   }
  },
  {
   "event_key": "MRNA|conference_data|2026-09-21",
   "ticker": "MRNA",
   "company": "Moderna, Inc.",
   "event_type": "conference_data",
   "family": "conference",
   "type_dir": "conference_data",
   "label": "Conference data (upcoming)",
   "subtype": "upcoming",
   "direction": null,
   "phase": null,
   "regulator": null,
   "trials": [],
   "impact": "low",
   "modality": [
    "mrna",
    "antibody_bispecific",
    "vaccine"
   ],
   "modality_primary": "mrna",
   "areas": [
    "oncology"
   ],
   "area_primary": "oncology",
   "headline": "Moderna To Present Three Abstracts On Intismeran Autogene At European Society For Medical Oncology Congress 2026",
   "published_at_et": "2026-09-21T06:13:43-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 11351.2,
   "session_date": "2026-09-21",
   "released": "premarket",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Moderna To Present Three Abstracts On Intismeran Autogene At European Society For Medical Oncology Congress 2026",
     "url": "https://finnhub.io/api/news?id=78b6f2912aeec0a40d3cfc1d5bc2aa458cb199f8b2fd683109d392bf6d27c3eb",
     "published_et": "2026-09-21T06:13:43-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Moderna Announces Late-Breaking Data to be Presented at ESMO Congress 2026",
     "url": "https://finnhub.io/api/news?id=d59977c043e481bc9c380401822c69bbe5433531c9eb0c6a6038b25ad7177e52",
     "published_et": "2026-09-21T10:12:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Moderna To Present Additional Data From Key Melanoma Trial At ESMO Congress – Retail Says ‘Breakout Is Getting Hard To Ignore’",
     "url": "https://finnhub.io/api/news?id=75368c5390dea5e6596b02a0e97eee378a8d5acece9df7257ee2b759aa52aba4",
     "published_et": "2026-09-21T13:40:20-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Moderna Stock Jumped 12% Yesterday. An ESMO Presidential Slot Explains Why.",
     "url": "https://finnhub.io/api/news?id=c25680dffd6279bff8d8c383db32e2274a11268e0b31110b5feb7737c4ff4244",
     "published_et": "2026-09-22T03:33:05-04:00"
    }
   ],
   "n_sources": 4,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 154.04,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 11351.2,
     "post_session": true
    },
    "at_close": {
     "open": 161.05,
     "high": 176.86,
     "low": 159.06,
     "close": 172.94,
     "volume": 21018288.555202,
     "gap_pct": 4.550766034796161,
     "day_pct": 12.269540379122311,
     "rvol": 1.177380122020033,
     "dollar_volume": 3634902822.736634,
     "close_loc": 0.7797752808988756,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": 28.070631004933787,
     "ret_21d_pct": null,
     "drift_5d_pct": 14.07424540302995,
     "matured_5d": true,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 154.04,
    "base_basis": "frame",
    "adv50_usd": 472508684.15275955,
    "avg_vol50": 17851744.022262655,
    "pre_ret_20d_pct": 15.541554155415538,
    "market_cap": 61498296341.56
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/MRNA?tab=supply",
    "timeline": "/sepa/MRNA?tab=catalyst"
   }
  }
 ],
 "rollup": {
  "by_modality": [
   {
    "key": "unclassified",
    "label": "unclassified",
    "n_events": 47,
    "n_high": 7,
    "n_positive": 10,
    "n_negative": 1,
    "n_obs": 44,
    "median_day_pct": 0.17439832577605952,
    "n_day": 37,
    "median_ret_5d_pct": -2.667961270670144,
    "n_5d": 6,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 39,
    "small_n": false,
    "tickers": [
     "ABBV",
     "ACAD",
     "ALKS",
     "AMGN",
     "ARAY",
     "AXSM",
     "CLDI",
     "CLYD"
    ]
   },
   {
    "key": "antibody_bispecific",
    "label": "Antibodies & bispecifics",
    "n_events": 25,
    "n_high": 4,
    "n_positive": 6,
    "n_negative": 2,
    "n_obs": 20,
    "median_day_pct": 0.4956499636650791,
    "n_day": 20,
    "median_ret_5d_pct": 1.239191121399874,
    "n_5d": 3,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 17,
    "small_n": false,
    "tickers": [
     "CCCC",
     "CGEM",
     "CLDX",
     "CMPX",
     "CUE",
     "ELDN",
     "HCM",
     "IMVT"
    ]
   },
   {
    "key": "small_molecule",
    "label": "Small molecule",
    "n_events": 21,
    "n_high": 6,
    "n_positive": 6,
    "n_negative": 0,
    "n_obs": 19,
    "median_day_pct": 0.19699954538567876,
    "n_day": 15,
    "median_ret_5d_pct": 1.0590560850218034,
    "n_5d": 2,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 14,
    "small_n": false,
    "tickers": [
     "ABBV",
     "ANIP",
     "ARVN",
     "GOSS",
     "HCM",
     "INCY",
     "LLY",
     "MLYS"
    ]
   },
   {
    "key": "glp1_obesity",
    "label": "GLP-1 / obesity",
    "n_events": 6,
    "n_high": 0,
    "n_positive": 1,
    "n_negative": 0,
    "n_obs": 4,
    "median_day_pct": 0.445208944652431,
    "n_day": 3,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 4,
    "small_n": true,
    "tickers": [
     "NVO",
     "RYTM",
     "VKTX",
     "WVE"
    ]
   },
   {
    "key": "medtech_device",
    "label": "Medtech device",
    "n_events": 4,
    "n_high": 1,
    "n_positive": 2,
    "n_negative": 0,
    "n_obs": 4,
    "median_day_pct": 1.8826179053734793,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 4,
    "small_n": true,
    "tickers": [
     "BSX",
     "GRAL",
     "NTRA",
     "SIBN"
    ]
   },
   {
    "key": "cell_therapy",
    "label": "Cell therapy",
    "n_events": 3,
    "n_high": 0,
    "n_positive": 0,
    "n_negative": 0,
    "n_obs": 3,
    "median_day_pct": 4.506993006993004,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 3,
    "small_n": true,
    "tickers": [
     "LGVN",
     "NKTX",
     "TCRT"
    ]
   },
   {
    "key": "mrna",
    "label": "mRNA",
    "n_events": 3,
    "n_high": 0,
    "n_positive": 0,
    "n_negative": 0,
    "n_obs": 2,
    "median_day_pct": 2.3795546123706153,
    "n_day": 2,
    "median_ret_5d_pct": 28.070631004933787,
    "n_5d": 1,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 2,
    "small_n": true,
    "tickers": [
     "ARCT",
     "MRNA"
    ]
   },
   {
    "key": "diagnostics",
    "label": "Diagnostics",
    "n_events": 2,
    "n_high": 0,
    "n_positive": 0,
    "n_negative": 0,
    "n_obs": 2,
    "median_day_pct": 2.7883055489129394,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 2,
    "small_n": true,
    "tickers": [
     "NTRA",
     "TECH"
    ]
   },
   {
    "key": "gene_editing",
    "label": "Gene editing",
    "n_events": 2,
    "n_high": 0,
    "n_positive": 0,
    "n_negative": 0,
    "n_obs": 2,
    "median_day_pct": 0.9646104694027935,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 2,
    "small_n": true,
    "tickers": [
     "NTLA",
     "PRME"
    ]
   },
   {
    "key": "gene_therapy",
    "label": "Gene therapy",
    "n_events": 2,
    "n_high": 0,
    "n_positive": 1,
    "n_negative": 0,
    "n_obs": 2,
    "median_day_pct": 0.9824233560827622,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 2,
    "small_n": true,
    "tickers": [
     "LXEO",
     "RGNX"
    ]
   },
   {
    "key": "rnai_antisense",
    "label": "RNAi / antisense",
    "n_events": 2,
    "n_high": 1,
    "n_positive": 1,
    "n_negative": 0,
    "n_obs": 2,
    "median_day_pct": -3.651153265238194,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 2,
    "small_n": true,
    "tickers": [
     "IONS",
     "WVE"
    ]
   },
   {
    "key": "radiopharma",
    "label": "Radiopharma",
    "n_events": 2,
    "n_high": 1,
    "n_positive": 1,
    "n_negative": 0,
    "n_obs": 2,
    "median_day_pct": -0.13960909453530346,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 1,
    "small_n": true,
    "tickers": [
     "LNTH"
    ]
   },
   {
    "key": "adc",
    "label": "ADC",
    "n_events": 1,
    "n_high": 0,
    "n_positive": 0,
    "n_negative": 0,
    "n_obs": 1,
    "median_day_pct": 2.155504234026173,
    "n_day": 1,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 1,
    "small_n": true,
    "tickers": [
     "BHVN"
    ]
   },
   {
    "key": "vaccine",
    "label": "Vaccine",
    "n_events": 1,
    "n_high": 0,
    "n_positive": 0,
    "n_negative": 0,
    "n_obs": 1,
    "median_day_pct": 12.269540379122311,
    "n_day": 1,
    "median_ret_5d_pct": 28.070631004933787,
    "n_5d": 1,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 1,
    "small_n": true,
    "tickers": [
     "MRNA"
    ]
   }
  ],
  "by_area": [
   {
    "key": "unclassified",
    "label": "unclassified",
    "n_events": 36,
    "n_high": 3,
    "n_positive": 5,
    "n_negative": 0,
    "n_obs": 32,
    "median_day_pct": 0.27601330913489264,
    "n_day": 25,
    "median_ret_5d_pct": -1.9416666666666638,
    "n_5d": 5,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 26,
    "small_n": false,
    "tickers": [
     "ABBV",
     "ALKS",
     "AMGN",
     "ANIP",
     "ARCT",
     "BSX",
     "CLDI",
     "CLDX"
    ]
   },
   {
    "key": "oncology",
    "label": "oncology",
    "n_events": 31,
    "n_high": 7,
    "n_positive": 8,
    "n_negative": 1,
    "n_obs": 30,
    "median_day_pct": 0.4506863308981979,
    "n_day": 27,
    "median_ret_5d_pct": 14.47477602678876,
    "n_5d": 2,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 25,
    "small_n": false,
    "tickers": [
     "ABBV",
     "AMGN",
     "ARAY",
     "ARVN",
     "BHVN",
     "CCCC",
     "CGEM",
     "CMPX"
    ]
   },
   {
    "key": "cardio_metabolic",
    "label": "cardio-metabolic",
    "n_events": 20,
    "n_high": 5,
    "n_positive": 7,
    "n_negative": 0,
    "n_obs": 18,
    "median_day_pct": 0.445208944652431,
    "n_day": 15,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 15,
    "small_n": false,
    "tickers": [
     "CLYD",
     "GOSS",
     "IONS",
     "KOD",
     "LLY",
     "MLYS",
     "MNOV",
     "MRK"
    ]
   },
   {
    "key": "immunology",
    "label": "immunology",
    "n_events": 20,
    "n_high": 5,
    "n_positive": 8,
    "n_negative": 1,
    "n_obs": 17,
    "median_day_pct": 0.26953740097106493,
    "n_day": 16,
    "median_ret_5d_pct": -12.516005062722668,
    "n_5d": 2,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 16,
    "small_n": false,
    "tickers": [
     "ABBV",
     "AMGN",
     "CGEM",
     "CLDX",
     "CUE",
     "ELDN",
     "EVMN",
     "IMVT"
    ]
   },
   {
    "key": "neurology",
    "label": "neurology",
    "n_events": 9,
    "n_high": 2,
    "n_positive": 2,
    "n_negative": 2,
    "n_obs": 9,
    "median_day_pct": -0.42032920369013405,
    "n_day": 8,
    "median_ret_5d_pct": -6.684955241120427,
    "n_5d": 1,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 9,
    "small_n": false,
    "tickers": [
     "ABBV",
     "ACAD",
     "ARAY",
     "AXSM",
     "IMVT",
     "IONS",
     "LXEO",
     "MSLE"
    ]
   },
   {
    "key": "ophthalmology",
    "label": "ophthalmology",
    "n_events": 7,
    "n_high": 2,
    "n_positive": 3,
    "n_negative": 0,
    "n_obs": 7,
    "median_day_pct": 0.5406135964319603,
    "n_day": 7,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 5,
    "small_n": false,
    "tickers": [
     "GKOS",
     "KOD",
     "LGND",
     "MRK",
     "RGNX"
    ]
   },
   {
    "key": "rare_disease",
    "label": "rare disease",
    "n_events": 6,
    "n_high": 4,
    "n_positive": 4,
    "n_negative": 0,
    "n_obs": 5,
    "median_day_pct": -0.5945667088967488,
    "n_day": 4,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 5,
    "small_n": false,
    "tickers": [
     "INCY",
     "IONS",
     "MIRM",
     "MSLE",
     "SRPT"
    ]
   },
   {
    "key": "infectious_disease",
    "label": "infectious disease",
    "n_events": 3,
    "n_high": 2,
    "n_positive": 2,
    "n_negative": 0,
    "n_obs": 2,
    "median_day_pct": -0.030560598100515257,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 2,
    "small_n": true,
    "tickers": [
     "MIRM",
     "QGEN"
    ]
   }
  ],
  "note": "Descriptive and UNMEASURED: medians of what these names did after their news in this window, one observation per name per session. No placebo, no twins, not a signal.",
  "window_days": 10
 },
 "counts": {
  "events": 115,
  "high_impact": 20,
  "unclassified_modality": 47,
  "unresolved_ticker": 2
 },
 "pass": {
  "as_of": null,
  "date": null,
  "counts": {}
 },
 "sources": [
  {
   "key": "finnhub",
   "label": "Company news (Finnhub)"
  },
  {
   "key": "sec",
   "label": "SEC 8-K press releases (EX-99.1)"
  },
  {
   "key": "massive",
   "label": "Market-wide news (Massive)"
  },
  {
   "key": "fda_rss",
   "label": "FDA press releases"
  }
 ],
 "push": {
  "kind": "med_catalyst",
  "gate_text": "High impact = FDA approval (not tentative or generic); FDA complete response letter, refuse-to-file or rejection (not a withdrawn application); Phase 3 / Phase 2/3 / pivotal topline positive or negative (never mixed or undirected); Breakthrough Therapy designation; clinical hold placed (incl. partial); prior close ≥ $2 and 50-session median dollar volume ≥ $5M; only while the regular session has traded the news ≤ 10 minutes; not a repeat of the same kind on the name within 21 sessions; one topline push per name per session; once per event; 3 ring individually then one digest."
 }
} as unknown as MedBoard;

export const LIVE_SYMBOL_KOD = {
 "symbol": "KOD",
 "as_of": "2026-09-29T03:47:51.155886-04:00",
 "labels": {
  "measured": false,
  "status": "unmeasured",
  "setup": "pending study",
  "note": "UNMEASURED — nothing here has been measured. Events are classified by fixed word rules; moves are what the stock did, not a prediction. Setup: pending study. Not a buy or sell signal."
 },
 "events": [
  {
   "event_key": "KOD|topline_positive|2026-09-28",
   "ticker": "KOD",
   "company": "Kodiak Sciences Inc.",
   "event_type": "topline",
   "family": "trial",
   "type_dir": "topline_positive",
   "label": "Phase 3 topline positive",
   "subtype": null,
   "direction": "positive",
   "phase": "3",
   "regulator": null,
   "trials": [
    "DAYBREAK"
   ],
   "impact": "high",
   "modality": [
    "antibody_bispecific"
   ],
   "modality_primary": "antibody_bispecific",
   "areas": [
    "ophthalmology",
    "cardio_metabolic"
   ],
   "area_primary": "ophthalmology",
   "headline": "Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints With Zenkuda (Tarcocimab Tedromer) And Tabirafusp-ted (KSI-501) Showing Non-inferiority In Vision Gains For Wet Age-related Macular Degeneration Vs. Aflibercept At Year One",
   "published_at_et": "2026-09-28T02:34:12-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 1490.8,
   "session_date": "2026-09-28",
   "released": "overnight",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints With Zenkuda (Tarcocimab Tedromer) And Tabirafusp-ted (KSI-501) Showing Non-inferiority In Vision Gains For Wet Age-related Macular Degeneration Vs. Aflibercept At Year One",
     "url": "https://finnhub.io/api/news?id=12279e5c8d466ae7e482d2066b56cd971e4e89d55aed3ca019d4624c3afe9792",
     "published_et": "2026-09-28T02:34:12-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences Shares Rise After DAYBREAK Phase 3 Trial Results",
     "url": "https://finnhub.io/api/news?id=5fab98fe7bf302b2f86088faac9438c01bf0a2894cc549d72250f13383645b49",
     "published_et": "2026-09-28T07:02:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences Stock Pops 70% After Eye-Disease Drugs Pass Key Trial",
     "url": "https://finnhub.io/api/news?id=5ccc96958948303f3ebe778c27f06e16375a6d2125a6ca030aabfaf6a769fd33",
     "published_et": "2026-09-28T07:58:00-04:00"
    },
    {
     "provider": "sec",
     "source": "SEC 8-K EX-99.1",
     "title": "Zenkuda and tabirafusp-ted Meet Primary Endpoints in Pivotal DAYBREAK Trial in wAMD, with Zenkuda Demonstrating a Potential New Standard-of-Care Profile with Strong Immediacy and Sustained Clinical Effect with Majority of Patients on 24-week Dosing Interval Using Strict Treat-to-Dryness Real World",
     "url": "https://www.sec.gov/Archives/edgar/data/1468748/000119312526403481/0001193125-26-403481-index.htm",
     "published_et": "2026-09-28T08:53:56-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences stock soars on positive AMD trial data",
     "url": "https://finnhub.io/api/news?id=a9a236c29ea2d798698b4572bf4a3735177e418b42da430ee0fd5b6e0773b567",
     "published_et": "2026-09-28T09:16:20-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences Soars 141% on “Truly Impressive” Pivotal Wet AMD Trial Win",
     "url": "https://finnhub.io/api/news?id=61d3cce9e3d728976866cce5e5d9206098f9e8e5ce8c9c0954a1b994d21f731a",
     "published_et": "2026-09-28T11:21:08-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak skyrockets on positive study data for 2 eye drugs",
     "url": "https://finnhub.io/api/news?id=6576ad23bafaed889c00ee39991c9982ab0fcb1d0d8f26c375245afe1ed63dd2",
     "published_et": "2026-09-28T12:11:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences soars as Zenkuda, tabirafusp-ted hit primary endpoints in phase III wet AMD trial",
     "url": "https://finnhub.io/api/news?id=10cc69c30509e8ec23a268bf8b02e837f8e94cb6094e782760d938658e7e2c52",
     "published_et": "2026-09-28T13:04:00-04:00"
    }
   ],
   "n_sources": 8,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 32.35,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 1490.8,
     "post_session": true
    },
    "at_close": {
     "open": 61.705,
     "high": 95.77,
     "low": 60.49,
     "close": 89.92,
     "volume": 38355170.0,
     "gap_pct": 90.74188562596599,
     "day_pct": 177.95981452859348,
     "rvol": 57.07526697474234,
     "dollar_volume": 3448896886.4,
     "close_loc": 0.8341836734693879,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 32.35,
    "base_basis": "frame",
    "adv50_usd": 22726016.883526836,
    "avg_vol50": 672010.34761648,
    "pre_ret_20d_pct": -17.305725971370133,
    "market_cap": 2033179933.95
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/KOD?tab=supply",
    "timeline": "/sepa/KOD?tab=catalyst"
   }
  },
  {
   "event_key": "KOD|readout_scheduled|2026-09-25",
   "ticker": "KOD",
   "company": "Kodiak Sciences Inc.",
   "event_type": "readout_scheduled",
   "family": "scheduled",
   "type_dir": "readout_scheduled",
   "label": "Readout scheduled",
   "subtype": "scheduled",
   "direction": null,
   "phase": null,
   "regulator": null,
   "trials": [
    "DAYBREAK"
   ],
   "impact": "low",
   "modality": [
    "antibody_bispecific"
   ],
   "modality_primary": "antibody_bispecific",
   "areas": [
    "ophthalmology"
   ],
   "area_primary": "ophthalmology",
   "headline": "Kodiak Sciences To Host Webcast To Report Phase 3 DAYBREAK Topline Results For Wet AMD Candidates On September 28 At 8:30 AM Eastern Time",
   "published_at_et": "2026-09-25T14:03:55-04:00",
   "first_seen_at_et": "2026-09-29T03:24:57.574000-04:00",
   "latency_min": 5121.0,
   "session_date": "2026-09-25",
   "released": "intraday",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Kodiak Sciences To Host Webcast To Report Phase 3 DAYBREAK Topline Results For Wet AMD Candidates On September 28 At 8:30 AM Eastern Time",
     "url": "https://finnhub.io/api/news?id=c41e82eec9b1b502aecef904392dccf8e2905817dc4331d6b476508ce2805796",
     "published_et": "2026-09-25T14:03:55-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences to Present Topline Results on September 28, 2026 from DAYBREAK Pivotal Phase 3 Study of Zenkuda and KSI-501 in Patients with Wet Age-Related Macular Degeneration",
     "url": "https://finnhub.io/api/news?id=b98cb90cbb0b1204a8612eeb69b8eb609180cf893ae727f0c328ab8b47ae196f",
     "published_et": "2026-09-25T18:01:00-04:00"
    }
   ],
   "n_sources": 2,
   "push": {
    "state": "pending",
    "reason": null,
    "at_et": null
   },
   "reaction": {
    "at_detection": {
     "as_of": "2026-09-29T03:24:57.574607-04:00",
     "session": "closed",
     "price": 0.0,
     "base_close": 33.22,
     "base_basis": "frame",
     "move_pct": -100.0,
     "volume_so_far": 0.0,
     "rvol_so_far": 0.0,
     "latency_min": 5121.0,
     "post_session": true
    },
    "at_close": {
     "open": 33.03,
     "high": 33.705,
     "low": 31.0,
     "close": 32.35,
     "volume": 2277335.752434,
     "gap_pct": -0.5719446116797089,
     "day_pct": -2.618904274533407,
     "rvol": 3.5821818689150438,
     "dollar_volume": 73671811.5912399,
     "close_loc": 0.4990757855822559,
     "basis": "closed_bar"
    },
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 33.22,
    "base_basis": "frame",
    "adv50_usd": 22496969.694000877,
    "avg_vol50": 635739.8467665601,
    "pre_ret_20d_pct": -15.535214848715995,
    "market_cap": 2033179933.95
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/KOD?tab=supply",
    "timeline": "/sepa/KOD?tab=catalyst"
   }
  }
 ],
 "tracking_since": "2026-09-29"
} as unknown as MedSymbolPayload;
