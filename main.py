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
@click.option('--authorize-ip', 'authorize_ip', default=None, metavar='IP',
              help='Add an IP address to the whitelist (e.g. --authorize-ip=82.1.2.3)')
def main(tui, web, authorize_ip):
    """JARVIS: Modular Agentic AI Ecosystem"""

    if authorize_ip:
        import ipaddress
        try:
            ipaddress.ip_address(authorize_ip)
        except ValueError:
            print(f"[ERREUR] '{authorize_ip}' n'est pas une adresse IP valide.")
            sys.exit(1)
        from config import JARVISConfig
        JARVISConfig.add_allowed_ip(authorize_ip)
        sys.exit(0)

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
