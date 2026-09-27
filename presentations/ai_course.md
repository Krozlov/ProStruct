# AI Course Presentation
## Distributed Protein Structure Prediction with Deep Learning

---

### Slide 1: Title
**Distributed Protein Structure Prediction**
- Deep Learning Techniques for Protein Analysis
- Week 13 Presentation
- Group: [Your Names]
- Course: Artificial Intelligence (COMP6065001)

---

### Slide 2: Problem Statement

**Problem:**
- Protein structure prediction is computationally expensive
- Traditional methods require experimental validation (X-ray, NMR)
- Need computational methods to predict functional regions

**AI Solution:**
- Use deep learning to predict binding sites from sequence
- Apply Transformer architecture (state-of-the-art in NLP)
- Distributed processing for scalability

---

### Slide 3: AI Techniques Used

**1. Transformer Architecture**
- Self-attention mechanism
- Multi-head attention
- Positional encoding
- Parallel processing

**2. Masked Language Modeling (MLM)**
- Pretraining objective
- Predict masked tokens
- Learn contextual representations

**3. Supervised Fine-tuning**
- Binary classification
- Binding site prediction
- Transfer learning from pretraining

---

### Slide 4: Transformer Architecture

**Self-Attention:**
```
Attention(Q, K, V) = softmax(QK^T / √d_k)V
```

**Multi-Head Attention:**
- Multiple attention heads in parallel
- Each head learns different relationships
- Concatenated and linearly transformed

**Positional Encoding:**
- Sinusoidal functions
- Captures sequence order
- Essential for sequence modeling

---

### Slide 5: Model Architecture Details

**Our Custom Transformer:**
- Embedding dimension: 64
- 4 attention heads, 4 layers
- Hidden dimension: 256
- Max sequence length: 1024
- Parameters: ~200K

**Vocabulary:**
- 20 amino acids
- Padding token
- Mask token
- Unknown token

---

### Slide 6: Training Pipeline

**Phase 1: MLM Pretraining**
- Objective: Predict masked tokens
- Mask 15% of positions
- Loss: Cross-entropy on masked positions
- 10 epochs with validation

**Phase 2: Fine-tuning**
- Task: Binary classification
- Binding site vs non-binding site
- Loss: Cross-entropy
- 20 epochs with validation

---

### Slide 7: MLM Pretraining

**Masking Strategy:**
- 80%: Replace with [MASK]
- 10%: Replace with random token
- 10%: Keep original

**Benefits:**
- Learns contextual representations
- No labeled data required
- Transferable to downstream tasks

**Results:**
- Validation loss decreased over epochs
- Best checkpoint saved
- Metadata logged for reproducibility

---

### Slide 8: Fine-tuning for Classification

**Task:**
- Predict binding sites (1) vs non-binding sites (0)
- Position-wise classification
- Imbalanced classes (few binding sites)

**Techniques:**
- Cross-entropy loss
- Class weighting (optional)
- Validation for early stopping

**Results:**
- [Fill in after training]
- Best checkpoint based on validation loss

---

### Slide 9: Evaluation Metrics

**ROC-AUC:**
- Area under ROC curve
- Measures ranking quality
- Robust to class imbalance

**PR-AUC:**
- Area under precision-recall curve
- Better for imbalanced data
- Focus on positive class

**Spearman Correlation:**
- Rank correlation
- For variant scoring
- Non-parametric

---

### Slide 10: Baseline Comparisons

**Random Baseline:**
- Predict random probabilities
- Establishes lower bound

**Majority Class Baseline:**
- Predict majority class
- Simple but effective baseline

**BLOSUM62 Baseline:**
- Substitution matrix scores
- Domain-specific knowledge
- Traditional method

**Our Model vs Baselines:**
- [Fill in after evaluation]

---

### Slide 11: Design Decisions

**Why Transformer?**
- State-of-the-art for sequences
- Parallelizable (faster training)
- Contextual representations
- Transfer learning capability

**Why MLM Pretraining?**
- Leverages unlabeled data
- Better initialization
- Proven in NLP (BERT)

**Why Custom Architecture?**
- Smaller model (faster)
- Sufficient for demo
- Easier to debug

---

### Slide 12: Challenges & Solutions

**Challenge 1: Limited Data**
- Only 19 real proteins
- Solution: Synthetic mutants for scale testing
- Limitation: Not biologically meaningful

**Challenge 2: Class Imbalance**
- Few binding sites
- Solution: PR-AUC metric
- Future: Class weighting, oversampling

**Challenge 3: Reproducibility**
- Randomness in training
- Solution: Fixed seeds, metadata logging

---

### Slide 13: Results

**Training Results:**
- MLM pretraining: 10 epochs
- Fine-tuning: 20 epochs
- Best validation loss: [fill in]

**Evaluation Results:**
- ROC-AUC: [fill in]
- PR-AUC: [fill in]
- Spearman r: [fill in]

**Comparison with Baselines:**
- Random: [fill in]
- Majority: [fill in]
- BLOSUM62: [fill in]

---

### Slide 14: Future Work

**Model Improvements:**
- Larger model architecture
- Ensemble methods
- Attention visualization
- Multi-task learning

**Data Improvements:**
- Larger real datasets
- Experimental validation
- Cross-species training

**Training Improvements:**
- Longer pretraining
- Learning rate scheduling
- Data augmentation

---

### Slide 15: Conclusion

**Summary:**
- Applied Transformer architecture to protein sequences
- MLM pretraining + fine-tuning pipeline
- Comprehensive evaluation with baselines
- Demonstrated feasibility of deep learning for protein analysis

**AI Techniques Demonstrated:**
- Self-attention mechanisms
- Transfer learning
- Supervised classification
- Evaluation metrics

**Code:** https://github.com/Krozlov/ProStruct

---

### Slide 16: Questions?

**Thank you!**

**Contact:** [Your email]
