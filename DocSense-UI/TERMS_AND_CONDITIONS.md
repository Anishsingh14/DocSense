<!--
BEFORE PUBLISHING, replace every [BRACKETED] placeholder:
  [CONTACT EMAIL], [GRIEVANCE OFFICER NAME], [CITY], [AMOUNT]
Also confirm section 5 (data handling) still matches how you deploy DocSense, and have a
lawyer review the whole file before you rely on it. This is a template, not legal advice.
-->

# Terms & Conditions

**DocSense: Document Question Answering with Page Citations**
**Last updated:** November 2026

Please read these Terms & Conditions ("Terms") before you upload a document to, or ask a question through, DocSense ("DocSense", "the Service", "we", "us"). By using any part of the Service, you confirm that you have read and understood these Terms and agree to be bound by them. If you do not agree, do not use the Service.

---

## 1. What DocSense Does

DocSense is a retrieval-augmented question answering (RAG) tool. You upload documents (PDF, DOCX or TXT). The Service then:

1. extracts the text of each page, and uses OCR on pages that contain little or no machine-readable text;
2. extracts embedded images and sends the non-decorative ones to an AI vision model, which writes a text description of each chart, diagram, table or photo;
3. splits the content into chunks, each labelled with its document and page number, and converts the chunks into vector embeddings;
4. stores the chunks and embeddings in a vector database;
5. when you ask a question, retrieves the most relevant chunks and asks an AI language model to write an answer from those chunks only, with a citation after each statement;
6. checks each citation against the chunks that were actually retrieved, and discards citations that do not match.

DocSense is a research and productivity aid. It is not a lawyer, accountant, doctor, examiner or any other licensed professional.

## 2. Eligibility and Accounts

- You must be at least 18 years old, or have the consent of a parent or guardian who accepts these Terms on your behalf.
- You must have the legal capacity to enter into a binding agreement.
- If the Service provides accounts, you are responsible for keeping your credentials confidential and for all activity under your account. Tell us promptly at [CONTACT EMAIL] if you suspect unauthorised access.
- The current version of the Service may run without authentication (for example, as a local or single-user deployment). In that case, anyone who can reach the Service can use it, and you are responsible for deciding who has access to your deployment.

## 3. Your Documents and Your Responsibilities

You confirm that for every document you upload:

- you own it, or you have the right and permission to upload it and to have it processed as described in these Terms;
- uploading it does not breach any confidentiality agreement, privacy law, copyright, or other right of any third party;
- you have removed or have no need to protect information that you are not permitted to share with third-party AI services (see Section 5).

Do not upload documents containing sensitive personal data (for example, government ID numbers, financial account details, health records) or confidential or privileged material unless you have assessed the risks in Section 5 and are entitled to proceed.

## 4. Acceptable Use

You agree that you will not:

- use the Service for any unlawful purpose, or in breach of any applicable law or third-party right;
- upload content that is malicious, infringing, defamatory, or that contains malware, or attempt to use a document to manipulate or attack the Service or its AI models (for example, prompt injection intended to extract data or bypass restrictions);
- attempt to gain unauthorised access to the Service, its data, other users' documents, or connected systems;
- overload, scrape, or disrupt the Service, or circumvent any rate limit or quota;
- reverse-engineer, decompile or tamper with the Service, except to the extent the open-source licence in Section 8 allows;
- present DocSense output as professional advice, or as your own verified work, without checking it against the source;
- use the Service to engage in academic dishonesty, fraud, impersonation or misrepresentation. You are solely responsible for how you use the output.

We may suspend or end access for anyone who breaks this section.

## 5. How Your Data Is Handled

**5.1 What is sent to third parties.** To work, the Service sends content to external AI providers. Depending on the step, this includes:

| Purpose | Content sent | Provider type |
|---|---|---|
| Embeddings (indexing and querying) | Chunk text and your question | Google Gemini API |
| Image understanding | Extracted images from your documents | Google Gemini API (vision) |
| Answer generation | Your question and the retrieved chunks | One of several language-model providers, selected automatically, such as Groq, Cohere, OpenRouter or Google Gemini |
| Quality evaluation (only when the evaluation tool is run by the operator) | Questions, expected answers and generated answers | The same provider pool |

The answer provider can change from one request to the next, because the Service rotates between providers when one is slow, rate-limited or unavailable. The Service records which provider and model produced each answer.

**5.2 Third-party terms.** Each provider processes the content under its own terms and privacy policy, and some providers operate free tiers that carry their own usage and data-use conditions. We do not control those providers, and we cannot guarantee how they retain or use the content they receive. **Do not upload anything you are not comfortable sending to these providers.**

**5.3 Deletion.** You can delete a document through the Service, which removes its chunks and embeddings from our vector store. Deletion does not reach content that a third-party provider has already received.

**5.4 Local processing.** Page extraction, OCR, chunking, the vector search, the reranking model and the citation check run within the Service's own environment.

**5.5 Personal data.** Where applicable, personal data is handled in line with the laws that apply to the operator, which may include the Digital Personal Data Protection Act, 2023 (India). Contact [CONTACT EMAIL] with any privacy request. If you publish a separate Privacy Policy, it forms part of these Terms.

## 6. AI-Generated Answers and Citations

**6.1 Answers can be wrong.** Language models can misread, omit, or misstate information. The Service has been tested on a fixed question set, and that testing found, among others, these behaviours:

- an answer can wrongly say that the information is not in a document when it is;
- an answer can be incomplete, can quote selectively, or can stop at the output length limit;
- a correct answer can be marked down, and an imperfect answer can be marked correct, by the automatic grader used in testing.

**6.2 What the citation means.** A citation shows which retrieved passage and page an answer statement was drawn from. The page number comes from the stored document metadata, not from the AI's own text. A citation tells you where to look. It does **not** prove that the statement is a correct or complete reading of that passage, and it does not prove that no other relevant passage exists elsewhere in the document.

**6.3 Warnings.** The Service may attach warnings to an answer, for example when the retrieved passages scored low on relevance, when no citation could be verified, or when the answer was cut off at the output limit. A missing warning does not mean an answer is correct.

**6.4 Your duty to verify.** You must check every answer against the source page before you rely on it, and particularly before using it in a legal, financial, medical, academic, regulatory or business decision. The Service accepts no responsibility for decisions made on unverified output.

**6.5 Limits of reading documents.** Scanned pages depend on OCR quality. Charts, tables and photos are converted to text descriptions by an AI model, which can misdescribe them or fail to name a person or object. Image descriptions are not a substitute for looking at the image.

## 7. Availability and Service Changes

DocSense depends on third-party AI services, some on free tiers, whose availability, quotas, speed and behaviour can change without notice. The Service may be slow, return errors, or be unavailable for some or all questions. We may change, suspend or discontinue any part of the Service at any time.

## 8. Intellectual Property and Open-Source Licence

- **Your content.** You keep all rights in the documents you upload. You give the Service a limited, temporary permission to process them as described in Section 1 and Section 5, solely to answer your questions.
- **The software.** DocSense's source code is released under the MIT Licence. That licence, not these Terms, governs your right to copy, modify and distribute the code. Third-party components keep their own licences.
- **Output.** Subject to the rights of any third party in the underlying documents, you may use the answers generated for you. We make no claim that the output is free of third-party rights.
- **Names and branding.** The "DocSense" name and any logo are not licensed by the MIT Licence unless the operator says so in writing.

## 9. Disclaimer of Warranties

TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING WARRANTIES OF ACCURACY, COMPLETENESS, MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, AND UNINTERRUPTED OR ERROR-FREE OPERATION. WE DO NOT WARRANT THAT ANY ANSWER, CITATION, OR IMAGE DESCRIPTION IS CORRECT OR COMPLETE.

## 10. Limitation of Liability

TO THE FULLEST EXTENT PERMITTED BY LAW, THE OPERATOR OF DOCSENSE AND ITS CONTRIBUTORS ARE NOT LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL OR PUNITIVE DAMAGES, OR FOR LOSS OF PROFITS, REVENUE, DATA OR GOODWILL, ARISING FROM YOUR USE OF, OR INABILITY TO USE, THE SERVICE, INCLUDING LOSS CAUSED BY RELIANCE ON AN INCORRECT OR INCOMPLETE ANSWER, OR BY THE ACTS OR OUTAGES OF A THIRD-PARTY AI PROVIDER. WHERE THE SERVICE IS FREE, OUR TOTAL LIABILITY TO YOU FOR ANY CLAIM IS LIMITED TO [AMOUNT, e.g. ₹500 / $10]. IF YOU HAVE PAID, IT IS LIMITED TO THE AMOUNT YOU PAID IN THE 30 DAYS BEFORE THE EVENT THAT GAVE RISE TO THE CLAIM.

## 11. Indemnification

You agree to indemnify and hold harmless the operator and contributors of DocSense from claims, losses and reasonable costs arising from (a) a document you upload, (b) your breach of these Terms, or (c) your breach of any law or third-party right.

## 12. Suspension and Termination

We may suspend or end your access to the Service at any time, with or without notice, for breach of these Terms or to protect the Service, its users, or its providers. You may stop using the Service at any time and delete your documents as described in Section 5.3.

## 13. Changes to These Terms

We may update these Terms. When we do, we will change the "Last updated" date above. Your continued use of the Service after a change means you accept the updated Terms.

## 14. Governing Law and Disputes

These Terms are governed by the laws of India. Courts located in [CITY], India have exclusive jurisdiction over any dispute arising from these Terms or the Service, subject to any mandatory consumer rights that apply to you.

## 15. Statutory Rights Not Excluded

Nothing in these Terms limits any right or remedy that you have under mandatory law and that cannot lawfully be excluded, including consumer protection law. Where a provision of these Terms conflicts with such a law, the law prevails to the extent of the conflict, and the rest of these Terms continue to apply.

## 16. Force Majeure

We are not liable for a failure or delay caused by events beyond our reasonable control, including natural events, power or internet failures, government action, and outages or changes at third-party hosting, API, or AI providers.

## 17. General

- **Severability.** If a provision of these Terms is unenforceable, the others remain in force.
- **No waiver.** Not enforcing a right does not mean we give it up.
- **Assignment.** You may not transfer your rights under these Terms. The operator may assign its rights to a successor.
- **Entire agreement.** These Terms, together with any Privacy Policy we publish, are the whole agreement between you and the operator about the Service.

## 18. Operator and Contact

DocSense is operated by Anish Singh, H. No. 51/B G.T.B.N., Shiv Singh Bagan Area, Agrico, Jamshedpur - 831009, India.

**Contact and Grievance Officer:** [GRIEVANCE OFFICER NAME], [CONTACT EMAIL]. We aim to acknowledge complaints within 48 hours and resolve them within one month.
