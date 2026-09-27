"""
End-to-End Demo Script for ProStruct
This script runs the complete pipeline: data generation, model training, queue processing, and dashboard.
"""

import sys
import os
import time
import subprocess
import multiprocessing
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.data_pipeline import main as run_data_pipeline
from src.model import ProStructModel
from src.queue_system import TaskQueue, Task
import yaml


def print_step(step_num: int, description: str):
    """Print a formatted step header."""
    print("\n" + "=" * 70)
    print(f"STEP {step_num}: {description}")
    print("=" * 70)


def step_1_generate_data():
    """Step 1: Generate the dataset."""
    print_step(1, "Generating Dataset")
    print("Running data pipeline to create train/val/test splits...")
    run_data_pipeline()
    print("✓ Dataset generated successfully")


def step_2_train_model():
    """Step 2: Train the model (simplified for demo)."""
    print_step(2, "Training Model")
    
    print("Loading configuration...")
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    print("Initializing model...")
    model = ProStructModel(config_path='config.yaml', device='cpu')
    
    print(f"Model parameters: {sum(p.numel() for p in model.model.parameters()):,}")
    
    # Load training data
    print("Loading training data...")
    with open('data/train.json', 'r') as f:
        train_data = json.load(f)
    
    with open('data/val.json', 'r') as f:
        val_data = json.load(f)
    
    print(f"Training samples: {len(train_data)}")
    print(f"Validation samples: {len(val_data)}")
    
    # Create simple dataloaders
    batch_size = config['training']['batch_size']
    
    def create_dataloader(data):
        for i in range(0, len(data), batch_size):
            yield data[i:i+batch_size]
    
    train_loader = list(create_dataloader(train_data))
    val_loader = list(create_dataloader(val_data))
    
    # MLM pretraining with validation
    print(f"\nStarting MLM pretraining ({config['training']['epochs_pretrain']} epochs)...")
    model.train_with_validation(
        train_loader, val_loader, 
        task='mlm',
        num_epochs=config['training']['epochs_pretrain'],
        checkpoint_path='data/pretrain_best.pt'
    )
    print("✓ Pretraining completed")
    
    # Fine-tuning with validation
    print(f"\nStarting binding site fine-tuning ({config['training']['epochs_finetune']} epochs)...")
    model.train_with_validation(
        train_loader, val_loader,
        task='classification',
        num_epochs=config['training']['epochs_finetune'],
        checkpoint_path='data/finetune_best.pt'
    )
    print("✓ Fine-tuning completed")
    
    # Save final model
    print("\nSaving final model checkpoint...")
    model.save_model('data/model_checkpoint.pt')
    print("✓ Model saved")


def step_3_start_redis():
    """Step 3: Start Redis server (if not already running)."""
    print_step(3, "Starting Redis Server")
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("✓ Redis is already running")
        return True
    except:
        print("Redis not detected. Please start Redis manually:")
        print("  - On Windows: Download and run Redis Server")
        print("  - On Linux/Mac: sudo service redis-server start")
        print("  - Or use Docker: docker run -d -p 6379:6379 redis")
        print("\nContinuing anyway (will fail if Redis is not available)...")
        return False


def step_4_enqueue_tasks():
    """Step 4: Enqueue tasks for processing."""
    print_step(4, "Enqueuing Tasks")
    
    print("Initializing queue system...")
    queue = TaskQueue()
    
    # Load test data
    print("Loading test data...")
    with open('data/test.json', 'r') as f:
        test_data = json.load(f)
    
    print(f"Found {len(test_data)} test proteins")
    
    # Create tasks
    print("Creating tasks...")
    tasks = []
    for protein in test_data[:50]:  # Limit to 50 for demo
        # Binding site prediction task
        task1 = Task(
            task_id=f"binding-{protein['id']}",
            protein_id=protein['id'],
            sequence=protein['sequence'],
            task_type='binding_site',
            priority=0
        )
        tasks.append(task1)
        
        # Variant scoring task
        task2 = Task(
            task_id=f"variant-{protein['id']}",
            protein_id=protein['id'],
            sequence=protein['sequence'],
            task_type='variant_scoring',
            priority=0
        )
        tasks.append(task2)
    
    print(f"Created {len(tasks)} tasks")
    
    # Enqueue tasks
    print("Enqueuing tasks...")
    count = queue.enqueue_batch(tasks)
    print(f"✓ Enqueued {count} tasks")
    
    stats = queue.get_queue_stats()
    print(f"Queue depth: {stats['total_queue_depth']}")


def step_5_start_workers():
    """Step 5: Start worker processes."""
    print_step(5, "Starting Workers")
    
    print("Starting 2 worker processes...")
    
    # Start workers in background
    worker_processes = []
    for i in range(2):
        proc = subprocess.Popen(
            [sys.executable, 'workers/worker.py', '--worker-id', f'demo-worker-{i}'],
            cwd=str(Path(__file__).parent)
        )
        worker_processes.append(proc)
        print(f"✓ Started worker {i} (PID: {proc.pid})")
    
    return worker_processes


def step_6_start_dashboard():
    """Step 6: Start the dashboard."""
    print_step(6, "Starting Dashboard")
    
    print("Starting dashboard server...")
    print("Dashboard will be available at http://localhost:8000")
    print("Press Ctrl+C to stop the dashboard")
    
    # Start dashboard in background
    dashboard_proc = subprocess.Popen(
        [sys.executable, 'dashboard/app.py'],
        cwd=str(Path(__file__).parent)
    )
    
    print(f"✓ Dashboard started (PID: {dashboard_proc.pid})")
    return dashboard_proc


def step_7_monitor_progress(queue: TaskQueue, duration: int = 60):
    """Step 7: Monitor progress for a specified duration."""
    print_step(7, "Monitoring Progress")
    
    print(f"Monitoring for {duration} seconds...")
    print("Press Ctrl+C to stop early\n")
    
    start_time = time.time()
    
    try:
        while time.time()   - start_time < duration:
            stats = queue.get_queue_stats()
            
            print(f"\rQueue: {stats['total_queue_depth']} | "
                  f"Active Workers: {stats['active_workers']} | "
                  f"Completed: {stats['total_completed']} | "
                  f"Failed: {stats['total_failed']}", end='')
            
            if stats['total_queue_depth'] == 0:
                print("\n✓ All tasks completed!")
                break
            
            time.sleep(2)
        
        print("\n")
        final_stats = queue.get_queue_stats()
        print(f"\nFinal Statistics:")
        print(f"  Total Completed: {final_stats['total_completed']}")
        print(f"  Total Failed: {final_stats['total_failed']}")
        print(f"  Dead Letter Queue: {final_stats['dead_letter_queue_depth']}")
        
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")


def main():
    """Main demo execution."""
    print("\n" + "=" * 70)
    print("ProStruct End-to-End Demo")
    print("=" * 70)
    print("\nThis demo will:")
    print("1. Generate the dataset")
    print("2. Train the model (simplified)")
    print("3. Start Redis (if available)")
    print("4. Enqueue tasks")
    print("5. Start workers")
    print("6. Start dashboard")
    print("7. Monitor progress")
    print("\nStarting automatically...")
    
    try:
        # Step 1: Generate data
        step_1_generate_data()
        
        # Step 2: Train model
        step_2_train_model()
        
        # Step 3: Start Redis
        step_3_start_redis()
        
        # Step 4: Enqueue tasks
        step_4_enqueue_tasks()
        
        # Step 5: Start workers
        worker_processes = step_5_start_workers()
        
        # Give workers time to initialize
        time.sleep(3)
        
        # Step 6: Start dashboard
        dashboard_proc = step_6_start_dashboard()
        
        # Give dashboard time to start
        time.sleep(2)
        
        # Step 7: Monitor progress
        queue = TaskQueue()
        step_7_monitor_progress(queue, duration=60)
        
        print("\n" + "=" * 70)
        print("Demo completed successfully!")
        print("=" * 70)
        print("\nDashboard is still running at http://localhost:8000")
        print("Workers are still running in the background")
        print("Press Ctrl+C to stop all processes")
        
        # Keep processes running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopping all processes...")
            for proc in worker_processes:
                proc.terminate()
            dashboard_proc.terminate()
            print("✓ All processes stopped")
    
    except KeyboardInterrupt:
        print("\n\nDemo cancelled by user")
    except Exception as e:
        print(f"\n\nError during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
