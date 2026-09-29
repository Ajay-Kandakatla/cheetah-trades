/* 🧬 Medical catalysts — REAL payload captured 2026-09-29 ~02:50 ET from the branch API
 * (GET /catalysts/medical?days=7 and /catalysts/medical/KOD) on a scratch DB after one branch
 * pass over real sources (Finnhub ×362 roster names, SEC 8-K EX-99.1, Massive market-wide,
 * FDA press RSS). Trimmed to 10 of the 44 events; everything else (labels, taxonomy, the
 * FULL served roll-up over all 44, counts, pass, push, sources) is verbatim.
 *
 * CAVEAT: WP-CLS (classify.py / taxonomy.py) had not landed when this was captured; the pass
 * used the scratch stand-in over the spec's reference harness (medcat_rev/rules_v2_final.py),
 * so served labels / modality / area keys are the stand-in's. Re-capture once classify.py lands.
 * push.state is `pending` on every row (dry run: nothing claimed, nothing sent) and `pass` is
 * empty (a dry run records no pass).
 */
import type { MedBoard, MedSymbolPayload } from '../medicalCatalysts';

export const LIVE_BOARD = {
 "as_of": "2026-09-29T02:50:56.854129-04:00",
 "window_days": 7,
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
    "label": "fda approval",
    "family": "fda",
    "emoji": "x"
   },
   {
    "key": "fda_crl",
    "label": "fda crl",
    "family": "fda",
    "emoji": "x"
   },
   {
    "key": "fda_revoked",
    "label": "fda revoked",
    "family": "fda",
    "emoji": "x"
   },
   {
    "key": "adcom",
    "label": "adcom",
    "family": "fda",
    "emoji": "x"
   },
   {
    "key": "topline",
    "label": "topline",
    "family": "trial",
    "emoji": "x"
   },
   {
    "key": "conference_data",
    "label": "conference data",
    "family": "conference",
    "emoji": "x"
   },
   {
    "key": "designation",
    "label": "designation",
    "family": "regulatory",
    "emoji": "x"
   },
   {
    "key": "regulatory_filing",
    "label": "regulatory filing",
    "family": "regulatory",
    "emoji": "x"
   },
   {
    "key": "pdufa",
    "label": "pdufa",
    "family": "regulatory",
    "emoji": "x"
   },
   {
    "key": "exus_approval",
    "label": "exus approval",
    "family": "regulatory",
    "emoji": "x"
   },
   {
    "key": "clinical_hold",
    "label": "clinical hold",
    "family": "hold",
    "emoji": "x"
   },
   {
    "key": "safety",
    "label": "safety",
    "family": "hold",
    "emoji": "x"
   },
   {
    "key": "deal",
    "label": "deal",
    "family": "deal",
    "emoji": "x"
   },
   {
    "key": "financing",
    "label": "financing",
    "family": "financing",
    "emoji": "x"
   },
   {
    "key": "readout_scheduled",
    "label": "readout scheduled",
    "family": "scheduled",
    "emoji": "x"
   },
   {
    "key": "trial_milestone",
    "label": "trial milestone",
    "family": "scheduled",
    "emoji": "x"
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
    "key": "antibody_bispecific",
    "label": "Antibodies & bispecifics"
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
  "high_impact_text": "FDA approval (not tentative/generic), CRL / refuse-to-file / rejection, Phase 3 / pivotal topline positive or negative, Breakthrough Therapy designation, clinical hold placed"
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
    "unclassified"
   ],
   "modality_primary": "unclassified",
   "areas": [
    "rare_disease"
   ],
   "area_primary": "rare_disease",
   "headline": "FDA Approves First Treatment for MCT8 Deficiency",
   "published_at_et": "2026-09-28T17:43:18-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
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
   "event_key": "HCM|regulatory_filing|2026-09-29",
   "ticker": "HCM",
   "company": "HUTCHMED (China) Ltd",
   "event_type": "regulatory_filing",
   "family": "regulatory",
   "type_dir": "regulatory_filing",
   "label": "regulatory_filing",
   "subtype": "submitted",
   "direction": null,
   "phase": null,
   "regulator": null,
   "trials": [],
   "impact": "low",
   "modality": [
    "small_molecule"
   ],
   "modality_primary": "small_molecule",
   "areas": [
    "oncology"
   ],
   "area_primary": "oncology",
   "headline": "HUTCHMED Announces Submission of US NDA for ORPATHYS® plus TAGRISSO® in MET-Driven EGFR-Mutated Lung Cancer",
   "published_at_et": "2026-09-28T20:00:00-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 389.2,
   "session_date": "2026-09-29",
   "released": "overnight",
   "sources": [
    {
     "provider": "massive",
     "source": "GlobeNewswire Inc.",
     "title": "HUTCHMED Announces Submission of US NDA for ORPATHYS® plus TAGRISSO® in MET-Driven EGFR-Mutated Lung Cancer",
     "url": "https://www.globenewswire.com/news-release/2026/09/29/3370345/0/en/hutchmed-announces-submission-of-us-nda-for-orpathys-plus-tagrisso-in-met-driven-egfr-mutated-lung-cancer.html",
     "published_et": "2026-09-28T20:00:00-04:00"
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
     "as_of": "2026-09-28T16:00:00.091117-04:00",
     "session": "closed",
     "price": 14.13,
     "base_close": 14.13,
     "base_basis": "frame",
     "move_pct": 0.0,
     "volume_so_far": 29670.0,
     "rvol_so_far": 0.4076978520954721,
     "latency_min": 389.2,
     "post_session": false
    },
    "at_close": null,
    "fwd": {
     "ret_5d_pct": null,
     "ret_21d_pct": null,
     "drift_5d_pct": null,
     "matured_5d": false,
     "matured_21d": false
    }
   },
   "liquidity": {
    "base_close": 14.13,
    "base_basis": "frame",
    "adv50_usd": 664573.9752355649,
    "avg_vol50": 72774.48200304,
    "pre_ret_20d_pct": 14.135702746365109,
    "market_cap": null
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/HCM?tab=supply",
    "timeline": "/sepa/HCM?tab=catalyst"
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
    "ophthalmology"
   ],
   "area_primary": "ophthalmology",
   "headline": "Zenkuda and tabirafusp-ted Meet Primary Endpoints in Pivotal DAYBREAK Trial in wAMD, with Zenkuda Demonstrating a Potential New Standard-of-Care Profile with Strong Immediacy and Sustained Clinical Effect with Majority of Patients on 24-week Dosing Interval Using Strict Treat-to-Dryness Real World",
   "published_at_et": "2026-09-28T02:34:12-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 1055.2,
   "session_date": "2026-09-28",
   "released": "premarket",
   "sources": [
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
     "title": "Kodiak Sciences soars as Zenkuda, tabirafusp-ted hit primary endpoints in phase III wet AMD trial",
     "url": "https://finnhub.io/api/news?id=10cc69c30509e8ec23a268bf8b02e837f8e94cb6094e782760d938658e7e2c52",
     "published_et": "2026-09-28T13:04:00-04:00"
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
     "title": "Kodiak Sciences Soars 141% on “Truly Impressive” Pivotal Wet AMD Trial Win",
     "url": "https://finnhub.io/api/news?id=61d3cce9e3d728976866cce5e5d9206098f9e8e5ce8c9c0954a1b994d21f731a",
     "published_et": "2026-09-28T11:21:08-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences Stock Pops 70% After Eye-Disease Drugs Pass Key Trial",
     "url": "https://finnhub.io/api/news?id=5ccc96958948303f3ebe778c27f06e16375a6d2125a6ca030aabfaf6a769fd33",
     "published_et": "2026-09-28T07:58:00-04:00"
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
     "source": "Benzinga",
     "title": "Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints With Zenkuda (Tarcocimab Tedromer) And Tabirafusp-ted (KSI-501) Showing Non-inferiority In Vision Gains For Wet Age-related Macular Degeneration Vs. Aflibercept At Year One",
     "url": "https://finnhub.io/api/news?id=12279e5c8d466ae7e482d2066b56cd971e4e89d55aed3ca019d4624c3afe9792",
     "published_et": "2026-09-28T02:34:12-04:00"
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
     "as_of": "2026-09-28T19:59:11.816388-04:00",
     "session": "closed",
     "price": 88.19,
     "base_close": 32.35,
     "base_basis": "frame",
     "move_pct": 172.61205564142193,
     "volume_so_far": 38556342.0,
     "rvol_so_far": 57.37462546038699,
     "latency_min": 1055.2,
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
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 944.2,
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
     "as_of": "2026-09-28T16:50:33.107973-04:00",
     "session": "closed",
     "price": 88.5,
     "base_close": 89.7,
     "base_basis": "frame",
     "move_pct": -1.3377926421404673,
     "volume_so_far": 1268393.0,
     "rvol_so_far": 1.8907300052377976,
     "latency_min": 944.2,
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
   "headline": "Mirum Pharmaceuticals Announces Primary Endpoint Met in Phase 3 AZURE-1 Study of Brelovitug in Chronic Hepatitis Delta Virus",
   "published_at_et": "2026-09-28T04:08:17-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 1109.2,
   "session_date": "2026-09-28",
   "released": "premarket",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Mirum Pharmaceuticals Announces Primary Endpoint Met in Phase 3 AZURE-1 Study of Brelovitug in Chronic Hepatitis Delta Virus",
     "url": "https://finnhub.io/api/news?id=d484b9aaa8c3c9dfabd287b1351753636ae5d95a8143e723887c554a6ef259fc",
     "published_et": "2026-09-28T08:00:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Mirum Pharma's Brelovitug Meets Phase 3 Primary Endpoint In AZURE-1 Study For Chronic Hepatitis Delta Virus",
     "url": "https://finnhub.io/api/news?id=2aebadde21d8da2fd265e8dde36ce2b88eaaa2f4f1da5935469109e1943394d8",
     "published_et": "2026-09-28T04:08:17-04:00"
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
     "as_of": "2026-09-28T16:50:33.107973-04:00",
     "session": "closed",
     "price": 88.5,
     "base_close": 89.7,
     "base_basis": "frame",
     "move_pct": -1.3377926421404673,
     "volume_so_far": 1268393.0,
     "rvol_so_far": 1.8907300052377976,
     "latency_min": 1109.2,
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
   "event_key": "KOD|readout_scheduled|2026-09-28",
   "ticker": "KOD",
   "company": "Kodiak Sciences Inc.",
   "event_type": "readout_scheduled",
   "family": "scheduled",
   "type_dir": "readout_scheduled",
   "label": "readout_scheduled",
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
   "headline": "Kodiak Sciences to Present Topline Results on September 28, 2026 from DAYBREAK Pivotal Phase 3 Study of Zenkuda and KSI-501 in Patients with Wet Age-Related Macular Degeneration",
   "published_at_et": "2026-09-25T14:03:55-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 4828.2,
   "session_date": "2026-09-28",
   "released": "afterhours",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences to Present Topline Results on September 28, 2026 from DAYBREAK Pivotal Phase 3 Study of Zenkuda and KSI-501 in Patients with Wet Age-Related Macular Degeneration",
     "url": "https://finnhub.io/api/news?id=b98cb90cbb0b1204a8612eeb69b8eb609180cf893ae727f0c328ab8b47ae196f",
     "published_et": "2026-09-25T18:01:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Kodiak Sciences To Host Webcast To Report Phase 3 DAYBREAK Topline Results For Wet AMD Candidates On September 28 At 8:30 AM Eastern Time",
     "url": "https://finnhub.io/api/news?id=c41e82eec9b1b502aecef904392dccf8e2905817dc4331d6b476508ce2805796",
     "published_et": "2026-09-25T14:03:55-04:00"
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
     "as_of": "2026-09-28T19:59:11.816388-04:00",
     "session": "closed",
     "price": 88.19,
     "base_close": 32.35,
     "base_basis": "frame",
     "move_pct": 172.61205564142193,
     "volume_so_far": 38556342.0,
     "rvol_so_far": 57.37462546038699,
     "latency_min": 4828.2,
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
   "headline": "MediciNova Announces Topline Results from  MN-001-NATG-202 Clinical Trial of MN-001 (Tipelukast)",
   "published_at_et": "2026-09-28T06:00:00-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 1229.2,
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
     "as_of": "2026-09-28T19:50:57.538660-04:00",
     "session": "closed",
     "price": 1.99,
     "base_close": 2.58,
     "base_basis": "frame",
     "move_pct": -22.868217054263575,
     "volume_so_far": 1617992.0,
     "rvol_so_far": 4.804697239003257,
     "latency_min": 1229.2,
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
   "event_key": "ACAD|topline_negative|2026-09-25",
   "ticker": "ACAD",
   "company": "ACADIA Pharmaceuticals Inc.",
   "event_type": "topline",
   "family": "trial",
   "type_dir": "topline_negative",
   "label": "Phase 2 topline negative",
   "subtype": null,
   "direction": "negative",
   "phase": "2",
   "regulator": null,
   "trials": [],
   "impact": "low",
   "modality": [
    "unclassified"
   ],
   "modality_primary": "unclassified",
   "areas": [
    "neurology"
   ],
   "area_primary": "neurology",
   "headline": "Bears Chase Down Acadia Pharma After Surprise Alzheimer's Setback",
   "published_at_et": "2026-09-24T03:04:01-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 6375.6,
   "session_date": "2026-09-25",
   "released": "afterhours",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Bears Chase Down Acadia Pharma After Surprise Alzheimer's Setback",
     "url": "https://finnhub.io/api/news?id=fe4f8c7d0d267f9297f84d14f47865a4bae46e87e1c7cbc5e34abe185a76d9c8",
     "published_et": "2026-09-24T16:13:34-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Acadia Pharmaceuticals Shares Fall After RADIANT Phase 2 Study Misses Primary Endpoint",
     "url": "https://finnhub.io/api/news?id=3abeed4fc6f65059df5bc6cd9419bf5ddd8375c808e37413fdd52af3b91ad51d",
     "published_et": "2026-09-24T09:56:18-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Acadia’s Remlifanserin Advances Toward Phase 3 In Alzheimer’s Psychosis Despite Narrow Miss On Primary Endpoint",
     "url": "https://finnhub.io/api/news?id=931a925d3f6cde5d1d28178b5eadd4d2c58ae728fdbb4c1003954ab8b31f8f96",
     "published_et": "2026-09-24T03:04:01-04:00"
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
     "as_of": "2026-09-28T19:41:01.135945-04:00",
     "session": "closed",
     "price": 20.2511,
     "base_close": 22.18,
     "base_basis": "frame",
     "move_pct": -8.696573489630289,
     "volume_so_far": 3522828.0,
     "rvol_so_far": 2.043147288631137,
     "latency_min": 6375.6,
     "post_session": true
    },
    "at_close": {
     "open": 22.21,
     "high": 22.21,
     "low": 20.61,
     "close": 20.68,
     "volume": 3364113.766734,
     "gap_pct": 0.13525698827774324,
     "day_pct": -6.762849413886385,
     "rvol": 1.9510972210818276,
     "dollar_volume": 69569872.69605912,
     "close_loc": 0.043750000000000136,
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
    "base_close": 22.18,
    "base_basis": "frame",
    "adv50_usd": 38792656.214576066,
    "avg_vol50": 1724216.3693250995,
    "pre_ret_20d_pct": -25.016903313049355,
    "market_cap": 3821736389.24
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/ACAD?tab=supply",
    "timeline": "/sepa/ACAD?tab=catalyst"
   }
  },
  {
   "event_key": "ARCT|topline_unknown|2026-09-25",
   "ticker": "ARCT",
   "company": "Arcturus Therapeutics Holdings Inc.",
   "event_type": "topline",
   "family": "trial",
   "type_dir": "topline_unknown",
   "label": "Topline results (direction not stated)",
   "subtype": null,
   "direction": "unknown",
   "phase": "2",
   "regulator": null,
   "trials": [],
   "impact": "low",
   "modality": [
    "mrna"
   ],
   "modality_primary": "mrna",
   "areas": [
    "unclassified"
   ],
   "area_primary": "unclassified",
   "headline": "Arcturus Highlights ARCT-810 Phase II Data, Unveils Next-Gen OTC Therapy Platform",
   "published_at_et": "2026-09-24T23:02:09-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 5967.0,
   "session_date": "2026-09-25",
   "released": "overnight",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Arcturus Highlights ARCT-810 Phase II Data, Unveils Next-Gen OTC Therapy Platform",
     "url": "https://finnhub.io/api/news?id=92510c8d11b611acdf636c5628a5c1255631395d728b36755df442c2bc0c7f27",
     "published_et": "2026-09-24T23:02:09-04:00"
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
     "as_of": "2026-09-28T18:44:23.040824-04:00",
     "session": "closed",
     "price": 14.41,
     "base_close": 14.12,
     "base_basis": "frame",
     "move_pct": 2.053824362606238,
     "volume_so_far": 825022.0,
     "rvol_so_far": 0.8109505917358312,
     "latency_min": 5967.0,
     "post_session": true
    },
    "at_close": {
     "open": 14.34,
     "high": 14.48,
     "low": 13.3005,
     "close": 13.85,
     "volume": 629878.507546,
     "gap_pct": 1.5580736543909346,
     "day_pct": -1.912181303116145,
     "rvol": 0.6191354271960152,
     "dollar_volume": 8723817.329512099,
     "close_loc": 0.465875370919881,
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
    "base_close": 14.12,
    "base_basis": "frame",
    "adv50_usd": 8633778.3726499,
    "avg_vol50": 1017351.7454793998,
    "pre_ret_20d_pct": -10.802274162981684,
    "market_cap": 401333734.28
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/ARCT?tab=supply",
    "timeline": "/sepa/ARCT?tab=catalyst"
   }
  },
  {
   "event_key": "VTGN|conference_data|2026-09-24",
   "ticker": "VTGN",
   "company": "Vistagen Therapeutics, Inc.",
   "event_type": "conference_data",
   "family": "conference",
   "type_dir": "conference_data",
   "label": "conference_data",
   "subtype": "presented",
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
   "headline": "Vistagen Reports Positive Findings Supporting Fasedienol’s Potential in Very Severe Social Anxiety Disorder Exploratory research results presented at Psych Congress 2026 in New Orleans Full poster presentation can be found on “Publications” section of Company’s website SOUTH SAN FRANCISCO,",
   "published_at_et": "2026-09-24T07:05:32-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 6923.6,
   "session_date": "2026-09-24",
   "released": "premarket",
   "sources": [
    {
     "provider": "sec",
     "source": "SEC 8-K EX-99.1",
     "title": "Vistagen Reports Positive Findings Supporting Fasedienol’s Potential in Very Severe Social Anxiety Disorder Exploratory research results presented at Psych Congress 2026 in New Orleans Full poster presentation can be found on “Publications” section of Company’s website SOUTH SAN FRANCISCO,",
     "url": "https://www.sec.gov/Archives/edgar/data/1411685/000162828026063316/0001628280-26-063316-index.htm",
     "published_et": "2026-09-24T07:05:32-04:00"
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
     "as_of": "2026-09-28T19:59:11.646650-04:00",
     "session": "closed",
     "price": 0.283,
     "base_close": 0.3684,
     "base_basis": "frame",
     "move_pct": -23.181324647122704,
     "volume_so_far": 6050120.0,
     "rvol_so_far": 0.40791383872098896,
     "latency_min": 6923.6,
     "post_session": true
    },
    "at_close": {
     "open": 0.349,
     "high": 0.3599,
     "low": 0.2701,
     "close": 0.295,
     "volume": 20471724.041784,
     "gap_pct": -5.266015200868623,
     "day_pct": -19.92399565689469,
     "rvol": 1.3802535386274768,
     "dollar_volume": 6039158.59232628,
     "close_loc": 0.2772828507795098,
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
    "base_close": 0.3684,
    "base_basis": "frame",
    "adv50_usd": 170240.23839437065,
    "avg_vol50": 14831857.67604774,
    "pre_ret_20d_pct": 48.30917874396135,
    "market_cap": 16348454.0124
   },
   "dilutive": null,
   "links": {
    "supply": "/sepa/VTGN?tab=supply",
    "timeline": "/sepa/VTGN?tab=catalyst"
   }
  }
 ],
 "rollup": {
  "by_modality": [
   {
    "key": "unclassified",
    "label": "unclassified",
    "n_events": 27,
    "n_high": 7,
    "n_positive": 6,
    "n_negative": 3,
    "n_obs": 24,
    "median_day_pct": -0.8247894067436867,
    "n_day": 22,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 23,
    "small_n": false,
    "tickers": [
     "ABBV",
     "ACAD",
     "ARVN",
     "CGEM",
     "CLYD",
     "CRL",
     "GRAL",
     "IMVT"
    ]
   },
   {
    "key": "antibody_bispecific",
    "label": "Antibodies & bispecifics",
    "n_events": 8,
    "n_high": 2,
    "n_positive": 3,
    "n_negative": 0,
    "n_obs": 6,
    "median_day_pct": 0.6477265768939477,
    "n_day": 6,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 6,
    "small_n": false,
    "tickers": [
     "BHVN",
     "CCCC",
     "HCM",
     "KOD",
     "MIRM",
     "MRK"
    ]
   },
   {
    "key": "small_molecule",
    "label": "Small molecule",
    "n_events": 8,
    "n_high": 2,
    "n_positive": 2,
    "n_negative": 0,
    "n_obs": 8,
    "median_day_pct": 1.3629842180774787,
    "n_day": 7,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 7,
    "small_n": false,
    "tickers": [
     "CGEM",
     "COGT",
     "HCM",
     "LLY",
     "MRK",
     "MSLE",
     "PALI"
    ]
   },
   {
    "key": "gene_editing",
    "label": "Gene editing",
    "n_events": 1,
    "n_high": 1,
    "n_positive": 1,
    "n_negative": 0,
    "n_obs": 1,
    "median_day_pct": -5.537459283387625,
    "n_day": 1,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 1,
    "small_n": true,
    "tickers": [
     "PRME"
    ]
   },
   {
    "key": "mrna",
    "label": "mRNA",
    "n_events": 1,
    "n_high": 0,
    "n_positive": 0,
    "n_negative": 0,
    "n_obs": 1,
    "median_day_pct": -1.912181303116145,
    "n_day": 1,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 1,
    "small_n": true,
    "tickers": [
     "ARCT"
    ]
   }
  ],
  "by_area": [
   {
    "key": "unclassified",
    "label": "unclassified",
    "n_events": 18,
    "n_high": 6,
    "n_positive": 5,
    "n_negative": 1,
    "n_obs": 18,
    "median_day_pct": -0.5434044287460971,
    "n_day": 17,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 16,
    "small_n": false,
    "tickers": [
     "ARCT",
     "CLYD",
     "COGT",
     "CRL",
     "GRAL",
     "INCY",
     "KYTX",
     "LLY"
    ]
   },
   {
    "key": "oncology",
    "label": "oncology",
    "n_events": 13,
    "n_high": 1,
    "n_positive": 1,
    "n_negative": 0,
    "n_obs": 13,
    "median_day_pct": -0.030246000806560813,
    "n_day": 12,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 11,
    "small_n": false,
    "tickers": [
     "ARVN",
     "BHVN",
     "CCCC",
     "CGEM",
     "HCM",
     "LNTH",
     "MRK",
     "PFE"
    ]
   },
   {
    "key": "rare_disease",
    "label": "rare disease",
    "n_events": 5,
    "n_high": 2,
    "n_positive": 2,
    "n_negative": 1,
    "n_obs": 4,
    "median_day_pct": -0.6846143802665461,
    "n_day": 4,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 4,
    "small_n": true,
    "tickers": [
     "BHVN",
     "IMVT",
     "MIRM",
     "SRPT"
    ]
   },
   {
    "key": "neurology",
    "label": "neurology",
    "n_events": 4,
    "n_high": 1,
    "n_positive": 1,
    "n_negative": 1,
    "n_obs": 3,
    "median_day_pct": -1.5978337438040668,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 3,
    "small_n": true,
    "tickers": [
     "ABBV",
     "ACAD",
     "MSLE"
    ]
   },
   {
    "key": "ophthalmology",
    "label": "ophthalmology",
    "n_events": 3,
    "n_high": 1,
    "n_positive": 2,
    "n_negative": 0,
    "n_obs": 2,
    "median_day_pct": 88.94614173215194,
    "n_day": 2,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 2,
    "small_n": true,
    "tickers": [
     "KOD",
     "MRK"
    ]
   },
   {
    "key": "infectious_disease",
    "label": "infectious disease",
    "n_events": 2,
    "n_high": 1,
    "n_positive": 1,
    "n_negative": 0,
    "n_obs": 1,
    "median_day_pct": -1.9397993311036865,
    "n_day": 1,
    "median_ret_5d_pct": null,
    "n_5d": 0,
    "median_ret_21d_pct": null,
    "n_21d": 0,
    "n_tickers": 1,
    "small_n": true,
    "tickers": [
     "MIRM"
    ]
   }
  ],
  "note": "Descriptive and UNMEASURED: medians of what these names did after their news in this window, one observation per name per session. No placebo, no twins, not a signal.",
  "window_days": 7
 },
 "counts": {
  "events": 44,
  "high_impact": 12,
  "unclassified_modality": 27,
  "unresolved_ticker": 1
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
  "gate_text": "FDA approval (not tentative/generic), CRL / refuse-to-file / rejection, Phase 3 / pivotal topline positive or negative, Breakthrough Therapy designation, clinical hold placed; prior close ≥ $2 and 50-session median dollar volume ≥ $5M; only while the regular session has traded the news ≤ 10 minutes; not a repeat of the same kind on the name within 21 sessions; one topline push per name per session; once per event; 3 ring individually then one digest."
 }
} as unknown as MedBoard;

export const LIVE_SYMBOL_KOD = {
 "symbol": "KOD",
 "as_of": "2026-09-29T02:50:56.966113-04:00",
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
    "ophthalmology"
   ],
   "area_primary": "ophthalmology",
   "headline": "Zenkuda and tabirafusp-ted Meet Primary Endpoints in Pivotal DAYBREAK Trial in wAMD, with Zenkuda Demonstrating a Potential New Standard-of-Care Profile with Strong Immediacy and Sustained Clinical Effect with Majority of Patients on 24-week Dosing Interval Using Strict Treat-to-Dryness Real World",
   "published_at_et": "2026-09-28T02:34:12-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 1055.2,
   "session_date": "2026-09-28",
   "released": "premarket",
   "sources": [
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
     "title": "Kodiak Sciences soars as Zenkuda, tabirafusp-ted hit primary endpoints in phase III wet AMD trial",
     "url": "https://finnhub.io/api/news?id=10cc69c30509e8ec23a268bf8b02e837f8e94cb6094e782760d938658e7e2c52",
     "published_et": "2026-09-28T13:04:00-04:00"
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
     "title": "Kodiak Sciences Soars 141% on “Truly Impressive” Pivotal Wet AMD Trial Win",
     "url": "https://finnhub.io/api/news?id=61d3cce9e3d728976866cce5e5d9206098f9e8e5ce8c9c0954a1b994d21f731a",
     "published_et": "2026-09-28T11:21:08-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences Stock Pops 70% After Eye-Disease Drugs Pass Key Trial",
     "url": "https://finnhub.io/api/news?id=5ccc96958948303f3ebe778c27f06e16375a6d2125a6ca030aabfaf6a769fd33",
     "published_et": "2026-09-28T07:58:00-04:00"
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
     "source": "Benzinga",
     "title": "Kodiak Sciences Says Phase 3 DAYBREAK Study Met Primary Endpoints With Zenkuda (Tarcocimab Tedromer) And Tabirafusp-ted (KSI-501) Showing Non-inferiority In Vision Gains For Wet Age-related Macular Degeneration Vs. Aflibercept At Year One",
     "url": "https://finnhub.io/api/news?id=12279e5c8d466ae7e482d2066b56cd971e4e89d55aed3ca019d4624c3afe9792",
     "published_et": "2026-09-28T02:34:12-04:00"
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
     "as_of": "2026-09-28T19:59:11.816388-04:00",
     "session": "closed",
     "price": 88.19,
     "base_close": 32.35,
     "base_basis": "frame",
     "move_pct": 172.61205564142193,
     "volume_so_far": 38556342.0,
     "rvol_so_far": 57.37462546038699,
     "latency_min": 1055.2,
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
   "event_key": "KOD|readout_scheduled|2026-09-28",
   "ticker": "KOD",
   "company": "Kodiak Sciences Inc.",
   "event_type": "readout_scheduled",
   "family": "scheduled",
   "type_dir": "readout_scheduled",
   "label": "readout_scheduled",
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
   "headline": "Kodiak Sciences to Present Topline Results on September 28, 2026 from DAYBREAK Pivotal Phase 3 Study of Zenkuda and KSI-501 in Patients with Wet Age-Related Macular Degeneration",
   "published_at_et": "2026-09-25T14:03:55-04:00",
   "first_seen_at_et": "2026-09-29T02:29:10.267000-04:00",
   "latency_min": 4828.2,
   "session_date": "2026-09-28",
   "released": "afterhours",
   "sources": [
    {
     "provider": "finnhub",
     "source": "Yahoo",
     "title": "Kodiak Sciences to Present Topline Results on September 28, 2026 from DAYBREAK Pivotal Phase 3 Study of Zenkuda and KSI-501 in Patients with Wet Age-Related Macular Degeneration",
     "url": "https://finnhub.io/api/news?id=b98cb90cbb0b1204a8612eeb69b8eb609180cf893ae727f0c328ab8b47ae196f",
     "published_et": "2026-09-25T18:01:00-04:00"
    },
    {
     "provider": "finnhub",
     "source": "Benzinga",
     "title": "Kodiak Sciences To Host Webcast To Report Phase 3 DAYBREAK Topline Results For Wet AMD Candidates On September 28 At 8:30 AM Eastern Time",
     "url": "https://finnhub.io/api/news?id=c41e82eec9b1b502aecef904392dccf8e2905817dc4331d6b476508ce2805796",
     "published_et": "2026-09-25T14:03:55-04:00"
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
     "as_of": "2026-09-28T19:59:11.816388-04:00",
     "session": "closed",
     "price": 88.19,
     "base_close": 32.35,
     "base_basis": "frame",
     "move_pct": 172.61205564142193,
     "volume_so_far": 38556342.0,
     "rvol_so_far": 57.37462546038699,
     "latency_min": 4828.2,
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
  }
 ],
 "tracking_since": "2026-09-29"
} as unknown as MedSymbolPayload;
