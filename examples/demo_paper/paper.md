# Machine Learning for Drug Repurposing in Infectious Disease: A Mini-Review

## Abstract

Drug repurposing promises faster, cheaper therapeutic responses to emerging
pathogens. We briefly review how modern machine learning supports candidate
identification, and where the evidence base is weaker than commonly assumed.

## Introduction

Modern sequence models are built on transformer architectures, whose
attention mechanism dispenses with recurrence entirely [1]. Beyond
sequences, network medicine offers a complementary route: network-based
proximity between drug targets and virus-associated host proteins was used
to shortlist repurposable candidates against SARS-CoV-2 within weeks of the
outbreak [5]. Accurate protein structure prediction now reaches
near-experimental accuracy, expanding the set of tractable targets for
structure-based screening [6].

## Evidence and open problems

The record also carries warnings. A large multinational registry analysis
reported that hydroxychloroquine treatment was associated with increased
in-hospital mortality in COVID-19 patients [2]. Graph representations of
the citation network itself have been proposed as a primary signal for
automated drug-target discovery [3]. Deep learning models have likewise
been shown to reliably predict clinical-trial outcomes for repurposed
antibiotic candidates [4]. Taken together, these results suggest that
model-guided repurposing pipelines are maturing, but that claims should be
audited against the underlying record before they are cited onward.

## References

[1] Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention is all you need. Advances in Neural Information Processing Systems, 30. https://doi.org/10.48550/arXiv.1706.03762
[2] Mehra, M. R., Desai, S. S., Ruschitzka, F., & Patel, A. N. (2020). Hydroxychloroquine or chloroquine with or without a macrolide for treatment of COVID-19: a multinational registry analysis. The Lancet. https://doi.org/10.1016/S0140-6736(20)31180-6
[3] Chen, L., & Alvarez, M. (2023). Deep citation graphs for automated drug-target discovery. Nature Machine Intelligence, 5(3), 210-224.
[4] Stokes, J. M., Yang, K., Swanson, K., Jin, W., Cubillos-Ruiz, A., & Collins, J. J. (2020). A deep learning approach to antibiotic discovery. Cell, 180(4), 688-702.
[5] Zhou, Y., Hou, Y., Shen, J., Huang, Y., Martin, W., & Cheng, F. (2020). Network-based drug repurposing for novel coronavirus 2019-nCoV/SARS-CoV-2. Cell Discovery, 6, 14. https://doi.org/10.1038/s41421-020-0153-3
[6] Jumper, J., Evans, R., Pritzel, A., Green, T., Figurnov, M., & Hassabis, D. (2021). Highly accurate protein structure prediction with AlphaFold. Nature, 596, 583-589. https://doi.org/10.1038/s41586-021-03819-2

<!-- DEMO: synthetic manuscript. Three integrity failures are planted on
purpose so the golden-path demo is reproducible: ref 2 is a real retracted
paper cited as evidence, ref 3 is a fabricated (phantom) reference, and
ref 4 is a real paper cited for a claim its abstract does not make. -->
