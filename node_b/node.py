from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
from datetime import datetime
import sys
import os
import ctypes
from pathlib import Path
import shutil

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Node, NodeStatus, Volume, LogicalInterface, NVRAMEntry, LIFStatus

# Set console window title
if os.name == 'nt':  # Windows
    ctypes.windll.kernel32.SetConsoleTitleW("ONTAP HA Pair Simulator - Node B")

# Define storage path
STORAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared_storage")
os.makedirs(STORAGE_PATH, exist_ok=True)

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

@app.get("/files")
async def list_files():
    """List all files in storage."""
    if node.status == NodeStatus.FAILED:
        raise HTTPException(status_code=503, detail="Node is in failed state")
    
    try:
        files = []
        for file_path in Path(STORAGE_PATH).glob("*"):
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime)
                })
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to storage."""
    if node.status == NodeStatus.FAILED:
        raise HTTPException(status_code=503, detail="Node is in failed state")
    
    try:
        file_path = os.path.join(STORAGE_PATH, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": f"File {file.filename} uploaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/{filename}")
async def download_file(filename: str):
    """Download a file from storage."""
    if node.status == NodeStatus.FAILED:
        raise HTTPException(status_code=503, detail="Node is in failed state")
    
    file_path = os.path.join(STORAGE_PATH, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        return FileResponse(file_path, filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """Delete a file from storage."""
    if node.status == NodeStatus.FAILED:
        raise HTTPException(status_code=503, detail="Node is in failed state")
    
    file_path = os.path.join(STORAGE_PATH, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        os.remove(file_path)
        return {"message": f"File {filename} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002) 