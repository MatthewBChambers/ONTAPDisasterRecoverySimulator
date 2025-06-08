import click
import requests
import json
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from datetime import datetime
import time
import sys
import os
import subprocess
import atexit
import signal
import psutil

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

console = Console()
simulator_process = None
CONTROL_URL = "http://localhost:8000"
shutdown_in_progress = False

def kill_proc_tree(pid, include_parent=True):
    """Kill a process tree (including grandchildren) with given pid."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # First try graceful termination
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        
        # Give them some time to terminate
        gone, alive = psutil.wait_procs(children, timeout=2)
        
        # If still alive, kill forcefully
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
                
        if include_parent:
            try:
                parent.terminate()
                parent.wait(2)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                try:
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
    except psutil.NoSuchProcess:
        pass

def start_simulator():
    """Start the simulator process if not already running"""
    global simulator_process
    if simulator_process is None:
        try:
            # Get the path to main.py relative to cli.py
            main_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')
            simulator_process = subprocess.Popen(
                [sys.executable, main_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            # Wait a bit for services to start
            time.sleep(3)
            console.print("[green]Started ONTAP HA Pair Simulator[/green]")
        except Exception as e:
            console.print(f"[red]Failed to start simulator: {e}[/red]")
            sys.exit(1)

def stop_simulator():
    """Stop the simulator process if running"""
    global simulator_process, shutdown_in_progress
    
    if shutdown_in_progress:
        return
        
    if simulator_process:
        try:
            shutdown_in_progress = True
            console.print("[yellow]Shutting down simulator...[/yellow]")
            
            # First try to gracefully shutdown through the control server
            try:
                requests.post(f"{CONTROL_URL}/shutdown", timeout=2)
            except requests.RequestException:
                pass  # Control server might already be down
            
            # Kill the process tree
            if simulator_process.poll() is None:  # If still running
                kill_proc_tree(simulator_process.pid)
            
            console.print("[green]Stopped ONTAP HA Pair Simulator[/green]")
            
        except Exception as e:
            console.print(f"[red]Error stopping simulator: {e}[/red]")
        finally:
            simulator_process = None
            shutdown_in_progress = False

def signal_handler(signum, frame):
    """Handle interrupt signals"""
    if not shutdown_in_progress:
        stop_simulator()
        sys.exit(0)
    else:
        # Force exit if already shutting down
        console.print("\n[red]Forcing shutdown...[/red]")
        if simulator_process and simulator_process.poll() is None:
            kill_proc_tree(simulator_process.pid, include_parent=True)
        sys.exit(1)

# Register cleanup function and signal handlers
atexit.register(stop_simulator)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class ONTAPSimulator:
    def __init__(self):
        self.node_a_url = "http://localhost:8001"
        self.node_b_url = "http://localhost:8002"

    def get_node_status(self, node_url):
        try:
            response = requests.get(f"{node_url}/status")
            return response.json()
        except requests.RequestException:
            return None

    def display_status(self):
        """Display current status of both nodes in a rich table."""
        table = Table(title="ONTAP HA Pair Status")
        
        table.add_column("Component")
        table.add_column("Node A")
        table.add_column("Node B")

        node_a_status = self.get_node_status(self.node_a_url)
        node_b_status = self.get_node_status(self.node_b_url)

        # Node Status
        table.add_row(
            "Status",
            "🟢 Online" if node_a_status else "🔴 Offline",
            "🟢 Online" if node_b_status else "🔴 Offline"
        )

        if node_a_status and node_b_status:
            # Volumes
            table.add_row(
                "Volumes",
                "\n".join([f"📁 {v['name']}" for v in node_a_status["volumes"]]),
                "\n".join([f"📁 {v['name']}" for v in node_b_status["volumes"]])
            )

            # LIFs
            table.add_row(
                "LIFs",
                "\n".join([f"🔌 {l['name']} ({l['ip_address']})" for l in node_a_status["lifs"]]),
                "\n".join([f"🔌 {l['name']} ({l['ip_address']})" for l in node_b_status["lifs"]])
            )

            # NVRAM Entries
            table.add_row(
                "NVRAM Entries",
                str(node_a_status["nvram_entries"]),
                str(node_b_status["nvram_entries"])
            )

        console.print(table)

@click.group()
def cli():
    """ONTAP HA Pair Simulator CLI"""
    # Start simulator when any command is run
    start_simulator()

@cli.command()
def status():
    """Display current status of the HA pair"""
    simulator = ONTAPSimulator()
    simulator.display_status()

@cli.command()
@click.argument('node', type=click.Choice(['a', 'b']))
def fail(node):
    """Simulate failure of a node"""
    simulator = ONTAPSimulator()
    node_url = simulator.node_a_url if node == 'a' else simulator.node_b_url
    
    try:
        response = requests.post(f"{node_url}/failover")
        if response.status_code == 200:
            console.print(f"[green]Node {node.upper()} failure simulated successfully[/green]")
        else:
            console.print(f"[red]Failed to simulate node failure: {response.text}[/red]")
    except requests.RequestException as e:
        console.print(f"[red]Error communicating with node: {e}[/red]")

@cli.command()
@click.argument('node', type=click.Choice(['a', 'b']))
def giveback(node):
    """Initiate giveback operation"""
    simulator = ONTAPSimulator()
    node_url = simulator.node_a_url if node == 'a' else simulator.node_b_url
    
    try:
        response = requests.post(f"{node_url}/giveback")
        if response.status_code == 200:
            console.print(f"[green]Giveback initiated successfully for Node {node.upper()}[/green]")
        else:
            console.print(f"[red]Failed to initiate giveback: {response.text}[/red]")
    except requests.RequestException as e:
        console.print(f"[red]Error communicating with node: {e}[/red]")

@cli.command()
def monitor():
    """Monitor HA pair status in real-time"""
    simulator = ONTAPSimulator()
    
    try:
        with Live(auto_refresh=False) as live:
            while True:
                simulator.display_status()
                live.refresh()
                time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping monitor...[/yellow]")
        stop_simulator()
        sys.exit(0)

if __name__ == '__main__':
    try:
        cli()
    finally:
        stop_simulator() 