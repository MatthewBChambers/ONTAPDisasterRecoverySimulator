import subprocess
import sys
import time
import click
from rich.console import Console
import os
import ctypes
from fastapi import FastAPI
import uvicorn
from threading import Thread, Event
import signal
import psutil
import asyncio

console = Console()
processes = []
app = FastAPI()
shutdown_event = Event()

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

def start_component(command, name, new_console=True):
    """Start a component and return its process."""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' and new_console else 0
        )
        console.print(f"[green]Started {name}[/green]")
        processes.append((process, name))
        return process
    except Exception as e:
        console.print(f"[red]Failed to start {name}: {e}[/red]")
        return None

def cleanup_processes():
    """Cleanup all running processes."""
    global processes
    
    # First try graceful shutdown
    for process, name in processes:
        if process and process.poll() is None:  # If process is still running
            try:
                console.print(f"[yellow]Stopping {name}...[/yellow]")
                kill_proc_tree(process.pid)
            except Exception as e:
                console.print(f"[red]Error stopping {name}: {e}[/red]")
    
    # Clear the processes list
    processes = []

@app.post("/shutdown")
async def shutdown():
    """Endpoint to shutdown all simulator components."""
    cleanup_processes()
    shutdown_event.set()
    return {"status": "success", "message": "All components shut down"}

def run_control_server():
    """Run the control server for shutdown coordination."""
    config = uvicorn.Config(app, host="localhost", port=8000, log_level="error")
    server = uvicorn.Server(config)
    
    # Override server install_signal_handlers to prevent conflict
    server.install_signal_handlers = lambda: None
    
    try:
        server.run()
    except Exception as e:
        console.print(f"[red]Control server error: {e}[/red]")

def set_window_title(title):
    """Set the console window title."""
    if os.name == 'nt':
        ctypes.windll.kernel32.SetConsoleTitleW(title)

@click.command()
@click.option('--debug/--no-debug', default=False, help='Run in debug mode')
def main(debug):
    """Start the ONTAP HA Pair Simulator"""
    set_window_title("ONTAP HA Pair Simulator - Main Controller")
    console.print("[bold blue]Starting ONTAP HA Pair Simulator...[/bold blue]")

    # Start control server in a separate thread
    control_thread = Thread(target=run_control_server, daemon=True)
    control_thread.start()

    # Give the control server a moment to start
    time.sleep(1)

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

    # Start File Application (without new console)
    fileapp = start_component(
        ["python", "fileapp/app.py"],
        "File Application",
        new_console=False
    )

    if not all([node_a, node_b, controller, fileapp]):
        console.print("[red]Failed to start all components. Shutting down...[/red]")
        cleanup_processes()
        sys.exit(1)

    console.print("\n[bold green]All components started successfully![/bold green]")
    console.print("\nAvailable endpoints:")
    console.print("- Node A: http://localhost:8001")
    console.print("- Node B: http://localhost:8002")
    console.print("- File Application: http://localhost:5000")
    console.print("\nUse the CLI to interact with the simulator:")
    console.print("python client/cli.py --help")

    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        if not shutdown_event.is_set():
            console.print("\n[yellow]Shutting down simulator...[/yellow]")
            cleanup_processes()
            shutdown_event.set()
            console.print("[green]Shutdown complete[/green]")
            sys.exit(0)
        else:
            # Force exit if already shutting down
            console.print("\n[red]Forcing shutdown...[/red]")
            sys.exit(1)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while not shutdown_event.is_set():
            time.sleep(0.1)  # More responsive than 1 second
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == '__main__':
    main() 