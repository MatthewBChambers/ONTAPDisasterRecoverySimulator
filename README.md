# ONTAP Disaster Recovery Simulator

A simulation of NetApp ONTAP's HA Pair and disaster recovery functionality, demonstrating key concepts like node failover, LIF migration, and SnapMirror replication.

## Features

- HA Pair Simulation (Node A & Node B)
- Automatic Failover on Node Failure
- LIF Migration Simulation
- Heartbeat Monitoring
- Basic SnapMirror-like Data Replication
- Real-time Status Dashboard
- CLI for Manual Testing and Control

## Architecture

The simulator consists of the following components:

1. **Storage Nodes (Node A & Node B)**
   - FastAPI servers simulating ONTAP nodes
   - Health monitoring endpoints
   - Data serving capabilities
   - NVRAM simulation

2. **Heartbeat Monitor**
   - Continuous health checking
   - Failover trigger mechanism
   - Node status tracking

3. **Failover Controller**
   - Request routing
   - LIF migration simulation
   - Failover orchestration

4. **Client Interface**
   - CLI for interaction
   - Status monitoring
   - Manual failure simulation

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the simulator:
   ```bash
   python main.py
   ```

## Usage

1. The simulator will start both nodes and the monitoring system
2. Access the dashboard at http://localhost:8000
3. Use the CLI to:
   - Check node status
   - Trigger manual failovers
   - Monitor replication
   - Simulate failures

## Project Structure

```
disaster-recovery-sim/
├── node_a/              # Primary node implementation
├── node_b/              # Secondary node implementation
├── controller/          # Failover and monitoring logic
├── client/             # CLI and dashboard
├── data/               # Simulated storage
│   ├── node_a/
│   └── node_b/
├── requirements.txt    # Python dependencies
└── README.md          # Documentation
```

## Development

This project uses:
- FastAPI for the node servers
- Rich for terminal UI
- Python's threading for monitoring
- File-based storage for data simulation

## License

MIT License 