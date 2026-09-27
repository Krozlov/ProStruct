# Distributed Systems Presentation
## Distributed Protein Structure Prediction Pipeline

---

### Slide 1: Title
**Distributed Protein Structure Prediction Pipeline**
- Architecture, Design Choices, and Analysis
- Week 13 Presentation
- Group: [Your Names]
- Course: Distributed Systems (COMP6705001)

---

### Slide 2: Problem Statement

**Problem:**
- Protein analysis is computationally expensive
- Large-scale variant scoring requires parallel processing
- Need real-time monitoring and fault tolerance

**Distributed Solution:**
- Redis-backed task queue for distributed processing
- Multi-process workers for parallel execution
- Real-time dashboard for monitoring
- Fault tolerance with retries and dead-letter queue

---

### Slide 3: System Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Data Pipeline│ →  │ Model Train │ →  │ Task Queue  │
└─────────────┘    └─────────────┘    └─────────────┘
                                            ↓
                                    ┌─────────────┐
                                    │   Workers   │
                                    └─────────────┘
                                            ↓
                                    ┌─────────────┐
                                    │  Dashboard  │
                                    └─────────────┘
```

**Distributed Components:**
- Task Queue (Redis)
- Workers (Multi-process)
- Dashboard (WebSocket)
- Results Database (SQLite)

---

### Slide 4: Communication

**1. Task Queue Communication (Redis)**
- Producer-Consumer pattern
- Workers dequeue tasks from Redis
- Length-aware load balancing

**2. Dashboard Communication (WebSocket)**
- Real-time updates to dashboard
- Queue statistics pushed to clients
- Low-latency monitoring

**3. Inter-Process Communication**
- Shared SQLite database for results
- Redis for coordination
- Process signals for shutdown

---

### Slide 5: Naming

**Task IDs:**
- Format: `{task_type}-{protein_id}`
- Example: `binding-P12345`, `variant-P12345`
- Unique identification across system

**Worker IDs:**
- Format: `demo-worker-{index}`
- Example: `demo-worker-0`, `demo-worker-1`
- Used for tracking and heartbeats

**Queue Names:**
- Regular queue: `prostruct:tasks`
- Priority queue: `prostruct:priority`
- Dead-letter queue: `prostruct:dlq`
- Worker registry: `prostruct:workers`

---

### Slide 6: Synchronization

**1. Thread Locks**
- Protect shared data structures
- Prevent race conditions in queue operations
- Used in enqueue/dequeue operations

**2. Worker Heartbeats**
- Workers send heartbeat every 30s
- Dashboard monitors worker status
- Failed workers detected and cleaned up

**3. Atomic Operations**
- Redis atomic operations (ZPOPMIN)
- SQLite transactions for results
- Prevents inconsistent state

---

### Slide 7: Consistency

**Eventual Consistency:**
- Results written to SQLite asynchronously
- Dashboard shows near real-time stats
- Small delay acceptable for monitoring

**Strong Consistency:**
- Task queue operations are atomic
- Worker registry updates are atomic
- No lost tasks or duplicate processing

**Trade-offs:**
- Chose eventual consistency for monitoring
- Strong consistency for critical operations
- Balance between performance and correctness

---

### Slide 8: Replication

**Current Implementation:**
- Single Redis instance (no replication)
- Single SQLite database (no replication)
- Suitable for demo/small-scale deployment

**Future Improvements:**
- Redis Cluster for high availability
- Database replication for fault tolerance
- Load balancer for workers

**Design Decision:**
- Simplified for demo purposes
- Architecture supports scaling
- Can add replication without major changes

---

### Slide 9: Fault Tolerance

**1. Retries with Exponential Backoff**
- Failed tasks re-enqueued automatically
- Backoff: 2^retry_count seconds
- Max 3 retries before dead-letter queue

**2. Dead-Letter Queue**
- Tasks that fail 3 times moved to DLQ
- Prevents infinite retry loops
- Can be inspected and re-queued manually

**3. Worker Failure Detection**
- Heartbeat timeout: 2x heartbeat interval
- Failed workers cleaned up automatically
- Current tasks re-queued

**4. Graceful Shutdown**
- SIGINT/SIGTERM handling
- Workers finish current task
- Dashboard closes connections

---

### Slide 10: Load Balancing

**Length-Aware Scheduling:**
- Tasks scored by sequence length
- Shorter sequences processed first
- Reduces queue depth variance

**Implementation:**
- Redis sorted sets with sequence length as score
- ZPOPMIN retrieves shortest task
- Workers get balanced workload

**Benefits:**
- Prevents long sequences from blocking queue
- Better resource utilization
- Predictable processing time

---

### Slide 11: Scalability

**Horizontal Scaling:**
- Add more workers to increase throughput
- Workers are stateless (can be added/removed)
- Task queue handles coordination

**Vertical Scaling:**
- Increase Redis memory for larger queues
- More CPU for model inference
- Faster network for dashboard updates

**Limitations:**
- Single Redis instance (bottleneck)
- SQLite not suitable for high write load
- Dashboard WebSocket connections limited

---

### Slide 12: Performance Analysis

**Throughput:**
- Tasks per second depends on:
  - Number of workers
  - Model inference time
  - Sequence length

**Latency:**
- Task enqueue: < 10ms
- Task dequeue: < 10ms
- Dashboard update: < 100ms

**Bottlenecks:**
- Model inference (CPU-bound)
- Redis operations (network-bound)
- Database writes (I/O-bound)

---

### Slide 13: Design Decisions

**Why Redis?**
- Fast in-memory operations
- Built-in sorted sets for load balancing
- Pub/sub for real-time updates
- Simple to deploy

**Why Multi-process Workers?**
- Python GIL limits threading
- Processes utilize multiple cores
- Independent failure domains

**Why SQLite?**
- Simple, no external dependencies
- Sufficient for demo scale
- Easy to backup/inspect

---

### Slide 14: Challenges & Solutions

**Challenge 1: Redis Version Compatibility**
- Older Redis doesn't support HELLO command
- Solution: Removed health_check_interval
- Fallback mode for in-memory queue

**Challenge 2: Worker Coordination**
- Need to track worker status
- Solution: Worker registry with heartbeats
- Automatic cleanup of failed workers

**Challenge 3: Task Ordering**
- Need fair task distribution
- Solution: Length-aware load balancing
- Sorted sets in Redis

---

### Slide 15: Evaluation of Distributed Principles

**Communication:**
- ✅ Redis pub/sub, WebSocket
- ✅ Clear communication patterns
- ✅ Low latency updates

**Naming:**
- ✅ Consistent naming scheme
- ✅ Unique identifiers
- ✅ Hierarchical queue names

**Synchronization:**
- ✅ Thread locks
- ✅ Heartbeats
- ✅ Atomic operations

**Consistency:**
- ✅ Strong consistency for critical ops
- ✅ Eventual consistency for monitoring
- ✅ Appropriate trade-offs

**Fault Tolerance:**
- ✅ Retries with backoff
- ✅ Dead-letter queue
- ✅ Worker failure detection

---

### Slide 16: Future Work

**High Availability:**
- Redis Cluster for replication
- Database replication
- Load balancer for workers

**Performance:**
- GPU acceleration for model
- Async I/O for database
- Connection pooling

**Monitoring:**
- Distributed tracing
- Metrics collection (Prometheus)
- Alerting system

---

### Slide 17: Conclusion

**Summary:**
- Built distributed protein analysis pipeline
- Applied distributed systems principles:
  - Communication (Redis, WebSocket)
  - Naming (consistent IDs)
  - Synchronization (locks, heartbeats)
  - Consistency (eventual + strong)
  - Fault tolerance (retries, DLQ)

**Demonstrated:**
- Scalable architecture
- Real-time monitoring
- Robust error handling

**Code:** https://github.com/Krozlov/ProStruct

---

### Slide 18: Questions?

**Thank you!**

**Contact:** [Your email]
