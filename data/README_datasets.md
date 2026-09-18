# Sample Datasets for DocIQ — What's Included

## 1. Three real legal contracts (from CUAD)
- `CUAD_XLITECHNOLOGIES_INC_..._STRATEGIC_ALLIANCE_A.pdf`
- `CUAD_GRIDIRONBIONUTRIENTS_INC_..._SUPPLY_AGREEMENT.pdf`
- `CUAD_TRANSMONTAIGNEPARTNERSLLC_..._SERVICES_AGREEM.pdf`

These are real, publicly filed commercial contracts, sourced from the **Contract
Understanding Atticus Dataset (CUAD v1)**, curated by The Atticus Project.
License: **CC BY 4.0** (free to use, attribution: The Atticus Project — CUAD).
Homepage: https://www.atticusprojectai.org/cuad

Each contract was paginated into a clean PDF (5–6 pages each) so you can test
Stage 1 (ingestion/parsing) against real-world legal language, not just
synthetic text.

## 2. cuad_sample_eval.json
17 real, expert-verified question/answer pairs pulled directly from CUAD's
own clause-level annotations (Document Name, Parties, Governing Law,
Termination for Convenience, Exclusivity, etc.), with the **expected_page**
already computed to match the PDF pagination above.

This file is ready to drop into `evaluation/eval_dataset.json` as your
starting point — no manual transcription needed for these entries. Format:

```json
{
  "doc_id": "CUAD_GRIDIRONBIONUTRIENTS_INC_02_05_2020-EX-10_3-SUPPLY_AGREEMENT",
  "mode": "legal",
  "clause_category": "Termination For Convenience",
  "question": "What does this contract say about termination for convenience?",
  "expected_answer": "Either Party may terminate this Agreement at any time prior ...",
  "expected_page": 3
}
```

## 3. Where to get the rest (not bundled — too large/no benefit to bulk-downloading)

| Dataset | Use | Link |
|---|---|---|
| Full CUAD (510 contracts) | More legal test docs if you want a bigger eval set later | https://www.atticusprojectai.org/cuad |
| SEC EDGAR 10-K filings | Real financial reports for general/financial mode | https://www.sec.gov/edgar/search/ |
| arXiv papers | Real research papers for multi-doc comparison mode | https://arxiv.org |
| DocVQA | Chart/image Q&A pairs for evaluating Stage 3 (image analysis) | https://www.docvqa.org |
| FinQA / TAT-QA | Financial table/chart QA benchmark | search "FinQA dataset GitHub" |

For these, just grab 2-3 individual files manually when you need them —
downloading the full corpora isn't necessary for a V1 evaluation set.
