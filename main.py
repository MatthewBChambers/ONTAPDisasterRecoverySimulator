import subprocess
import sys
import time
import click
from rich.console import Console
import os

console = Console()

def start_component(command, name):
    """Start a component and return its process."""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        console.print(f"[green]Started {name}[/green]")
        return process
    except Exception as e:
        console.print(f"[red]Failed to start {name}: {e}[/red]")
        return None

@click.command()
@click.option('--debug/--no-debug', default=False, help='Run in debug mode')
def main(debug):
    """Start the ONTAP HA Pair Simulator"""
    console.print("[bold blue]Starting ONTAP HA Pair Simulator...[/bold blue]")

    # Start Node A
    node_a = start_component(
        ["python", "node_a/node.py"],
        "Node A"
    )

    # Start Node B
    node_b = start_component(
        ["python", "node_b/node.py"],
        "Node B"
    )

    # Start HA Controller
    controller = start_component(
        ["python", "controller/monitor.py"],
        "HA Controller"
    )

    if not all([node_a, node_b, controller]):
        console.print("[red]Failed to start all components. Shutting down...[/red]")
        sys.exit(1)

    console.print("\n[bold green]All components started successfully![/bold green]")
    console.print("\nAvailable endpoints:")
    console.print("- Node A: http://localhost:8001")
    console.print("- Node B: http://localhost:8002")
    console.print("\nUse the CLI to interact with the simulator:")
    console.print("python client/cli.py --help")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down simulator...[/yellow]")
        for process in [node_a, node_b, controller]:
            if process:
                process.terminate()
                process.wait()
        console.print("[green]Shutdown complete[/green]")

if __name__ == '__main__':
    main() 