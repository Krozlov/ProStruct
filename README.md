# ProStruct - Distributed Protein Structure/Effect Prediction Pipeline

A distributed computing pipeline for protein binding-site prediction and variant effect scoring using a custom Transformer model.

## Features

- **Data Pipeline**: Extracts real SwissProt records from Biopython test corpus and generates tagged synthetic mutants for scale testing (~500 sequences)
- **Custom Transformer Model**: Small encoder with masked language modeling pretraining and binding-site classification
- **Distributed Task Queue**: Redis-backed queue with length-aware load balancing, retries with exponential backoff, and dead-letter queue
- **Multi-process Workers**: Parallel processing of binding site prediction and variant scoring tasks
- **Real-time Dashboard**: Live monitoring with WebSocket updates, Chart.js visualizations, and worker status tracking

## Architecture

```
Data Pipeline → Model Training → Task Queue → Workers → Dashboard
```

## Installation

### Prerequisites

- Python 3.8+
- Redis server

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Install Redis

**Option 1: Download for Windows**
- Download from: https://github.com/microsoftarchive/redis/releases
- Extract and run `redis-server.exe`

**Option 2: WSL**
```bash
wsl
sudo apt-get update
sudo apt-get install redis-server
sudo service redis-server start
```

**Option 3: Cloud Redis**
- Use Redis Cloud, AWS ElastiCache, or similar services

## Usage

### Run the Demo

```bash
python demo.py
```

This will:
1. Generate the dataset
2. Train the model (simplified for demo)
3. Enqueue tasks
4. Start workers
5. Launch the dashboard at http://localhost:8000

### Individual Components

**Generate dataset:**
```bash
python src/data_pipeline.py
```

**Train model:**
```bash
python src/model.py
```

**Start a worker:**
```bash
python workers/worker.py
```

**Start dashboard:**
```bash
python dashboard/app.py
```

## Project Structure

```
ProStruct/
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
├── demo.py                  # End-to-end demo script
├── src/
│   ├── data_pipeline.py     # Data generation
│   ├── model.py             # Transformer model
│   └── queue_system.py      # Redis task queue
├── workers/
│   └── worker.py            # Worker processes
├── dashboard/
│   ├── app.py               # FastAPI backend
│   └── index.html           # Dashboard UI
└── data/                    # Generated datasets
```

## Configuration

Edit `config.yaml` to adjust:
- Model architecture (embedding_dim, num_layers, etc.)
- Training parameters (batch_size, learning_rate, epochs)
- Queue settings (Redis host/port, retry behavior)
- Worker count and timeouts

## Limitations

- Real annotated dataset is small (~19 proteins) — results demonstrate pipeline correctness, not statistical robustness
- No genuine ClinVar clinical labels — "pathogenicity" scoring uses heuristic proxy
- Synthetic mutants are for load-testing only and carry no biological ground truth

## License

MIT License
