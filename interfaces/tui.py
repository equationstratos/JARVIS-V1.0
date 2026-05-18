from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static, ListView, ListItem, Label, Select, LoadingIndicator
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from core.orchestrator import Orchestrator
import asyncio

class JARVISApp(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 3fr;
        background: #0f172a;
    }
    #sidebar {
        background: #1e293b;
        border-right: solid #334155;
        padding: 1;
    }
    #chat-container {
        layout: vertical;
        padding: 1;
    }
    #messages {
        height: 1fr;
        background: #0f172a;
        border: solid #334155;
        padding: 1;
        overflow-y: scroll;
    }
    #input-container {
        height: auto;
        margin-top: 1;
    }
    .user-msg {
        color: #38bdf8;
        background: #0c4a6e 20%;
        padding: 1;
        margin: 1 0;
        border-left: solid #38bdf8;
    }
    .agent-msg {
        color: #f8fafc;
        background: #1e293b;
        padding: 1;
        margin: 1 0;
        border-left: solid #10b981;
    }
    .system-msg {
        color: #94a3b8;
        text-style: italic;
        margin: 0 1;
    }
    Label {
        color: #f8fafc;
    }
    ListItem {
        padding: 0 1;
        color: #94a3b8;
    }
    ListItem:hover {
        background: #334155;
    }
    """

    def __init__(self, orchestrator: Orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.history = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="sidebar"):
            yield Label("🛠️ [bold]MODÈLE[/bold]")
            yield Select(
                options=[(m, m) for m in [
                    "gemini/gemini-3.1-flash-lite-preview",
                    "gemini/gemini-flash-latest",
                    "gemini/gemini-pro-latest",
                    "openai/gpt-4o",
                ]],
                value="gemini/gemini-3.1-flash-lite-preview",
                id="model-select"
            )
            yield Label("\n🤖 [bold]AGENTS DISPONIBLES[/bold]")
            agent_items = [ListItem(Label(f"• {name}")) for name in self.orchestrator.agents.keys()]
            yield ListView(*agent_items)
            yield Label("\n📈 [bold]STATUS[/bold]")
            yield Static("System: Online", id="status-text")
        
        with Vertical(id="chat-container"):
            yield ScrollableContainer(id="messages")
            with Horizontal(id="input-container"):
                yield Input(placeholder="Parlez à JARVIS...", id="user-input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_query = event.value
        if not user_query:
            return
        
        input_widget = self.query_one("#user-input", Input)
        input_widget.value = ""
        
        messages_container = self.query_one("#messages", ScrollableContainer)
        
        # Add user message
        user_msg = Static(f"[bold]Vous:[/bold] {user_query}", classes="user-msg")
        messages_container.mount(user_msg)
        messages_container.scroll_end()
        
        self.history.append({"role": "user", "content": user_query})
        
        # Thinking indicator
        status = self.query_one("#status-text", Static)
        status.update("System: Thinking...")
        
        # Call orchestrator
        try:
            response = await self.orchestrator.route(user_query, self.history)
            self.history.append({"role": "assistant", "content": response})
            
            agent_msg = Static(f"[bold]JARVIS:[/bold]\n{response}", classes="agent-msg")
            messages_container.mount(agent_msg)
            messages_container.scroll_end()
        except Exception as e:
            messages_container.mount(Static(f"Erreur: {str(e)}", classes="system-msg"))
        
        status.update("System: Online")

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "model-select":
            self.orchestrator.set_override_model(str(event.value))

if __name__ == "__main__":
    import os
    from core.orchestrator import Orchestrator
    # This block is for testing directly
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    orch = Orchestrator(os.path.join(project_root, "agents/configs"))
    app = JARVISApp(orch)
    app.run()
