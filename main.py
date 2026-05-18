import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import click
import subprocess
from core.orchestrator import Orchestrator

@click.command()
@click.option('--tui', is_flag=True, help='Start the TUI interface')
@click.option('--web', is_flag=True, help='Start the Web Dashboard')
def main(tui, web):
    """JARVIS: Modular Agentic AI Ecosystem"""
    
    agents_dir = os.path.join(os.path.dirname(__file__), "agents/configs")
    orchestrator = Orchestrator(agents_dir)
    
    if tui:
        from interfaces.tui import JARVISApp
        app = JARVISApp(orchestrator)
        app.run()
    elif web:
        print("Starting JARVIS Web Ecosystem (v2)...")
        from interfaces.web_v2 import start_web
        start_web()
    else:
        print("Please specify an interface: --tui or --web")

if __name__ == "__main__":
    main()
