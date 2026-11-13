import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePage } from '../hooks/usePage';
import Waves from '../components/common/Waves';
import '../styles/terms.css';

const SECTIONS = [
  ['s1', 'What DocSense Does'],
  ['s2', 'Eligibility and Accounts'],
  ['s3', 'Your Documents and Your Responsibilities'],
  ['s4', 'Acceptable Use'],
  ['s5', 'How Your Data Is Handled'],
  ['s6', 'AI-Generated Answers and Citations'],
  ['s7', 'Availability and Service Changes'],
  ['s8', 'Intellectual Property and Open-Source Licence'],
  ['s9', 'Disclaimer of Warranties'],
  ['s10', 'Limitation of Liability'],
  ['s11', 'Indemnification'],
  ['s12', 'Suspension and Termination'],
  ['s13', 'Changes to These Terms'],
  ['s14', 'Governing Law and Disputes'],
  ['s15', 'Statutory Rights Not Excluded'],
  ['s16', 'Force Majeure'],
  ['s17', 'General'],
];

/** "Contents" list on the left; the section being read is highlighted. */
function TermsToc({ activeId }) {
  return (
    <nav aria-label="Sections" className="tc-toc" id="tc-toc">
      <p className="tc-toc__title">Contents</p>
      <ol>
        {SECTIONS.map(([id, title]) => (
          <li key={id}>
            <a className={activeId === id ? 'is-active' : undefined} href={`#${id}`}>{title}</a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export default function Terms() {
  usePage({ page: 'terms', title: 'Terms & Conditions | DocSense', themeColor: '#D3D4C0' });
  const [activeId, setActiveId] = useState('s1');

  useEffect(() => {
    if (!('IntersectionObserver' in window)) return undefined;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) setActiveId(e.target.id); });
    }, { rootMargin: '-20% 0px -70% 0px' });
    document.querySelectorAll('.tc-section').forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <Waves p="tc" />

      <header className="tc-header">
        <Link aria-label="Back to the DocSense home page" className="tc-back" to="/#home">
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M11 6l-6 6 6 6" />
          </svg>
        </Link>
        <div className="tc-header__inner">
          <Link className="tc-brand" to="/#home">
            <img alt="" className="tc-brand__logo" height="44" src="/assets/docsense-logo.png" width="44" />
            <span className="tc-brand__name">DocSense</span>
          </Link>
        </div>
      </header>

      <main className="tc-main" id="main">
      <div className="tc-intro">
        <h1>
          Terms &amp; Conditions
        </h1>
        <p className="tc-updated">
          <strong>
            Last updated:
          </strong>
          {' '}November 2026
        </p>
        <p className="tc-lead">
          Please read these Terms &amp; Conditions (&ldquo;Terms&rdquo;) before you upload a document to, or ask a question through, DocSense (&ldquo;DocSense&rdquo;, &ldquo;the Service&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;). By using any part of the Service, you confirm that you have read and understood these Terms and agree to be bound by them. If you do not agree, do not use the Service.
        </p>
      </div>
      <div className="tc-layout">
<TermsToc activeId={activeId} />
        <div className="tc-content">
          <section className="tc-section" id="s1">
            <h2>
              <span className="tc-num">
                1
              </span>
              What DocSense Does
            </h2>
            <p>
              DocSense is a retrieval-augmented question answering (RAG) tool. You upload documents (PDF, DOCX or TXT). The Service then:
            </p>
            <ol>
              <li>
                extracts the text of each page, and uses OCR on pages that contain little or no machine-readable text;
              </li>
              <li>
                extracts embedded images and sends the non-decorative ones to an AI vision model, which writes a text description of each chart, diagram, table or photo;
              </li>
              <li>
                splits the content into chunks, each labelled with its document and page number, and converts the chunks into vector embeddings;
              </li>
              <li>
                stores the chunks and embeddings in a vector database;
              </li>
              <li>
                when you ask a question, retrieves the most relevant chunks and asks an AI language model to write an answer from those chunks only, with a citation after each statement;
              </li>
              <li>
                checks each citation against the chunks that were actually retrieved, and discards citations that do not match.
              </li>
            </ol>
            <p>
              DocSense is a research and productivity aid. It is not a lawyer, accountant, doctor, examiner or any other licensed professional.
            </p>
          </section>
          <section className="tc-section" id="s2">
            <h2>
              <span className="tc-num">
                2
              </span>
              Eligibility and Accounts
            </h2>
            <ul>
              <li>
                You must be at least 18 years old, or have the consent of a parent or guardian who accepts these Terms on your behalf.
              </li>
              <li>
                You must have the legal capacity to enter into a binding agreement.
              </li>
              <li>
                If the Service provides accounts, you are responsible for keeping your credentials confidential and for all activity under your account. Tell us promptly at{' '}
                <a href="mailto:singhanish1404@gmail.com">
                  singhanish1404@gmail.com
                </a>
                {' '}if you suspect unauthorised access.
              </li>
              <li>
                The current version of the Service may run without authentication (for example, as a local or single-user deployment). In that case, anyone who can reach the Service can use it, and you are responsible for deciding who has access to your deployment.
              </li>
            </ul>
          </section>
          <section className="tc-section" id="s3">
            <h2>
              <span className="tc-num">
                3
              </span>
              Your Documents and Your Responsibilities
            </h2>
            <p>
              You confirm that for every document you upload:
            </p>
            <ul>
              <li>
                you own it, or you have the right and permission to upload it and to have it processed as described in these Terms;
              </li>
              <li>
                uploading it does not breach any confidentiality agreement, privacy law, copyright, or other right of any third party;
              </li>
              <li>
                you have removed or have no need to protect information that you are not permitted to share with third-party AI services (see Section 5).
              </li>
            </ul>
            <p>
              Do not upload documents containing sensitive personal data (for example, government ID numbers, financial account details, health records) or confidential or privileged material unless you have assessed the risks in Section 5 and are entitled to proceed.
            </p>
          </section>
          <section className="tc-section" id="s4">
            <h2>
              <span className="tc-num">
                4
              </span>
              Acceptable Use
            </h2>
            <p>
              You agree that you will not:
            </p>
            <ul>
              <li>
                use the Service for any unlawful purpose, or in breach of any applicable law or third-party right;
              </li>
              <li>
                upload content that is malicious, infringing, defamatory, or that contains malware, or attempt to use a document to manipulate or attack the Service or its AI models (for example, prompt injection intended to extract data or bypass restrictions);
              </li>
              <li>
                attempt to gain unauthorised access to the Service, its data, other users&rsquo; documents, or connected systems;
              </li>
              <li>
                overload, scrape, or disrupt the Service, or circumvent any rate limit or quota;
              </li>
              <li>
                reverse-engineer, decompile or tamper with the Service, except to the extent the open-source licence in Section 8 allows;
              </li>
              <li>
                present DocSense output as professional advice, or as your own verified work, without checking it against the source;
              </li>
              <li>
                use the Service to engage in academic dishonesty, fraud, impersonation or misrepresentation. You are solely responsible for how you use the output.
              </li>
            </ul>
            <p>
              We may suspend or end access for anyone who breaks this section.
            </p>
          </section>
          <section className="tc-section" id="s5">
            <h2>
              <span className="tc-num">
                5
              </span>
              How Your Data Is Handled
            </h2>
            <p>
              <strong>
                5.1 What is sent to third parties.
              </strong>
              {' '}To work, the Service sends content to external AI providers. Depending on the step, this includes:
            </p>
            <div className="tc-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>
                      Purpose
                    </th>
                    <th>
                      Content sent
                    </th>
                    <th>
                      Provider type
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      Embeddings (indexing and querying)
                    </td>
                    <td>
                      Chunk text and your question
                    </td>
                    <td>
                      Google Gemini API
                    </td>
                  </tr>
                  <tr>
                    <td>
                      Image understanding
                    </td>
                    <td>
                      Extracted images from your documents
                    </td>
                    <td>
                      Google Gemini API (vision)
                    </td>
                  </tr>
                  <tr>
                    <td>
                      Answer generation
                    </td>
                    <td>
                      Your question and the retrieved chunks
                    </td>
                    <td>
                      One of several language-model providers, selected automatically, such as Groq, Cohere, OpenRouter or Google Gemini
                    </td>
                  </tr>
                  <tr>
                    <td>
                      Quality evaluation (only when the evaluation tool is run by the operator)
                    </td>
                    <td>
                      Questions, expected answers and generated answers
                    </td>
                    <td>
                      The same provider pool
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p>
              The answer provider can change from one request to the next, because the Service rotates between providers when one is slow, rate-limited or unavailable. The Service records which provider and model produced each answer.
            </p>
            <p>
              <strong>
                5.2 Third-party terms.
              </strong>
              {' '}Each provider processes the content under its own terms and privacy policy, and some providers operate free tiers that carry their own usage and data-use conditions. We do not control those providers, and we cannot guarantee how they retain or use the content they receive.
            </p>
            <p className="tc-callout">
              <strong>
                Do not upload anything you are not comfortable sending to these providers.
              </strong>
            </p>
            <p>
              <strong>
                5.3 Deletion.
              </strong>
              {' '}You can delete a document through the Service, which removes its chunks and embeddings from our vector store. Deletion does not reach content that a third-party provider has already received.
            </p>
            <p>
              <strong>
                5.4 Local processing.
              </strong>
              {' '}Page extraction, OCR, chunking, the vector search, the reranking model and the citation check run within the Service&rsquo;s own environment.
            </p>
            <p>
              <strong>
                5.5 Personal data.
              </strong>
              {' '}Where applicable, personal data is handled in line with the laws that apply to the operator, which may include the Digital Personal Data Protection Act, 2023 (India). Contact{' '}
              <a href="mailto:singhanish1404@gmail.com">
                singhanish1404@gmail.com
              </a>
              {' '}with any privacy request. If you publish a separate Privacy Policy, it forms part of these Terms.
            </p>
          </section>
          <section className="tc-section" id="s6">
            <h2>
              <span className="tc-num">
                6
              </span>
              AI-Generated Answers and Citations
            </h2>
            <p>
              <strong>
                6.1 Answers can be wrong.
              </strong>
              {' '}Language models can misread, omit, or misstate information. The Service has been tested on a fixed question set, and that testing found, among others, these behaviours:
            </p>
            <ul>
              <li>
                an answer can wrongly say that the information is not in a document when it is;
              </li>
              <li>
                an answer can be incomplete, can quote selectively, or can stop at the output length limit;
              </li>
              <li>
                a correct answer can be marked down, and an imperfect answer can be marked correct, by the automatic grader used in testing.
              </li>
            </ul>
            <p>
              <strong>
                6.2 What the citation means.
              </strong>
              {' '}A citation shows which retrieved passage and page an answer statement was drawn from. The page number comes from the stored document metadata, not from the AI&rsquo;s own text. A citation tells you where to look. It does{' '}
              <strong>
                not
              </strong>
              {' '}prove that the statement is a correct or complete reading of that passage, and it does not prove that no other relevant passage exists elsewhere in the document.
            </p>
            <p>
              <strong>
                6.3 Warnings.
              </strong>
              {' '}The Service may attach warnings to an answer, for example when the retrieved passages scored low on relevance, when no citation could be verified, or when the answer was cut off at the output limit. A missing warning does not mean an answer is correct.
            </p>
            <p>
              <strong>
                6.4 Your duty to verify.
              </strong>
              {' '}You must check every answer against the source page before you rely on it, and particularly before using it in a legal, financial, medical, academic, regulatory or business decision. The Service accepts no responsibility for decisions made on unverified output.
            </p>
            <p>
              <strong>
                6.5 Limits of reading documents.
              </strong>
              {' '}Scanned pages depend on OCR quality. Charts, tables and photos are converted to text descriptions by an AI model, which can misdescribe them or fail to name a person or object. Image descriptions are not a substitute for looking at the image.
            </p>
          </section>
          <section className="tc-section" id="s7">
            <h2>
              <span className="tc-num">
                7
              </span>
              Availability and Service Changes
            </h2>
            <p>
              DocSense depends on third-party AI services, some on free tiers, whose availability, quotas, speed and behaviour can change without notice. The Service may be slow, return errors, or be unavailable for some or all questions. We may change, suspend or discontinue any part of the Service at any time.
            </p>
          </section>
          <section className="tc-section" id="s8">
            <h2>
              <span className="tc-num">
                8
              </span>
              Intellectual Property and Open-Source Licence
            </h2>
            <ul>
              <li>
                <strong>
                  Your content.
                </strong>
                {' '}You keep all rights in the documents you upload. You give the Service a limited, temporary permission to process them as described in Section 1 and Section 5, solely to answer your questions.
              </li>
              <li>
                <strong>
                  The software.
                </strong>
                {' '}DocSense&rsquo;s source code is released under the MIT Licence. That licence, not these Terms, governs your right to copy, modify and distribute the code. Third-party components keep their own licences.
              </li>
              <li>
                <strong>
                  Output.
                </strong>
                {' '}Subject to the rights of any third party in the underlying documents, you may use the answers generated for you. We make no claim that the output is free of third-party rights.
              </li>
              <li>
                <strong>
                  Names and branding.
                </strong>
                {' '}The &ldquo;DocSense&rdquo; name and any logo are not licensed by the MIT Licence unless the operator says so in writing.
              </li>
            </ul>
          </section>
          <section className="tc-section" id="s9">
            <h2>
              <span className="tc-num">
                9
              </span>
              Disclaimer of Warranties
            </h2>
            <p className="tc-caps">
              To the maximum extent permitted by applicable law, the Service is provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo;, without warranty of any kind, express or implied, including warranties of accuracy, completeness, merchantability, fitness for a particular purpose, non-infringement, and uninterrupted or error-free operation. We do not warrant that any answer, citation, or image description is correct or complete.
            </p>
          </section>
          <section className="tc-section" id="s10">
            <h2>
              <span className="tc-num">
                10
              </span>
              Limitation of Liability
            </h2>
            <p className="tc-caps">
              To the fullest extent permitted by law, the operator of DocSense and its contributors are not liable for any indirect, incidental, special, consequential or punitive damages, or for loss of profits, revenue, data or goodwill, arising from your use of, or inability to use, the Service, including loss caused by reliance on an incorrect or incomplete answer, or by the acts or outages of a third-party AI provider. Where the Service is free, our total liability to you for any claim is limited to none. If you have paid, it is limited to the amount you paid in the 30 days before the event that gave rise to the claim.
            </p>
          </section>
          <section className="tc-section" id="s11">
            <h2>
              <span className="tc-num">
                11
              </span>
              Indemnification
            </h2>
            <p>
              You agree to indemnify and hold harmless the operator and contributors of DocSense from claims, losses and reasonable costs arising from (a) a document you upload, (b) your breach of these Terms, or (c) your breach of any law or third-party right.
            </p>
          </section>
          <section className="tc-section" id="s12">
            <h2>
              <span className="tc-num">
                12
              </span>
              Suspension and Termination
            </h2>
            <p>
              We may suspend or end your access to the Service at any time, with or without notice, for breach of these Terms or to protect the Service, its users, or its providers. You may stop using the Service at any time and delete your documents as described in Section 5.3.
            </p>
          </section>
          <section className="tc-section" id="s13">
            <h2>
              <span className="tc-num">
                13
              </span>
              Changes to These Terms
            </h2>
            <p>
              We may update these Terms. When we do, we will change the &ldquo;Last updated&rdquo; date above. Your continued use of the Service after a change means you accept the updated Terms.
            </p>
          </section>
          <section className="tc-section" id="s14">
            <h2>
              <span className="tc-num">
                14
              </span>
              Governing Law and Disputes
            </h2>
            <p>
              These Terms are governed by the laws of India. Courts located in Jamshedpur, India have exclusive jurisdiction over any dispute arising from these Terms or the Service, subject to any mandatory consumer rights that apply to you.
            </p>
          </section>
          <section className="tc-section" id="s15">
            <h2>
              <span className="tc-num">
                15
              </span>
              Statutory Rights Not Excluded
            </h2>
            <p>
              Nothing in these Terms limits any right or remedy that you have under mandatory law and that cannot lawfully be excluded, including consumer protection law. Where a provision of these Terms conflicts with such a law, the law prevails to the extent of the conflict, and the rest of these Terms continue to apply.
            </p>
          </section>
          <section className="tc-section" id="s16">
            <h2>
              <span className="tc-num">
                16
              </span>
              Force Majeure
            </h2>
            <p>
              We are not liable for a failure or delay caused by events beyond our reasonable control, including natural events, power or internet failures, government action, and outages or changes at third-party hosting, API, or AI providers.
            </p>
          </section>
          <section className="tc-section" id="s17">
            <h2>
              <span className="tc-num">
                17
              </span>
              General
            </h2>
            <ul>
              <li>
                <strong>
                  Severability.
                </strong>
                {' '}If a provision of these Terms is unenforceable, the others remain in force.
              </li>
              <li>
                <strong>
                  No waiver.
                </strong>
                {' '}Not enforcing a right does not mean we give it up.
              </li>
              <li>
                <strong>
                  Assignment.
                </strong>
                {' '}You may not transfer your rights under these Terms. The operator may assign its rights to a successor.
              </li>
              <li>
                <strong>
                  Entire agreement.
                </strong>
                {' '}These Terms, together with any Privacy Policy we publish, are the whole agreement between you and the operator about the Service.
              </li>
            </ul>
            <h3>
              Operator and Contact
            </h3>
            <p>
              DocSense is operated by Anish Singh, H. No. 51/B G.T.B.N., Shiv Singh Bagan Area, Agrico, Jamshedpur - 831009, India.
            </p>
            <p>
              <strong>
                Contact and Grievance Officer:
              </strong>
              {' '}Anish Singh,{' '}
              <a href="mailto:singhanish1404@gmail.com">
                singhanish1404@gmail.com
              </a>
              . We aim to acknowledge complaints within 48 hours and resolve them within one month.
            </p>
          </section>
          <div className="tc-end">
            <Link to="/#home" className="tc-cta">
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 12H5M11 6l-6 6 6 6" />
              </svg>
              <span>
                Back to Home
              </span>
            </Link>
          </div>
        </div>
      </div>
      </main>
    </>
  );
}
