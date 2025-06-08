import asyncio
import aiohttp
import logging
from datetime import datetime
import sys
import os
import ctypes
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import FailoverEvent, NodeStatus

# Set console window title
if os.name == 'nt':  # Windows
    ctypes.windll.kernel32.SetConsoleTitleW("ONTAP HA Pair Simulator - HA Controller")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HAController:
    def __init__(self):
        self.node_a_url = "http://localhost:8001"
        self.node_b_url = "http://localhost:8002"
        self.node_states: Dict[str, Dict] = {
            "node-a": {"healthy": True, "last_seen": None, "simulated_failure": False},
            "node-b": {"healthy": True, "last_seen": None, "simulated_failure": False}
        }
        self.failover_events = []
        self.heartbeat_interval = 5  # seconds
        self.failover_timeout = 15  # seconds

    async def check_node_health(self, session: aiohttp.ClientSession, node_url: str, node_name: str) -> bool:
        """Check health status of a node."""
        try:
            async with session.get(f"{node_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    # If node reports it's in FAILED state, it's a simulated failure
                    if data.get("status") == NodeStatus.FAILED:
                        if not self.node_states[node_name]["simulated_failure"]:
                            self.node_states[node_name]["simulated_failure"] = True
                            await self.handle_simulated_failure(session, node_name)
                        return False
                    self.node_states[node_name]["healthy"] = True
                    self.node_states[node_name]["last_seen"] = datetime.now()
                    self.node_states[node_name]["simulated_failure"] = False
                    return True
                return False
        except aiohttp.ClientError:
            if not self.node_states[node_name]["simulated_failure"]:
                logger.warning(f"Failed to connect to {node_name}")
            return False

    async def handle_simulated_failure(self, session: aiohttp.ClientSession, failed_node: str):
        """Handle a simulated node failure."""
        logger.info(f"Handling simulated failure of {failed_node}")
        takeover_node = "node-b" if failed_node == "node-a" else "node-a"
        takeover_url = self.node_b_url if failed_node == "node-a" else self.node_a_url
        
        try:
            # Notify the takeover node
            async with session.post(f"{takeover_url}/takeover") as response:
                if response.status == 200:
                    event = FailoverEvent(
                        timestamp=datetime.now(),
                        trigger="simulated_failure",
                        failed_node=failed_node,
                        takeover_node=takeover_node,
                        duration_ms=0
                    )
                    self.failover_events.append(event)
                    logger.info(f"Simulated failover completed: {failed_node} → {takeover_node}")
                else:
                    logger.error(f"Failed to initiate takeover on {takeover_node}")
        except aiohttp.ClientError as e:
            logger.error(f"Failed to communicate with {takeover_node}: {e}")

    async def initiate_failover(self, session: aiohttp.ClientSession, failed_node: str):
        """Initiate failover process when a node fails unexpectedly."""
        # Skip if this is a simulated failure
        if self.node_states[failed_node]["simulated_failure"]:
            return
            
        start_time = datetime.now()
        
        # Determine the takeover node
        takeover_node = "node-b" if failed_node == "node-a" else "node-a"
        takeover_url = self.node_b_url if failed_node == "node-a" else self.node_a_url
        
        try:
            # Notify the takeover node
            async with session.post(f"{takeover_url}/takeover") as response:
                if response.status == 200:
                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    event = FailoverEvent(
                        timestamp=start_time,
                        trigger="node_failure",
                        failed_node=failed_node,
                        takeover_node=takeover_node,
                        duration_ms=duration
                    )
                    self.failover_events.append(event)
                    logger.info(f"Failover completed: {failed_node} → {takeover_node}")
                else:
                    logger.error(f"Failed to initiate takeover on {takeover_node}")
        except aiohttp.ClientError as e:
            logger.error(f"Failed to communicate with {takeover_node}: {e}")

    async def monitor_heartbeat(self):
        """Main heartbeat monitoring loop."""
        while True:  # Outer loop to ensure monitoring continues even if session fails
            try:
                async with aiohttp.ClientSession() as session:
                    while True:
                        try:
                            # Check Node A
                            node_a_healthy = await self.check_node_health(session, self.node_a_url, "node-a")
                            if not node_a_healthy and self.node_states["node-a"]["healthy"]:
                                logger.warning("Node A appears to be down")
                                await self.initiate_failover(session, "node-a")
                                self.node_states["node-a"]["healthy"] = False

                            # Check Node B
                            node_b_healthy = await self.check_node_health(session, self.node_b_url, "node-b")
                            if not node_b_healthy and self.node_states["node-b"]["healthy"]:
                                logger.warning("Node B appears to be down")
                                await self.initiate_failover(session, "node-b")
                                self.node_states["node-b"]["healthy"] = False

                            await asyncio.sleep(self.heartbeat_interval)
                        except aiohttp.ClientError as e:
                            logger.error(f"Error during health check: {e}")
                            await asyncio.sleep(1)  # Brief pause before retry
                        except Exception as e:
                            logger.error(f"Unexpected error during health check: {e}")
                            await asyncio.sleep(1)  # Brief pause before retry
            except Exception as e:
                logger.error(f"Session error in monitor_heartbeat: {e}")
                await asyncio.sleep(1)  # Brief pause before creating new session

    def get_node_status(self) -> Dict:
        """Return current status of both nodes."""
        return {
            "node_states": self.node_states,
            "failover_events": [event.dict() for event in self.failover_events]
        }

async def main():
    controller = HAController()
    logger.info("Starting HA Controller...")
    await controller.monitor_heartbeat()

if __name__ == "__main__":
    asyncio.run(main()) 