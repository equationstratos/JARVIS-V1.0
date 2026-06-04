from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Input, Static, ListView, ListItem,
    Label, Select, Button, TextArea, Markdown,
)
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer, Grid
from textual.screen import ModalScreen
from textual.binding import Binding
from textual import events
from textual.reactive import reactive
from core.orchestrator import Orchestrator
import asyncio
import os
import re
import pyperclip


# ─────────────────────────── Modals ────────────────────────────

class SettingsScreen(ModalScreen):
    """Fenêtre modale Paramètres / Clés API."""

    CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-dialog {
        width: 70;
        height: auto;
        max-height: 40;
        background: #1e293b;
        border: solid #38bdf8;
        padding: 1 2;
    }
    #settings-title {
        text-align: center;
        color: #38bdf8;
        text-style: bold;
        margin-bottom: 1;
    }
    .settings-label {
        color: #94a3b8;
        margin-top: 1;
    }
    .settings-input {
        margin-bottom: 1;
    }
    #settings-buttons {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    Button {
        margin: 0 1;
    }
    #btn-save {
        background: #0ea5e9;
    }
    #btn-cancel {
        background: #475569;
    }
    """

    def compose(self) -> ComposeResult:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        anthropic_key = ""
        google_key = ""
        openai_key = ""
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY="):
                        anthropic_key = line.split("=", 1)[1].strip()
                    elif line.startswith("GOOGLE_API_KEY="):
                        google_key = line.split("=", 1)[1].strip()
                    elif line.startswith("OPENAI_API_KEY="):
                        openai_key = line.split("=", 1)[1].strip()

        with Container(id="settings-dialog"):
            yield Label("⚙️  PARAMÈTRES & CLÉS API", id="settings-title")
            yield Label("Clé Anthropic (Claude) :", classes="settings-label")
            yield Input(value=anthropic_key, placeholder="sk-ant-...", id="inp-anthropic", password=True, classes="settings-input")
            yield Label("Clé Google (Gemini) :", classes="settings-label")
            yield Input(value=google_key, placeholder="AIza...", id="inp-google", password=True, classes="settings-input")
            yield Label("Clé OpenAI (GPT) :", classes="settings-label")
            yield Input(value=openai_key, placeholder="sk-...", id="inp-openai", password=True, classes="settings-input")
            with Horizontal(id="settings-buttons"):
                yield Button("💾 Sauvegarder", id="btn-save", variant="primary")
                yield Button("✖ Annuler", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            anthropic = self.query_one("#inp-anthropic", Input).value.strip()
            google = self.query_one("#inp-google", Input).value.strip()
            openai_k = self.query_one("#inp-openai", Input).value.strip()
            self.dismiss({"anthropic": anthropic, "google": google, "openai": openai_k})

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class HelpScreen(ModalScreen):
    """Aide sur les commandes slash."""

    CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-dialog {
        width: 65;
        height: auto;
        background: #1e293b;
        border: solid #10b981;
        padding: 1 2;
    }
    """

    HELP_TEXT = """\
# Commandes JARVIS

| Commande | Description |
|---|---|
| `/help` | Afficher cette aide |
| `/clear` | Effacer la conversation |
| `/api` | Ouvrir les paramètres clés API |
| `/model <nom>` | Changer de modèle (ex: `/model gemini/gemini-2.0-flash`) |
| `/agents` | Lister les agents disponibles |
| `/status` | Afficher le statut du système |
| `/config` | Résumé de la configuration |
| `!commande` | Exécuter directement via ShellAgent |

**Clic droit** sur un message → Copier le texte
**Ctrl+L** → Effacer la conversation
**Ctrl+S** → Ouvrir les paramètres
**Ctrl+H** → Cette aide
**Escape** → Fermer les modals
"""

    def compose(self) -> ComposeResult:
        with Container(id="help-dialog"):
            yield Markdown(self.HELP_TEXT)
            with Horizontal(style="align: center middle; height: 3;"):
                yield Button("✖ Fermer", id="btn-close-help")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ContextMenu(Container):
    """Mini menu contextuel clic-droit."""

    CSS = """
    ContextMenu {
        width: 22;
        height: auto;
        background: #334155;
        border: solid #475569;
        layer: overlay;
        display: none;
    }
    ContextMenu.visible {
        display: block;
    }
    .ctx-item {
        padding: 0 1;
        color: #f8fafc;
        height: 1;
    }
    .ctx-item:hover {
        background: #0ea5e9;
        color: #ffffff;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("📋 Copier", classes="ctx-item", id="ctx-copy")
        yield Static("🧹 Tout effacer", classes="ctx-item", id="ctx-clear")
        yield Static("⚙️  Paramètres", classes="ctx-item", id="ctx-settings")

    def show_at(self, x: int, y: int) -> None:
        self.styles.offset = (x, y)
        self.add_class("visible")

    def hide(self) -> None:
        self.remove_class("visible")


# ──────────────────────── Application principale ────────────────────────

SLASH_COMMANDS = {
    "/help": "Afficher l'aide et les commandes disponibles",
    "/clear": "Effacer la conversation",
    "/api": "Ouvrir les paramètres des clés API",
    "/model": "Changer de modèle (ex: /model gemini/gemini-2.0-flash)",
    "/agents": "Lister tous les agents disponibles",
    "/status": "Afficher le statut du système",
    "/config": "Afficher le résumé de configuration",
}

AVAILABLE_MODELS = [
    ("gemini/gemini-2.0-flash", "gemini/gemini-2.0-flash"),
    ("gemini/gemini-3.1-flash-lite-preview", "gemini/gemini-3.1-flash-lite-preview"),
    ("gemini/gemini-pro-latest", "gemini/gemini-pro-latest"),
    ("claude-opus-4-8", "claude-opus-4-8"),
    ("claude-sonnet-4-6", "claude-sonnet-4-6"),
    ("claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001"),
    ("openai/gpt-4o", "openai/gpt-4o"),
    ("openai/gpt-4o-mini", "openai/gpt-4o-mini"),
]


class JARVISApp(App):
    TITLE = "JARVIS"
    SUB_TITLE = "v1.0"

    BINDINGS = [
        Binding("ctrl+l", "clear_chat", "Effacer"),
        Binding("ctrl+s", "open_settings", "Paramètres"),
        Binding("ctrl+h", "open_help", "Aide"),
        Binding("ctrl+q", "quit", "Quitter"),
    ]

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 3fr;
        background: #0f172a;
    }

    /* ── Barre de menu ── */
    #menubar {
        dock: top;
        height: 1;
        background: #1e3a5f;
        layout: horizontal;
        padding: 0 1;
    }
    .menu-btn {
        background: transparent;
        border: none;
        color: #cbd5e1;
        height: 1;
        min-width: 14;
        padding: 0 1;
    }
    .menu-btn:hover {
        background: #334155;
        color: #ffffff;
    }
    .menu-btn:focus {
        background: #0ea5e9;
        color: #ffffff;
    }

    /* ── Sidebar ── */
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
    #user-input {
        width: 1fr;
    }
    #send-btn {
        width: 10;
        background: #0ea5e9;
        border: none;
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
        padding: 0 1;
    }
    .error-msg {
        color: #f87171;
        background: #450a0a 20%;
        padding: 1;
        margin: 1 0;
        border-left: solid #ef4444;
    }
    .cmd-result {
        color: #86efac;
        background: #052e16 20%;
        padding: 1;
        margin: 1 0;
        border-left: solid #22c55e;
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
    Select {
        margin-bottom: 1;
    }
    """

    def __init__(self, orchestrator: Orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.history = []
        self._last_message_text = ""
        self._context_menu_visible = False

    def compose(self) -> ComposeResult:
        # Barre de menu en haut
        with Horizontal(id="menubar"):
            yield Button("⚡ JARVIS", classes="menu-btn", id="menu-home")
            yield Button("⚙️  Paramètres", classes="menu-btn", id="menu-settings")
            yield Button("🤖 Modèle", classes="menu-btn", id="menu-model")
            yield Button("❓ Aide", classes="menu-btn", id="menu-help")
            yield Button("✖ Quitter", classes="menu-btn", id="menu-quit")

        yield Header(show_clock=True)

        with Vertical(id="sidebar"):
            yield Label("🛠️ [bold]MODÈLE ACTIF[/bold]")
            yield Select(
                options=AVAILABLE_MODELS,
                value="gemini/gemini-2.0-flash",
                id="model-select",
            )
            yield Label("\n🤖 [bold]AGENTS DISPONIBLES[/bold]")
            agent_items = [ListItem(Label(f"• {name}")) for name in self.orchestrator.agents.keys()]
            yield ListView(*agent_items, id="agents-list")
            yield Label("\n📈 [bold]STATUS[/bold]")
            yield Static("System: Online", id="status-text")
            yield Label("\n💡 [bold]COMMANDES[/bold]")
            yield Static(
                "[dim]/help  /clear  /api\n/model  /agents  /status[/dim]",
                classes="system-msg",
            )

        with Vertical(id="chat-container"):
            yield ScrollableContainer(id="messages")
            with Horizontal(id="input-container"):
                yield Input(placeholder="Parlez à JARVIS... (/ pour les commandes)", id="user-input")
                yield Button("▶ Envoyer", id="send-btn")

        yield ContextMenu(id="context-menu")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#messages").mount(
            Static(
                "[bold green]JARVIS[/bold green] est en ligne. Tapez [bold]/help[/bold] pour les commandes disponibles.",
                classes="system-msg",
            )
        )

    # ── Boutons menu ────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "menu-settings" or btn_id == "ctx-settings":
            self.action_open_settings()
        elif btn_id == "menu-help":
            self.action_open_help()
        elif btn_id == "menu-quit":
            self.action_quit()
        elif btn_id == "menu-home":
            self.query_one("#user-input", Input).focus()
        elif btn_id == "menu-model":
            self.query_one("#model-select", Select).focus()
        elif btn_id == "send-btn":
            inp = self.query_one("#user-input", Input)
            self._process_input(inp.value)
            inp.value = ""
            inp.focus()
        elif btn_id == "ctx-copy":
            self._copy_last_message()
            self._hide_context_menu()
        elif btn_id == "ctx-clear":
            self.action_clear_chat()
            self._hide_context_menu()

    # ── Input soumis ────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "user-input":
            return
        text = event.value.strip()
        event.input.value = ""
        if text:
            await self._process_input(text)

    async def _process_input(self, text: str) -> None:
        if not text:
            return
        self._hide_context_menu()

        # Commandes slash
        if text.startswith("/"):
            await self._handle_slash_command(text)
            return

        messages = self.query_one("#messages", ScrollableContainer)
        user_msg = Static(f"[bold]Vous:[/bold] {text}", classes="user-msg")
        user_msg.can_focus = True
        messages.mount(user_msg)
        messages.scroll_end()
        self.history.append({"role": "user", "content": text})

        status = self.query_one("#status-text", Static)
        status.update("System: [yellow]Réflexion...[/yellow]")

        try:
            response = await self.orchestrator.route(text, self.history)
            self.history.append({"role": "assistant", "content": response})
            self._last_message_text = response

            agent_msg = Static(f"[bold green]JARVIS:[/bold green]\n{response}", classes="agent-msg")
            messages.mount(agent_msg)
            messages.scroll_end()
        except Exception as e:
            messages.mount(Static(f"⚠ Erreur: {str(e)}", classes="error-msg"))
            messages.scroll_end()

        status.update("System: [green]Online[/green]")

    # ── Commandes slash ─────────────────────────────────────────

    async def _handle_slash_command(self, text: str) -> None:
        messages = self.query_one("#messages", ScrollableContainer)
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        def show(content: str, cls: str = "cmd-result") -> None:
            messages.mount(Static(content, classes=cls))
            messages.scroll_end()

        if cmd == "/help":
            self.action_open_help()

        elif cmd == "/clear":
            self.action_clear_chat()

        elif cmd == "/api":
            self.action_open_settings()

        elif cmd == "/agents":
            names = list(self.orchestrator.agents.keys())
            show("🤖 [bold]Agents disponibles:[/bold]\n" + "\n".join(f"  • {n}" for n in names))

        elif cmd == "/status":
            model = self.orchestrator.override_model or "auto"
            agents_count = len(self.orchestrator.agents)
            history_count = len(self.history)
            show(
                f"📊 [bold]Statut JARVIS[/bold]\n"
                f"  Modèle actif : {model}\n"
                f"  Agents chargés : {agents_count}\n"
                f"  Messages dans l'historique : {history_count}\n"
                f"  Cache routage : {len(self.orchestrator._route_cache)} entrées"
            )

        elif cmd == "/config":
            from config import JARVISConfig
            show(f"⚙️  [bold]Configuration[/bold]\n{JARVISConfig.summary()}")

        elif cmd == "/model":
            if not arg:
                current = self.orchestrator.override_model or "auto (selon l'agent)"
                models = "\n".join(f"  • {m}" for m, _ in AVAILABLE_MODELS)
                show(f"🔧 Modèle actuel: [cyan]{current}[/cyan]\n\nModèles disponibles:\n{models}")
            else:
                self.orchestrator.set_override_model(arg)
                show(f"✅ Modèle changé → [cyan]{arg}[/cyan]")
                status = self.query_one("#status-text", Static)
                status.update(f"System: [green]Online[/green] | Modèle: {arg}")

        else:
            show(f"❓ Commande inconnue: [red]{cmd}[/red]\nTapez [bold]/help[/bold] pour la liste des commandes.", "error-msg")

    # ── Clic droit / menu contextuel ────────────────────────────

    def on_click(self, event: events.Click) -> None:
        if event.button == 3:  # clic droit
            ctx = self.query_one("#context-menu", ContextMenu)
            ctx.show_at(event.screen_x, event.screen_y)
            self._context_menu_visible = True
            event.stop()
        else:
            if self._context_menu_visible:
                self._hide_context_menu()

    def _hide_context_menu(self) -> None:
        self.query_one("#context-menu", ContextMenu).hide()
        self._context_menu_visible = False

    def _copy_last_message(self) -> None:
        try:
            pyperclip.copy(self._last_message_text)
            self.notify("Copié dans le presse-papiers !", severity="information")
        except Exception:
            self.notify("Impossible de copier (pyperclip)", severity="warning")

    # ── Actions ─────────────────────────────────────────────────

    def action_clear_chat(self) -> None:
        messages = self.query_one("#messages", ScrollableContainer)
        messages.remove_children()
        self.history.clear()
        messages.mount(Static("🗑️ Conversation effacée.", classes="system-msg"))

    def action_open_settings(self) -> None:
        def _on_close(result) -> None:
            if result is None:
                return
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
            lines = []
            if os.path.exists(env_path):
                with open(env_path) as f:
                    lines = f.readlines()

            def _set_env(lines, key, value):
                found = False
                for i, line in enumerate(lines):
                    if line.startswith(f"{key}="):
                        lines[i] = f"{key}={value}\n"
                        found = True
                        break
                if not found and value:
                    lines.append(f"{key}={value}\n")
                return lines

            if result.get("anthropic"):
                lines = _set_env(lines, "ANTHROPIC_API_KEY", result["anthropic"])
                os.environ["ANTHROPIC_API_KEY"] = result["anthropic"]
            if result.get("google"):
                lines = _set_env(lines, "GOOGLE_API_KEY", result["google"])
                os.environ["GOOGLE_API_KEY"] = result["google"]
            if result.get("openai"):
                lines = _set_env(lines, "OPENAI_API_KEY", result["openai"])
                os.environ["OPENAI_API_KEY"] = result["openai"]

            with open(env_path, "w") as f:
                f.writelines(lines)

            self.notify("✅ Clés API sauvegardées dans .env", severity="information")

        self.push_screen(SettingsScreen(), _on_close)

    def action_open_help(self) -> None:
        self.push_screen(HelpScreen())

    # ── Changement de modèle (Select sidebar) ────────────────────

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "model-select":
            model = str(event.value)
            self.orchestrator.set_override_model(model)
            status = self.query_one("#status-text", Static)
            status.update(f"System: [green]Online[/green]\nModèle: {model.split('/')[-1]}")


if __name__ == "__main__":
    from core.orchestrator import Orchestrator
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    orch = Orchestrator(os.path.join(project_root, "agents/configs"))
    app = JARVISApp(orch)
    app.run()
