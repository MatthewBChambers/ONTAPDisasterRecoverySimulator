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

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

console = Console()

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
    pass

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
    
    with Live(auto_refresh=False) as live:
        while True:
            simulator.display_status()
            live.refresh()
            time.sleep(2)

if __name__ == '__main__':
    cli() 