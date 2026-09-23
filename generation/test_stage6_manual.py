"""Manual test script for Stage 6 — Answer Generation with Citation.

PREREQUISITE: run Stage 4's test script first so the vector store is
populated:
    python -m embedding.test_stage4_manual

Then run this script:
    python -m generation.test_stage6_manual

Makes real Gemini API calls. Runs representative questions through
all 3 modes, both answer styles, and one deliberate "not found" case
(a question with no relevant content in the target document), then
prints the final answer, its sources (with confidence), and any
warning — so you can manually verify every citation actually points
to a real, correct page/section, and that "not found" is honestly
reported rather than a guessed answer.
"""

from __future__ import annotations

from generation.pipeline import answer_question

SAMPLE_MSA = "SampleServices_MSA_Contract"
SAMPLE_CUAD_SUPPLY = "CUAD_GRIDIRONBIONUTRIENTS_INC_02_05_2020-EX-10_3-SUPPLY_AGREEMENT"
SAMPLE_CUAD_STRATEGIC = "CUAD_XLITECHNOLOGIES_INC_12_02_2015-EX-10_02-STRATEGIC_ALLIANCE_A"
SAMPLE_RESEARCH = "Retrieval_Augmented_QA_Systems"
SAMPLE_ACME = "Acme_Corp_Annual_Report"

TEST_CASES = [
    {
        "label": "single_doc, full style — legal clause via general Q&A",
        "question": "What is the termination notice period?",
        "mode": "single_doc",
        "doc_ids": [SAMPLE_MSA],
        "answer_style": "full",
    },
    {
        "label": "single_doc, summary style — same question, summarized",
        "question": "What is the termination notice period?",
        "mode": "single_doc",
        "doc_ids": [SAMPLE_MSA],
        "answer_style": "summary",
    },
    {
        "label": "single_doc — image/chart question",
        "question": "What does the revenue chart show?",
        "mode": "single_doc",
        "doc_ids": [SAMPLE_ACME],
        "answer_style": "full",
    },
    {
        "label": "legal mode — exact clause quoting, verbatim expected",
        "question": "What does this contract say about indemnity?",
        "mode": "legal",
        "doc_ids": [SAMPLE_CUAD_STRATEGIC],
        "answer_style": "full",
    },
    {
        "label": "multi_doc — comparison across contracts",
        "question": "What do these contracts say about termination?",
        "mode": "multi_doc",
        "doc_ids": [SAMPLE_CUAD_SUPPLY, SAMPLE_CUAD_STRATEGIC, SAMPLE_MSA],
        "answer_style": "full",
    },
    {
        "label": "research paper question",
        "question": "What were the results of the experiments?",
        "mode": "single_doc",
        "doc_ids": [SAMPLE_RESEARCH],
        "answer_style": "summary",
    },
    {
        "label": "DELIBERATE NOT-FOUND CASE — question has no answer in this doc",
        "question": "What is the CEO's name and salary?",
        "mode": "single_doc",
        "doc_ids": [SAMPLE_MSA],
        "answer_style": "full",
    },
]


def run_case(case: dict) -> None:
    print("=" * 80)
    print(f"CASE: {case['label']}")
    print(f"  question: {case['question']}")
    print(f"  mode: {case['mode']} | style: {case['answer_style']} | doc_ids: {case['doc_ids']}")

    result = answer_question(
        case["question"], case["mode"], case["doc_ids"], case["answer_style"]
    )

    print(f"\n  ANSWER:\n  {result['answer']}\n")
    print(f"  SOURCES ({len(result['sources'])}):")
    for src in result["sources"]:
        section = src["section"] or "-"
        print(
            f"    - {src['doc_name']} | page {src['page_num']} | "
            f"section: {section} | type: {src['type']} | "
            f"confidence: {src['confidence']}"
        )

    if result["warning"]:
        print(f"\n  WARNING: {result['warning']}")


def main() -> None:
    for case in TEST_CASES:
        run_case(case)

    print("=" * 80)
    print(f"Done. Ran {len(TEST_CASES)} test case(s).")


if __name__ == "__main__":
    main()
