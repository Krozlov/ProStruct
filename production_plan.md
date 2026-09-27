# Production Implementation Plan

## Issues Found in Demo
1. **Type error in model fine-tuning**: Annotations have string keys but code expects int
2. **Workers not processing tasks**: 0 completed/failed despite 100 tasks enqueued
3. **Redis version incompatibility**: Running in fallback mode (in-memory)
4. **Missing evaluation metrics**: No ROC-AUC, PR-AUC, or baseline comparisons
5. **Insufficient training**: Only 1 epoch each for pretrain/finetune

## Production Implementation Steps

### Phase 1: Fix Critical Bugs
1. Fix annotation type error in `src/model.py` collate_batch
2. Fix worker task processing logic
3. Resolve Redis compatibility or upgrade Redis
4. Add proper error handling and logging

### Phase 2: Complete Training Pipeline
1. Implement proper MLM pretraining (10+ epochs)
2. Implement proper fine-tuning (20+ epochs)
3. Add validation during training
4. Save best checkpoints based on validation metrics
5. Add learning rate scheduling

### Phase 3: Evaluation & Metrics
1. Implement ROC-AUC for binding site prediction
2. Implement PR-AUC for imbalanced classification
3. Implement Spearman correlation for variant scoring
4. Add baseline comparisons:
   - Random baseline
   - Majority class baseline
   - BLOSUM62 substitution score baseline
5. Compute metrics on real data only (exclude synthetic)
6. Generate evaluation report

### Phase 4: Reproducibility
1. Fix random seeds in all modules
2. Log all hyperparameters to config
3. Save training metadata (data hash, model version, timestamps)
4. Add version control for model checkpoints

### Phase 5: Documentation
1. Write comprehensive README with setup instructions
2. Add API documentation
3. Create user guide for running predictions
4. Document limitations explicitly
5. Add troubleshooting guide

### Phase 6: Testing
1. Add unit tests for data pipeline
2. Add unit tests for model components
3. Integration tests for queue system
4. End-to-end test with small dataset
5. Performance benchmarks

### Phase 7: Deployment
1. Create Docker container
2. Add systemd service files
3. Create deployment scripts
4. Add monitoring/alerting
5. Backup and recovery procedures

## Priority Order
1. Phase 1 (Critical bugs) - MUST FIX
2. Phase 2 (Training) - HIGH
3. Phase 3 (Evaluation) - HIGH
4. Phase 4 (Reproducibility) - MEDIUM
5. Phase 5 (Documentation) - MEDIUM
6. Phase 6 (Testing) - LOW
7. Phase 7 (Deployment) - LOW
