from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import sys
import os
import ctypes

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Node, NodeStatus, Volume, LogicalInterface, NVRAMEntry, LIFStatus

# Set console window title
if os.name == 'nt':  # Windows
    ctypes.windll.kernel32.SetConsoleTitleW("ONTAP HA Pair Simulator - Node B")

app = FastAPI(title="ONTAP Node B")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize node state
node = Node(
    name="node-b",
    role="secondary",
    partner_node="node-a",
    volumes=[
        Volume(
            name="vol1-replica",
            size_gb=100,
            used_gb=20.5,
            state="online",
            owner_node="node-b",
            is_replica=True
        )
    ],
    lifs=[
        LogicalInterface(
            name="lif2",
            ip_address="192.168.1.11",
            current_node="node-b",
            home_node="node-b",
            protocol="nfs",
            port=2049
        )
    ]
)

@app.get("/health")
async def health_check():
    """Health check endpoint for the node."""
    if node.status == NodeStatus.FAILED:
        raise HTTPException(status_code=503, detail="Node is in failed state")
    return {
        "status": node.status,
        "last_heartbeat": node.last_heartbeat,
        "role": node.role
    }

@app.get("/status")
async def get_status():
    """Get detailed node status."""
    return {
        "node": node.dict(),
        "volumes": [vol.dict() for vol in node.volumes],
        "lifs": [lif.dict() for lif in node.lifs],
        "nvram_entries": len(node.nvram_log)
    }

@app.post("/takeover")
async def initiate_takeover():
    """Take over for failed partner node."""
    if node.status == NodeStatus.TAKEOVER:
        # Already in takeover mode
        return {"message": "Already in takeover mode", "timestamp": datetime.now()}
        
    node.status = NodeStatus.TAKEOVER
    
    # Accept migrated LIFs from partner
    partner_lifs = [
        LogicalInterface(
            name="lif1",
            ip_address="192.168.1.10",
            current_node="node-b",  # Now on this node
            home_node="node-a",     # Originally from partner
            protocol="nfs",
            port=2049,
            status=LIFStatus.ONLINE
        )
    ]
    
    # Add partner LIFs to our list
    node.lifs.extend(partner_lifs)
    
    return {"message": "Takeover initiated", "timestamp": datetime.now()}

@app.post("/nvram/sync")
async def sync_nvram(entry: NVRAMEntry):
    """Simulate NVRAM synchronization with partner node."""
    node.nvram_log.append(entry)
    return {"message": "NVRAM entry synchronized", "sequence_no": entry.sequence_no}

@app.post("/prepare-giveback")
async def prepare_giveback():
    """Prepare for giveback to partner node."""
    if node.status != NodeStatus.TAKEOVER:
        raise HTTPException(status_code=400, detail="Node must be in takeover state for giveback")
    
    # Prepare to return LIFs to partner
    for lif in node.lifs:
        if lif.home_node == node.partner_node:
            lif.status = LIFStatus.MIGRATING
    
    return {"message": "Ready for giveback", "timestamp": datetime.now()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002) 