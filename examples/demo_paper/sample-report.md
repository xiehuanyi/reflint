# RefLint audit — Machine Learning for Drug Repurposing in Infectious Disease: A Mini-Review

*Generated 2026-08-30 22:47 UTC by RefLint (Strands Agents SDK + Gemini · Crossref · OpenAlex).*

**Summary:** The audit of the manuscript revealed significant citation integrity issues, including one phantom reference ([3]), one retracted study cited without qualification ([2]), and one unsupported claim where the cited paper's abstract does not discuss clinical trial outcomes ([6], claim C6).

## References

| Ref | Title | Verdict | DOI |
|---|---|---|---|
| [1] | Attention is all you need | **OK** | [10.65215/2q58a426](https://doi.org/10.65215/2q58a426) |
| [2] | Hydroxychloroquine or chloroquine with or without a macrolide for treatment of COVID-19: a multinational registry analysis | **RETRACTED** | [10.1016/s0140-6736(20)31180-6](https://doi.org/10.1016/s0140-6736(20)31180-6) |
| [3] | Deep citation graphs for automated drug-target discovery | **PHANTOM** | — |
| [4] | A deep learning approach to antibiotic discovery | **OK** | [10.1016/j.cell.2020.01.021](https://doi.org/10.1016/j.cell.2020.01.021) |
| [5] | Network-based drug repurposing for novel coronavirus 2019-nCoV/SARS-CoV-2 | **OK** | [10.1038/s41421-020-0153-3](https://doi.org/10.1038/s41421-020-0153-3) |
| [6] | Highly accurate protein structure prediction with AlphaFold | **OK** | [10.1038/s41586-021-03819-2](https://doi.org/10.1038/s41586-021-03819-2) |

## Findings

### R002 · RETRACTED — cited work has been retracted

**Where:** [2] — Hydroxychloroquine or chloroquine with or without a macrolide for treatment of COVID-19: a multinational registry analysis

The record explicitly indicates that this article has been retracted (is_retracted: true), with 1251 citations prior to/following retraction.

> RETRACTED: Hydroxychloroquine or chloroquine with or without a macrolide for treatment of COVID-19: a multinational registry analysis

DOI: https://doi.org/10.1016/s0140-6736(20)31180-6

### R001 · PHANTOM — reference not found in the scholarly record

**Where:** [3] — Deep citation graphs for automated drug-target discovery

No matching publication was found in Crossref or OpenAlex. The reference appears to be a hallucinated source.

### R005 · UNVERIFIABLE — could not be checked against the record

**Where:** C4 → [2] — A large multinational registry analysis reported that hydroxychloroquine treatment was associated with increased in-hospital mortality in COVID-19 patients [2].

The provided abstract text cuts off before presenting the findings regarding the association between hydroxychloroquine treatment and in-hospital mortality.

> no relevant line

### R005 · UNVERIFIABLE — could not be checked against the record

**Where:** C5 → [3] — Graph representations of the citation network itself have been proposed as a primary signal for automated drug-target discovery [3].

no abstract available in the record for this reference

### R003 · UNSUPPORTED — source does not support the claim

**Where:** C6 → [4] — Deep learning models have likewise been shown to reliably predict clinical-trial outcomes for repurposed antibiotic candidates [4].

The abstract describes using deep learning to predict molecules with antibacterial activity and testing them in murine (mouse) models, but it does not mention predicting clinical-trial outcomes.

> no relevant line


## Claim-by-claim verdicts

| Claim | Ref | Verdict | Why |
|---|---|---|---|
| C1: Modern sequence models are built on transformer architectures, whose attention m | [1] | **supported** | The abstract explicitly states that the Transformer architecture is based solely on attention mechanisms, dispensing wit |
| C2: Beyond sequences, network medicine offers a complementary route: network-based p | [5] | **supported** | The abstract confirms that network proximity between drug targets and host proteins was used to prioritize (shortlist) r |
| C3: Accurate protein structure prediction now reaches near-experimental accuracy, ex | [6] | **supported** | The abstract states that AlphaFold achieves accuracy competitive with experimental structures, supporting the claim that |
| C4: A large multinational registry analysis reported that hydroxychloroquine treatme | [2] | **unverifiable** | The provided abstract text cuts off before presenting the findings regarding the association between hydroxychloroquine  |
| C5: Graph representations of the citation network itself have been proposed as a pri | [3] | **unverifiable** | no abstract available in the record for this reference |
| C6: Deep learning models have likewise been shown to reliably predict clinical-trial | [4] | **unsupported** | The abstract describes using deep learning to predict molecules with antibacterial activity and testing them in murine ( |

## Recommended actions

1. Remove reference [3] or replace it with a genuine, peer-reviewed source on citation graph analysis for drug discovery.
1. Explicitly acknowledge the retraction of reference [2] if it is retained as a case study, or replace it with valid post-retraction systematic reviews/meta-analyses.
1. Revise or replace reference [4] for claim C6, as the cited Stokes et al. paper focuses on discovering antibacterial molecules via deep learning and testing them in murine models, not predicting clinical trial outcomes.
