# Distributed Protein Structure/Effect Prediction Pipeline — Plan

## Decisions locked in
- **Comp-bio scope**: both binding-site prediction AND variant effect prediction
- **Workers**: multiple Python processes on one machine (simplest distributed simulation)
- **Dataset scale**: ~500 sequences for the demo/load-test

## Important constraint discovered
This sandbox's network allows PyPI and GitHub, but **blocks direct access to
UniProt, NCBI/ClinVar, RCSB PDB, and Hugging Face**. That rules out live bulk
API pulls and downloading pretrained ESM2 weights.

**Workaround (honest, not faked):**
- **Real data core**: ~19 genuine, fully-annotated UniProt/SwissProt records
  (real sequences + real binding/active-site/variant annotations), sourced from
  Biopython's official bundled test corpus — these are actual UniProt flat
  files, not synthetic.
- **Synthetic scale-up**: additional sequences generated as point-mutated
  derivatives of the real ones, clearly tagged `synthetic` in the dataset, used
  only to stress-test the queue/scheduler at ~500-sequence scale — never mixed
  into evaluation metrics.
- **Model**: since Hugging Face is unreachable, use the "small custom model"
  option from the original spec — a compact Transformer trained from scratch
  (masked-language-modeling pretraining, then fine-tuned head), instead of
  pretrained ESM2.
- Data-loader code is still written against the real UniProt/ClinVar REST APIs
  so it works unmodified in an environment with open network access.

## Architecture

1. **Data pipeline** (`src/data_pipeline.py`)
   - Parse real SwissProt records → per-residue binding/active-site labels
   - Generate tagged synthetic mutants for scale
   - Output: clean train/eval JSON + a 500-sequence demo batch

2. **Model** (`src/model.py`)
   - Small Transformer encoder (custom, few M params)
   - Pretrain via masked-language-modeling on protein sequences
   - Fine-tune head for binding-site residue classification
   - Zero-shot-style variant scoring via masked-marginal log-likelihood

3. **Distributed task queue** (`src/queue_system.py`, `workers/worker.py`)
   - Redis-backed queue (mini-Celery, built from scratch)
   - Length-aware load balancing (long sequences → less-loaded workers)
   - Retries with exponential backoff, dead-letter queue
   - Worker heartbeats, failure detection
   - Result aggregation into SQLite

4. **Dashboard** (`dashboard/`)
   - FastAPI + WebSocket backend
   - Live throughput, per-worker utilization, queue depth, retries
   - Table of predicted binding sites / variant scores

## Methodology & evaluation protocol

- **Splits**: split at the protein level (not residue/variant level) into
  train/val/test, so no residues or mutants from the same protein appear in
  more than one split. Real records and their synthetic mutant derivatives
  always stay together in the same split — never separated across
  train/test — to prevent leakage.
- **Real vs. synthetic separation**: all evaluation metrics are computed on
  real-data only. Synthetic mutants are excluded from every reported metric
  and used solely to load-test the queue/scheduler's throughput and
  load-balancing behavior.
- **Baselines**: report at least two baselines alongside the model —
  (1) majority-class / random baseline, (2) a simple heuristic baseline
  (e.g. BLOSUM62 substitution score or amino-acid conservation frequency) —
  so the custom model's lift is actually demonstrated, not assumed.
- **Metrics**: since binding/active-site residues are rare (class imbalance),
  report ROC-AUC and PR-AUC, not just accuracy. For variant scoring, report
  correlation/ranking metrics (e.g. Spearman) against the heuristic proxy
  labels, not a single pass/fail number.
- **Reproducibility**: fixed random seeds, a single versioned config file for
  all hyperparameters, and logged run metadata (data version, model version,
  commit-like hash) saved alongside results.
- **Limitations section (explicit, in the final writeup)**:
  - Real annotated dataset is small (~19 proteins) — results demonstrate the
    pipeline works correctly on real data, not statistically robust
    biological conclusions.
  - No genuine ClinVar clinical labels were available (network-restricted);
    "pathogenicity" scoring uses a documented heuristic proxy (mutations at
    annotated active/binding sites treated as more likely deleterious), not
    real clinical ground truth.
  - Synthetic mutants are for systems load-testing only and carry no
    biological ground truth.

## Build order
1. ~~Data pipeline (real + tagged synthetic)~~ ✅ COMPLETED
2. ~~Model (pretrain + fine-tune, small/fast)~~ ✅ COMPLETED
3. ~~Task queue + scheduler~~ ✅ COMPLETED
4. ~~Workers wired to the model~~ ✅ COMPLETED
5. ~~Dashboard wired to live queue state~~ ✅ COMPLETED
6. ~~End-to-end demo script~~ ✅ COMPLETED

## Stack
Python, PyTorch (CPU), Redis, FastAPI, SQLite, vanilla JS/Chart.js frontend.

## Implementation Status
### Core Implementation ✅ COMPLETED
- ✅ Data pipeline (`src/data_pipeline.py`)
- ✅ Model (`src/model.py`)
- ✅ Task queue system (`src/queue_system.py`)
- ✅ Workers (`workers/worker.py`)
- ✅ Dashboard (`dashboard/app.py`, `dashboard/index.html`)
- ✅ End-to-end demo script (`demo.py`)
- ✅ Configuration (`config.yaml`)
- ✅ Dependencies (`requirements.txt`)

### Course Deliverables - TODO
#### 1. Research Methodology (COMP6705001)
- ❌ Literature review on protein structure prediction & distributed ML
- ❌ 25-page LaTeX research paper (IEEE two-column format)
- ✅ Statistical analysis with baseline comparisons

#### 2. Computational Biology (COMP6705001)
- ✅ Proposal slides (Session 7) - `presentations/compbio_proposal.md`
- ✅ Milestone slides (Session 10) - `presentations/compbio_milestone.md`
- ✅ Final presentation with live demo (Session 13) - `presentations/compbio_final.md`
- ✅ 4-6 page IEEE format report - `reports/compbio_report.md`

#### 3. AI Course (COMP6065001)
- ✅ Presentation emphasizing AI techniques (Week 13) - `presentations/ai_course.md`

#### 4. Distributed Systems (COMP6705001)
- ✅ Presentation emphasizing distributed principles (Week 13) - `presentations/distributed_systems.md`

### Core Improvements Needed
- ✅ Proper training (10+ epochs pretrain, 20+ epochs finetune)
- ✅ Validation during training
- ✅ Baseline comparisons (random, majority, BLOSUM62)
- ✅ Evaluation metrics (ROC-AUC, PR-AUC, Spearman correlation)
- ✅ Reproducibility (fixed seeds, metadata logging)

## Step-by-Step Execution Plan

### Step 1: Fix Reproducibility ✅ COMPLETED
- ✅ Add fixed random seeds to all modules
- ✅ Add metadata logging for training runs

### Step 2: Implement Proper Training with Validation ✅ COMPLETED
- ✅ Implement proper MLM pretraining (10+ epochs)
- ✅ Implement proper fine-tuning (20+ epochs)
- ✅ Add validation during training
- ✅ Save best checkpoints

### Step 3: Add Evaluation Metrics ✅ COMPLETED
- ✅ Implement ROC-AUC for binding site prediction
- ✅ Implement PR-AUC for imbalanced classification
- ✅ Implement Spearman correlation for variant scoring

### Step 4: Implement Baseline Comparisons ✅ COMPLETED
- ✅ Random baseline
- ✅ Majority class baseline
- ✅ BLOSUM62 substitution score baseline

### Step 5: Course Deliverables ✅ COMPLETED (except Research Methodology)
- ✅ Computational Biology Proposal slides (Session 7)
- ✅ Computational Biology Milestone slides (Session 10)
- ✅ Computational Biology Final presentation (Session 13)
- ✅ Computational Biology 4-6 page report
- ✅ AI Course presentation
- ✅ Distributed Systems presentation
- ❌ Literature review for research paper (PENDING)
- ❌ 25-page LaTeX research paper (PENDING)