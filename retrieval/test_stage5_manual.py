"""Manual test script for Stage 5 — Retrieval & Re-ranking.

PREREQUISITE: run Stage 4's test script first so the vector store is
populated:
    python -m embedding.test_stage4_manual

Then run this script:
    python -m retrieval.test_stage5_manual

Runs a handful of representative questions through all three modes
(single_doc, multi_doc, legal) against the already-embedded sample
documents, printing the top reranked chunks with their page numbers
and scores, so you can manually verify the right chunk/page comes
back for each question.
"""

from __future__ import annotations

from retrieval.pipeline import retrieve_and_rerank

SAMPLE_MSA = "SampleServices_MSA_Contract"
SAMPLE_CUAD_SUPPLY = "CUAD_GRIDIRONBIONUTRIENTS_INC_02_05_2020-EX-10_3-SUPPLY_AGREEMENT"
SAMPLE_CUAD_STRATEGIC = "CUAD_XLITECHNOLOGIES_INC_12_02_2015-EX-10_02-STRATEGIC_ALLIANCE_A"
SAMPLE_RESEARCH = "Retrieval_Augmented_QA_Systems"
SAMPLE_ACME = "Acme_Corp_Annual_Report"

TEST_CASES = [
    {
        "label": "single_doc — legal clause lookup by content, general mode",
        "question": "What is the termination notice period?",
        "mode": "single_doc",
        "doc_ids": [SAMPLE_MSA],
        "expected_page_hint": 3,  # Section 4.2 Termination for Convenience
    },
    {
        "label": "single_doc — image/chart question",
        "question": "What does the revenue chart show?",
        "mode": "single_doc",
        "doc_ids": [SAMPLE_ACME],
        "expected_page_hint": 2,
    },
    {
        "label": "single_doc — research paper content",
        "question": "What chunking approaches were evaluated?",
        "mode": "single_doc",
        "doc_ids": [SAMPLE_RESEARCH],
        "expected_page_hint": 3,  # Methodology
    },
    {
        "label": "legal — exact clause mode on a CUAD contract",
        "question": "What does this contract say about termination?",
        "mode": "legal",
        "doc_ids": [SAMPLE_CUAD_SUPPLY],
        "expected_page_hint": 3,  # "2. Term and Termination" per Stage 2 test output
    },
    {
        "label": "legal — indemnity clause on a different CUAD contract",
        "question": "What does this contract say about indemnity?",
        "mode": "legal",
        "doc_ids": [SAMPLE_CUAD_STRATEGIC],
        "expected_page_hint": 4,  # "9. INDEMNITY" per Stage 2 test output
    },
    {
        "label": "multi_doc — comparison across two legal contracts",
        "question": "What do these contracts say about termination?",
        "mode": "multi_doc",
        "doc_ids": [SAMPLE_CUAD_SUPPLY, SAMPLE_CUAD_STRATEGIC, SAMPLE_MSA],
        "expected_page_hint": None,  # multiple valid sources expected
    },
]


def run_case(case: dict) -> None:
    print("=" * 80)
    print(f"CASE: {case['label']}")
    print(f"  question: {case['question']}")
    print(f"  mode: {case['mode']} | doc_ids: {case['doc_ids']}")

    results = retrieve_and_rerank(case["question"], case["mode"], case["doc_ids"])

    if not results:
        print("  NO RESULTS — nothing retrieved for this question/mode/doc_ids.")
        return

    for i, chunk in enumerate(results):
        preview = chunk["text"][:100].replace("\n", " ")
        print(
            f"  [{i}] {chunk['doc_name']} | page {chunk['page_num']} | "
            f"section: {chunk.get('section') or '-'} | type: {chunk['type']} | "
            f"rerank_score: {chunk['rerank_score']:.4f}"
        )
        print(f"       \"{preview}\"")

    top_page = results[0]["page_num"]
    hint = case.get("expected_page_hint")
    if hint is not None:
        match = "OK" if top_page == hint else "CHECK"
        print(f"  [{match}] top result page={top_page}, expected_page_hint={hint}")


def main() -> None:
    for case in TEST_CASES:
        run_case(case)

    print("=" * 80)
    print(f"Done. Ran {len(TEST_CASES)} test case(s).")


if __name__ == "__main__":
    main()
