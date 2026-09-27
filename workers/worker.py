"""
ProStruct Worker: Processes tasks from the distributed queue.
Implements binding site prediction and variant scoring using the trained model.
"""

import sys
import os
import time
import uuid
import signal
import threading
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.queue_system import TaskQueue, Task
from src.model import ProStructModel


class Worker:
    """Worker process that pulls tasks from the queue and processes them."""
    
    def __init__(self, worker_id: Optional[str] = None, config_path: str = 'config.yaml'):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.config_path = config_path
        self.running = False
        self.should_stop = False
        
        # Initialize queue connection
        self.queue = TaskQueue(config_path)
        
        # Initialize model (lazy load when needed)
        self.model = None
        
        # Register worker
        self.queue.register_worker(self.worker_id)
        print(f"Worker {self.worker_id} initialized")
    
    def load_model(self):
        """Load the model for inference."""
        if self.model is None:
            self.model = ProStructModel(config_path=self.config_path, device='cpu')
            
            # Try to load trained model if available
            model_path = Path('data/model_checkpoint.pt')
            if model_path.exists():
                self.model.load_model(str(model_path))
                print(f"Worker {self.worker_id}: Loaded trained model")
            else:
                print(f"Worker {self.worker_id}: Using untrained model (for testing only)")
    
    def process_binding_site_task(self, task: Task) -> Dict:
        """Process a binding site prediction task."""
        self.load_model()
        
        try:
            # Predict binding sites
            binding_predictions = self.model.predict_binding_sites(task.sequence)
            
            # Filter high-confidence predictions (threshold 0.5)
            high_confidence = [(pos, prob) for pos, prob in binding_predictions if prob >= 0.5]
            
            result = {
                'protein_id': task.protein_id,
                'task_type': 'binding_site',
                'sequence_length': len(task.sequence),
                'predictions': binding_predictions,
                'high_confidence_sites': high_confidence,
                'num_predicted_sites': len(high_confidence)
            }
            
            return result
        except Exception as e:
            raise Exception(f"Binding site prediction failed: {str(e)}")
    
    def process_variant_scoring_task(self, task: Task) -> Dict:
        """
        Process a variant scoring task.
        For demo purposes, score random positions in the sequence.
        """
        self.load_model()
        
        try:
            # Generate random variants to score (for demo)
            import random
            random.seed(42)  # For reproducibility
            
            amino_acids = ['A', 'R', 'N', 'D', 'C', 'E', 'Q', 'G', 'H', 'I', 
                          'L', 'K', 'M', 'F', 'P', 'S', 'T', 'W', 'Y', 'V']
            
            # Score 5 random variants
            variant_scores = []
            seq_len = len(task.sequence)
            
            for _ in range(5):
                pos = random.randint(1, seq_len)
                original_aa = task.sequence[pos - 1]
                mutant_aa = random.choice([aa for aa in amino_acids if aa != original_aa])
                
                score = self.model.score_variant(task.sequence, pos, mutant_aa)
                
                variant_scores.append({
                    'position': pos,
                    'original_aa': original_aa,
                    'mutant_aa': mutant_aa,
                    'deleterious_score': score
                })
            
            result = {
                'protein_id': task.protein_id,
                'task_type': 'variant_scoring',
                'sequence_length': seq_len,
                'variant_scores': variant_scores,
                'num_variants_scored': len(variant_scores)
            }
            
            return result
        except Exception as e:
            raise Exception(f"Variant scoring failed: {str(e)}")
    
    def process_task(self, task: Task) -> Dict:
        """Process a task based on its type."""
        if task.task_type == 'binding_site':
            return self.process_binding_site_task(task)
        elif task.task_type == 'variant_scoring':
            return self.process_variant_scoring_task(task)
        else:
            raise Exception(f"Unknown task type: {task.task_type}")
    
    def run(self):
        """Main worker loop."""
        self.running = True
        print(f"Worker {self.worker_id} started")
        
        heartbeat_interval = self.queue.config['queue']['heartbeat_interval']
        
        while self.running and not self.should_stop:
            try:
                # Update heartbeat
                self.queue.update_heartbeat(self.worker_id)
                
                # Try to get a task
                task = self.queue.dequeue_task(self.worker_id)
                
                if task:
                    print(f"Worker {self.worker_id}: Processing task {task.task_id} ({task.task_type})")
                    
                    try:
                        # Process the task
                        result = self.process_task(task)
                        
                        # Mark as complete
                        self.queue.task_complete(task, self.worker_id, result, success=True)
                        print(f"Worker {self.worker_id}: Task {task.task_id} completed successfully")
                    
                    except Exception as e:
                        error_msg = str(e)
                        print(f"Worker {self.worker_id}: Task {task.task_id} failed: {error_msg}")
                        self.queue.task_failed(task, self.worker_id, error_msg)
                
                else:
                    # No tasks available, wait a bit
                    time.sleep(1)
            
            except Exception as e:
                print(f"Worker {self.worker_id}: Error in main loop: {e}")
                time.sleep(5)
        
        print(f"Worker {self.worker_id} stopped")
    
    def stop(self):
        """Stop the worker gracefully."""
        self.should_stop = True
        self.running = False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"Worker {self.worker_id}: Received signal {signum}, shutting down...")
        self.stop()


def main():
    """Main entry point for worker process."""
    import argparse
    
    parser = argparse.ArgumentParser(description='ProStruct Worker')
    parser.add_argument('--worker-id', type=str, help='Custom worker ID')
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to config file')
    args = parser.parse_args()
    
    # Create worker
    worker = Worker(worker_id=args.worker_id, config_path=args.config)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, worker.signal_handler)
    signal.signal(signal.SIGTERM, worker.signal_handler)
    
    # Run worker
    try:
        worker.run()
    except KeyboardInterrupt:
        worker.stop()


if __name__ == '__main__':
    main()
