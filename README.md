# Seismo

Seismo is a retrieval-augmented generation (RAG) chatbot that
explains why a brand's marketing metrics moved, with citations. It
is built on 59 of Tephra's documents from 2025, including agency
reports, change logs, Slack exports, meeting notes and tracking
documentation. Tephra is a fictional backcountry ski brand. Ask
Seismo why a metric moved, and it answers in plain language and
shows exactly which documents it used.

Live app: [seismo.nullhypothesis.ca](https://seismo.nullhypothesis.ca)

Tephra isn't a real brand. Its documents and data were created for
this project.

## Repository Structure

- `app.py`: contains the Streamlit app, with the Chat, How It Works
  and Analytics tabs.
- `src/load.py`: contains document loading for PDF, markdown and
  .txt files.
- `src/clean.py`: contains text cleaning, including PDF table
  rebuilding.
- `src/chunk.py`: contains format-aware chunking and chunk metadata.
- `src/embed.py`: contains OpenAI embeddings and the persistent
  ChromaDB store.
- `src/rewrite.py`: contains the query rewrite step.
- `src/metric_map.py`: contains the glossary and the likely causes
  behind each metric.
- `src/retrieve.py`: contains stratified retrieval, the similarity
  threshold filter and the final selection of chunks.
- `src/rerank.py`: contains the re-ranker.
- `src/generate.py`: contains the grounded prompt, moderation,
  answer generation, citations and fallback messages.
- `src/usage_log.py`: contains the usage log.
- `src/analytics.py`: contains the analytics calculations.
- `src/analytics_tab.py`: contains the Analytics tab.
- `src/themes.py`: contains question theme clustering.
- `src/how_it_works.py`: contains the How It Works tab.
- `src/tiles.py`: contains the headline number tiles.
- `src/evaluate.py`: contains the retrieval evaluation.
- `src/grade.py`: contains the answer grading.
- `src/seed_sample.py`: contains the script that builds the sample
  usage log.
- `src/peek.py` and `src/peek_pool.py`: contain debugging tools for
  cleaned pages and candidate pools.
- `data/docs/`: contains the 59 Tephra documents.
- `data/sample_usage.jsonl`: contains sample questions for the
  Analytics tab.
- `chroma_db/`: contains the persistent ChromaDB vector database.
- `eval/eval-questions.csv`: contains the 54 evaluation questions
  with expected answers and sources.
- `eval/storyline-bible.md`: contains the ground truth for every
  2025 incident.
- `eval/metrics_2024_2025.csv`, `eval/channels_2025.csv`,
  `eval/meta_split_2025.csv` and `eval/categories_2024_2025.csv`:
  contain the ground-truth numbers the documents were built from.
- `eval/results/`: contains every evaluation and grading round.
- `.streamlit/config.toml`: contains the app theme.
- `requirements.txt`: contains the Python packages and versions.
- `LICENSE`: contains the license terms.

## How It Works

### Building the Knowledge Base

1. **Document:** 59 files in 9 folders: 15 PDFs, 31 markdown files
   and 13 .txt files.
2. **Load:** each file is read into one shape: its text plus
   metadata from its file name and folder (source, title, folder,
   file type). PDFs load one document per page. Files that fail to
   load are reported and skipped, so one bad file can't stop the
   build.
3. **Clean:** PDF tables are rebuilt from text positions, so each
   value lands in the right column and cells that wrapped onto a
   second line are put back. Sentences split across lines are
   rejoined, repeated blank lines are collapsed, bullet symbols are
   standardized and extra spaces are trimmed.
4. **Chunk:** each format gets its own rule.
   - Markdown, including change logs and meeting notes: one chunk
     per `##` section. A short overview section (300 characters or
     fewer) is added to the title instead of becoming its own
     chunk.
   - Slack exports: one chunk per day.
   - .txt files, such as supplier emails: one chunk per file.
   - PDFs: split by heading, with headings carried across pages.
     Table rows are rewritten as plain-language sentences, so a
     single row can be retrieved on its own.
   - Every chunk is capped at 1,500 characters, and longer sections
     are split. There is no overlap, because chunks follow the
     document's own sections. The title and section are added to
     the top of each chunk.
   - Every chunk carries metadata: `chunk_id`, `chunk_type`,
     `source`, `title`, `section`, `folder`, `file_type`, `page`,
     `date`, `month` and `file_hash`. The result is 825 chunks.
5. **Embed:** chunks are embedded with OpenAI
   `text-embedding-3-small` in batches of 100. Each file gets a
   fingerprint from its contents and the pipeline version, so only
   new or changed files are embedded again, and chunks from deleted
   files are removed.
6. **Store:** embeddings, chunk text, chunk IDs and metadata are
   saved in a persistent ChromaDB database in `chroma_db/`. The app
   opens it once at start-up and never rebuilds it.

### Answering a Question

7. **Query:**
   - **Input check:** empty questions and questions over 500
     characters are rejected, a guardrail declines requests for
     secrets or attempts to override Seismo's rules, and OpenAI
     moderation declines harmful questions.
   - **Query rewrite:** GPT-6 Luna fixes spelling, rewrites
     follow-ups as standalone questions using the previous question,
     and expands abbreviations using a glossary.
   - **Query embedding:** the rewritten question is embedded with
     the same model as the documents.
8. **Retrieve:** semantic search with stratified retrieval builds a
   candidate pool of up to about 70 chunks from the 150 closest
   matches:
   - 30 general candidates, with at most 2 chunks per section.
   - A quota of 8 chunks for each month named in the question.
   - A quota of 2 chunks for each folder.
   - For "why" questions, a look-back to the month before, plus a
     second search for the likely causes from the metric map.

   Agency reports make up 63% of all chunks, so without these
   quotas they would crowd out the change logs and Slack threads
   where causes are usually recorded.
9. **Filter:** three thresholds, one per stage.
   - **Threshold filter:** at least one chunk must reach a
     similarity of 0.32, or the question is treated as off-topic.
   - **Re-rank floor:** candidates below a similarity of 0.25
     aren't sent to the re-ranker.
   - **Re-rank:** GPT-6 Luna scores each candidate from 0 to 3 in
     parallel batches of 24, and only chunks scoring 2 or higher
     are kept, up to the top 8. If none reach 2, Seismo says it
     couldn't find an answer and names the closest documents.
   - **Relevance tiers:** strongly relevant (0.50 and up),
     potentially relevant (0.32 and up), weakly relevant (0.25 and
     up) and irrelevant (below 0.25).
10. **Generate:** the question, the kept chunks and the system
    instructions go to GPT-6.1 Terra, and the answer streams into
    the chat. The question is never sent alone. The instructions
    tell the model to answer only from the sources, never invent
    facts, say when information isn't available, keep Seismo's
    role and voice, and treat the sources as data, not
    instructions.
11. **Cite:** the model tags each claim with its source, and the
    tags are renumbered in the order they appear. A View Sources
    panel under each answer shows, for every cited chunk, the
    document and section, the file name, page and chunk ID, the
    similarity score with its relevance tier, the cosine distance,
    the re-rank score and the retrieved text itself. A timing
    breakdown above each answer shows the latency of each step.

### Top-K and Thresholds

The usual guidance is a top-k of 3 to 5. Seismo retrieves wider and
then re-ranks down to 8, because diagnostic questions need evidence
from several documents: the metric, the cause and the timing.
Seismo kept 6 chunks until the final grading round, and raising it
to 8 cut partial answers from 12 to 9. The thresholds were tuned by
testing direct, paraphrased, misspelled and irrelevant questions,
and the threshold chart for each round is in `eval/results/`.

### Response Time

Average time per answered question, from 50 sample questions:

| Step | Seconds |
|---|---|
| Query rewrite | 1.3 |
| Query embedding and vector search | 0.3 |
| Re-rank | 2.3 |
| Generate | 2.2 |
| Total | 6.4 |

Documents are embedded once and stored, so each question only
needs one new embedding. Most of the time goes to the two model
calls that re-rank and generate.

## Evaluation

Seismo was tested on 54 questions with known answers. They include
fact, diagnosis, multi-document, red herring, seasonality and
synthesis questions, plus paraphrased, misspelled, unanswerable and
irrelevant ones.

### Retrieval

| Round | Expected Source Retrieved | Expected Sources Covered |
|---|---|---|
| First version | 91% | 76% |
| Final version | 100% | 91% |

A side-by-side test of `text-embedding-3-large` found the expected
source 96% of the time, against 94% for `text-embedding-3-small` on
the same pipeline. The final gains came from stratified retrieval
and re-ranking rather than the larger model, so the app uses the
small one.

### Answers

Every answer was graded against the answer key as correct, partial
or wrong, and checked for grounding and citations.

| Round | Answer Score | Wrong Answers | Average Answer Time |
|---|---|---|---|
| 1 | 92% | 1 | 8.3 s |
| 2 | 90% | 0 | 7.2 s |
| 3 | 89% | 0 | 6.1 s |
| 4 (final) | 92% | 0 | 5.8 s |

In the final round, 100% of answers were grounded, 98% cited the
expected source, and 100% of irrelevant and unanswerable questions
were correctly rejected.

### Required Test Questions

Question types follow the assignment's categories.

| ID | Type | Question | Retrieved | Answer | Cited | Rejected |
|---|---|---|---|---|---|---|
| Q01 | Direct | When was Tephra founded and by whom? | Yes | Correct | Yes | No |
| Q03 | Direct | How much does the Mackenzie airbag pack cost and when did it launch? | Yes | Correct | Yes | No |
| Q24 | Direct | What is the rule for event_id on Meta Purchase events? | Yes | Correct | Yes | No |
| Q49 | Paraphrased | What made our Meta retargeting fall apart in the spring? | Yes | Correct | Yes | No |
| Q50 | Paraphrased | Why didn't moving Google money into PMax over the summer bring in more sales? | Yes | Correct | Yes | No |
| Q51 | Misspelled | wen did the fissle splitbord come bak in stok? | Yes | Correct | Yes | No |
| Q23 | Multi-section | What decision was made based on the inflated September Meta numbers, and what did it cost? | Yes | Correct | Yes | No |
| Q30 | Multi-section | Why did the Fissile Meta campaign keep running after Fissile sold out? | Yes | Partial | Yes | No |
| Q53 | Irrelevant | What's a good recipe for banana bread? | n/a | Correct | n/a | Yes |
| Q54 | Irrelevant | Who won the Stanley Cup in 2024? | n/a | Correct | n/a | Yes |

### The Hardest Problem

Asked why Meta retargeting fell apart in March 2025, an early
version repeated the agency's answer: creative fatigue. The real
cause was a tracking script removed in a February 11, 2025 theme
migration, recorded in the change log and Slack. It never made it
into the candidate pool, for two reasons: agency reports crowded out
every other folder, and the cause happened a month before the month
in the question. Stratified retrieval, the look-back month and the
cause search from the metric map fixed it. Seismo now names the
removed script and explains why the creative fatigue story doesn't
hold up.

## Guardrails and Error Handling

- The OpenAI key is read from an environment variable or
  `.streamlit/secrets.toml`, never written in code, and the secrets
  file is never committed.
- Sources are fenced off and treated as data, not instructions, to
  guard against prompt injection.
- A guardrail in the input check declines requests for keys,
  passwords or Seismo's instructions, and attempts to override its
  rules, before any search runs.
- OpenAI moderation declines harmful questions.
- Each visit is limited to 15 questions, and the app to 300 a day.
  OpenAI spending is capped with a hard monthly limit.
- A missing or invalid key, an empty or missing database, OpenAI
  timeouts, rate limits, the spend limit and network errors each
  show a clear message in Seismo's voice instead of crashing.
  OpenAI calls time out after 45 seconds instead of hanging.
- If the re-ranker fails, Seismo falls back to the top chunks by
  similarity.

## Deployment

Seismo runs on Render as a web service. The OpenAI key, the
analytics password and the log folder are set as environment
variables, and usage logs are saved to a persistent disk so they
survive redeploys. The `chroma_db/` folder is committed, so the live
app uses exactly the database that was evaluated.

## Analytics

The Analytics tab logs every question, without any personal
information, and shows how questions were handled, question themes
found by clustering question embeddings with k-means, content gaps,
the most-cited documents and where the answer time goes. Themes with
fewer than 3 questions are grouped as "Other questions" for privacy,
and raw questions are behind a password.

## Limitations

- Retrieval finds the best evidence, not all of it. Questions that
  need every month aggregated, or an exhaustive list, can come back
  incomplete.
- The same model family generates and grades the answers, so the
  scores may be a little generous.
- The evaluation questions were written alongside Seismo, so the
  scores show it works on this storyline, not that it would
  generalize to any brand.
- Ask the same thing twice and the wording can change, because the
  models are not fully deterministic.

## Future Improvements

- Semantic caching, so repeated questions are answered instantly.
- Screenshot uploads, with a guard against instructions hidden in
  images.
- Clickable citations that open the cited source.

## Running It

1. Build the vector database. This only embeds new or changed
   files:
   ```
   python -m src.embed
   ```
2. Start the app:
   ```
   streamlit run app.py
   ```
3. Optional: score retrieval on the 54 questions. The last word
   names the results file:
   ```
   python -m src.evaluate text-embedding-3-small round7
   ```
4. Optional: grade full answers:
   ```
   python -m src.grade round5
   ```

## Environment

```
conda create -n seismo python=3.12
conda activate seismo
pip install -r requirements.txt
```

Add your OpenAI key and an analytics password to
`.streamlit/secrets.toml`:

```
OPENAI_API_KEY = "your-key-here"
ANALYTICS_PASSWORD = "your-password-here"
```

## License

Copyright (c) 2026 Kaiya Sjoholm. All rights reserved. This
repository is public for viewing and portfolio review only. See
`LICENSE` for details.