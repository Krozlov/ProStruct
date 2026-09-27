"""
Evaluation metrics for ProStruct.
Implements ROC-AUC, PR-AUC, and Spearman correlation for model evaluation.
"""

import numpy as np
from typing import List, Dict, Tuple
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve, precision_recall_curve
from scipy.stats import spearmanr
import json


class EvaluationMetrics:
    """Compute and store evaluation metrics."""
    
    def __init__(self):
        self.metrics = {}
    
    def compute_roc_auc(self, y_true: List[int], y_scores: List[float]) -> Dict[str, float]:
        """
        Compute ROC-AUC for binary classification.
        
        Args:
            y_true: Ground truth labels (0 or 1)
            y_scores: Predicted probabilities
            
        Returns:
            Dictionary with ROC-AUC and related metrics
        """
        y_true = np.array(y_true)
        y_scores = np.array(y_scores)
        
        # Handle edge cases
        if len(np.unique(y_true)) < 2:
            return {'roc_auc': 0.0, 'error': 'Only one class in y_true'}
        
        roc_auc = roc_auc_score(y_true, y_scores)
        fpr, tpr, thresholds = roc_curve(y_true, y_scores)
        
        return {
            'roc_auc': float(roc_auc),
            'fpr': fpr.tolist(),
            'tpr': tpr.tolist(),
            'thresholds': thresholds.tolist()
        }
    
    def compute_pr_auc(self, y_true: List[int], y_scores: List[float]) -> Dict[str, float]:
        """
        Compute Precision-Recall AUC for imbalanced classification.
        
        Args:
            y_true: Ground truth labels (0 or 1)
            y_scores: Predicted probabilities
            
        Returns:
            Dictionary with PR-AUC and related metrics
        """
        y_true = np.array(y_true)
        y_scores = np.array(y_scores)
        
        # Handle edge cases
        if len(np.unique(y_true)) < 2:
            return {'pr_auc': 0.0, 'error': 'Only one class in y_true'}
        
        pr_auc = average_precision_score(y_true, y_scores)
        precision, recall, thresholds = precision_recall_curve(y_true, y_scores)
        
        return {
            'pr_auc': float(pr_auc),
            'precision': precision.tolist(),
            'recall': recall.tolist(),
            'thresholds': thresholds.tolist()
        }
    
    def compute_spearman(self, y_true: List[float], y_pred: List[float]) -> Dict[str, float]:
        """
        Compute Spearman rank correlation for variant scoring.
        
        Args:
            y_true: Ground truth scores
            y_pred: Predicted scores
            
        Returns:
            Dictionary with Spearman correlation and p-value
        """
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)
        
        if len(y_true) < 2:
            return {'spearman_r': 0.0, 'p_value': 1.0, 'error': 'Insufficient samples'}
        
        spearman_r, p_value = spearmanr(y_true, y_pred)
        
        return {
            'spearman_r': float(spearman_r),
            'p_value': float(p_value)
        }
    
    def evaluate_binding_site_predictions(
        self,
        predictions: List[Dict],
        ground_truth: List[Dict]
    ) -> Dict[str, float]:
        """
        Evaluate binding site predictions against ground truth.
        
        Args:
            predictions: List of prediction dicts with 'position' and 'probability'
            ground_truth: List of ground truth dicts with annotations
            
        Returns:
            Dictionary with evaluation metrics
        """
        # Flatten predictions and ground truth
        all_y_true = []
        all_y_scores = []
        
        for pred, gt in zip(predictions, ground_truth):
            annotations = gt.get('annotations', {})
            seq_len = len(gt['sequence'])
            
            # For each position in the sequence
            for pos in range(1, seq_len + 1):
                # Ground truth: 1 if binding site, 0 otherwise
                is_binding = 1 if str(pos) in annotations else 0
                all_y_true.append(is_binding)
                
                # Predicted probability
                pred_probs = {p['position']: p['probability'] for p in pred.get('predictions', [])}
                prob = pred_probs.get(pos, 0.0)
                all_y_scores.append(prob)
        
        # Compute metrics
        roc_metrics = self.compute_roc_auc(all_y_true, all_y_scores)
        pr_metrics = self.compute_pr_auc(all_y_true, all_y_scores)
        
        return {
            'roc_auc': roc_metrics.get('roc_auc', 0.0),
            'pr_auc': pr_metrics.get('pr_auc', 0.0),
            'num_samples': len(all_y_true),
            'num_positive': sum(all_y_true),
            'num_negative': len(all_y_true) - sum(all_y_true)
        }
    
    def evaluate_variant_scoring(
        self,
        predictions: List[Dict],
        ground_truth: List[Dict] = None
    ) -> Dict[str, float]:
        """
        Evaluate variant scoring predictions.
        Since we don't have real ground truth, we compute statistics on predictions.
        
        Args:
            predictions: List of variant scoring predictions
            ground_truth: Optional ground truth (not available in demo)
            
        Returns:
            Dictionary with evaluation metrics
        """
        all_scores = []
        
        for pred in predictions:
            for variant in pred.get('variant_scores', []):
                all_scores.append(variant['deleterious_score'])
        
        if not all_scores:
            return {'error': 'No variant scores found'}
        
        all_scores = np.array(all_scores)
        
        return {
            'mean_score': float(np.mean(all_scores)),
            'std_score': float(np.std(all_scores)),
            'min_score': float(np.min(all_scores)),
            'max_score': float(np.max(all_scores)),
            'num_variants': len(all_scores)
        }
    
    def save_metrics(self, path: str):
        """Save evaluation metrics to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        print(f"Metrics saved to {path}")


class BaselineComparisons:
    """Implement baseline methods for comparison."""
    
    def __init__(self, random_seed: int = 42):
        np.random.seed(random_seed)
    
    def random_baseline(self, y_true: List[int]) -> Dict[str, float]:
        """
        Random baseline: predict random probabilities.
        
        Args:
            y_true: Ground truth labels
            
        Returns:
            Dictionary with ROC-AUC and PR-AUC
        """
        y_true = np.array(y_true)
        y_scores = np.random.random(len(y_true))
        
        if len(np.unique(y_true)) < 2:
            return {'roc_auc': 0.0, 'pr_auc': 0.0}
        
        roc_auc = roc_auc_score(y_true, y_scores)
        pr_auc = average_precision_score(y_true, y_scores)
        
        return {
            'roc_auc': float(roc_auc),
            'pr_auc': float(pr_auc)
        }
    
    def majority_class_baseline(self, y_true: List[int]) -> Dict[str, float]:
        """
        Majority class baseline: predict majority class probability.
        
        Args:
            y_true: Ground truth labels
            
        Returns:
            Dictionary with ROC-AUC and PR-AUC
        """
        y_true = np.array(y_true)
        majority_class = np.bincount(y_true).argmax()
        y_scores = np.full(len(y_true), 1.0 if majority_class == 1 else 0.0)
        
        if len(np.unique(y_true)) < 2:
            return {'roc_auc': 0.0, 'pr_auc': 0.0}
        
        roc_auc = roc_auc_score(y_true, y_scores)
        pr_auc = average_precision_score(y_true, y_scores)
        
        return {
            'roc_auc': float(roc_auc),
            'pr_auc': float(pr_auc)
        }
    
    def blosum62_baseline(self, sequence: str, position: int, mutant_aa: str) -> float:
        """
        BLOSUM62 substitution score baseline.
        
        Args:
            sequence: Original protein sequence
            position: Position to mutate (1-indexed)
            mutant_aa: Mutant amino acid
            
        Returns:
            BLOSUM62 score (negative for deleterious)
        """
        # Simplified BLOSUM62 matrix (subset)
        blosum62 = {
            'A': {'A': 4, 'R': -1, 'N': -2, 'D': -2, 'C': 0, 'Q': -1, 'E': -1, 'G': 0, 'H': -2, 'I': -1,
                  'L': -1, 'K': -1, 'M': -1, 'F': -2, 'P': -1, 'S': 1, 'T': 0, 'W': -3, 'Y': -2, 'V': 0},
            'R': {'A': -1, 'R': 5, 'N': 0, 'D': -2, 'C': -3, 'Q': 1, 'E': 0, 'G': -2, 'H': 0, 'I': -3,
                  'L': -2, 'K': 2, 'M': -1, 'F': -3, 'P': -2, 'S': -1, 'T': -1, 'W': -3, 'Y': -2, 'V': -3},
            # ... (full matrix would be included in production)
        }
        
        if position < 1 or position > len(sequence):
            return 0.0
        
        original_aa = sequence[position - 1]
        
        if original_aa not in blosum62 or mutant_aa not in blosum62[original_aa]:
            return 0.0
        
        # Negative score = deleterious
        return -blosum62[original_aa][mutant_aa]


if __name__ == '__main__':
    # Quick test
    eval_metrics = EvaluationMetrics()
    
    # Test ROC-AUC
    y_true = [0, 1, 0, 1, 0, 1]
    y_scores = [0.1, 0.9, 0.2, 0.8, 0.3, 0.7]
    roc = eval_metrics.compute_roc_auc(y_true, y_scores)
    print(f"ROC-AUC: {roc['roc_auc']:.4f}")
    
    # Test PR-AUC
    pr = eval_metrics.compute_pr_auc(y_true, y_scores)
    print(f"PR-AUC: {pr['pr_auc']:.4f}")
    
    # Test Spearman
    y_true_scores = [1.0, 2.0, 3.0, 4.0, 5.0]
    y_pred_scores = [1.1, 2.1, 2.9, 4.2, 4.8]
    spearman = eval_metrics.compute_spearman(y_true_scores, y_pred_scores)
    print(f"Spearman r: {spearman['spearman_r']:.4f}")
    
    # Test baselines
    baseline = BaselineComparisons()
    random_baseline = baseline.random_baseline(y_true)
    print(f"Random baseline ROC-AUC: {random_baseline['roc_auc']:.4f}")
    
    majority_baseline = baseline.majority_class_baseline(y_true)
    print(f"Majority baseline ROC-AUC: {majority_baseline['roc_auc']:.4f}")
