from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime

class NodeStatus(str, Enum):
    HEALTHY = "healthy"
    FAILED = "failed"
    TAKEOVER = "takeover"
    GIVEBACK = "giveback"

class LIFStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MIGRATING = "migrating"

class LogicalInterface(BaseModel):
    name: str
    ip_address: str
    current_node: str
    home_node: str
    status: LIFStatus = LIFStatus.ONLINE
    protocol: str
    port: int

class Volume(BaseModel):
    name: str
    size_gb: int
    used_gb: float
    state: str
    owner_node: str
    is_replica: bool = False
    last_sync: Optional[datetime] = None

class NVRAMEntry(BaseModel):
    timestamp: datetime
    operation: str
    data: Dict
    sequence_no: int

class Node(BaseModel):
    name: str
    status: NodeStatus = NodeStatus.HEALTHY
    role: str
    partner_node: Optional[str] = None
    volumes: List[Volume] = []
    lifs: List[LogicalInterface] = []
    nvram_log: List[NVRAMEntry] = []
    last_heartbeat: Optional[datetime] = None

class FailoverEvent(BaseModel):
    timestamp: datetime
    trigger: str
    failed_node: str
    takeover_node: str
    duration_ms: float 