"""
Agent JARVIS — version optimisée

Optimisations clés :
- Streaming token-par-token via litellm stream=True
- Blackboard sérialisé en cache (évite re-JSON à chaque message)
- Sliding window sur l'historique (évite envoi croissant)
- Tools exécutés en parallèle quand possible
- System prompt précompilé une fois au chargement
"""
import json
import os
import time
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Optional
import litellm
from core.blackboard import Blackboard
from utils.shell_utils import execute_shell_async, write_file
from utils.web_utils import search_duckduckgo
from utils.validator import ResponseValidator
from utils.cache_manager import CacheManager


# Format markdown commun (compilé une fois)
FORMAT_INSTRUCTIONS = (
    "\n\nFORMATAGE:\n"
    "- Sois concis et structuré.\n"
    "- Markdown autorisé. Code dans ```lang ... ```.\n"
    "- Listes à puces si pertinent."
)


class Agent:
    def __init__(self, config_path: str, cache_manager: Optional[CacheManager] = None):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        self.name = self.config["name"]
        # System prompt précompilé (sans blackboard, ajouté à la volée)
        self._base_system = self.config["system_prompt"] + FORMAT_INSTRUCTIONS
        self.model = self.config.get("model", "claude-opus-4-7")
        self.skills = self.config.get("skills", [])
        self.history_limit = self.config.get("history_limit", 10)
        self.temperature = self.config.get("temperature", 0.3)
        self.max_tokens = self.config.get("max_tokens", 1024)
        self.routing_keywords = self.config.get("routing_keywords", [])
        self.enable_validation = self.config.get("enable_validation", False)
        self.tools = self._setup_tools()
        # Cache de la dernière sérialisation blackboard
        self._bb_cache_key: Optional[int] = None
        self._bb_cache_str: str = ""
        # Validator et Cache
        self.validator = ResponseValidator(self.model)
        self.cache_manager = cache_manager

    def _setup_tools(self):
        tools = []
        if "shell_executor" in self.skills:
            tools.append({
                "type": "function",
                "function": {
                    "name": "execute_shell",
                    "description": "Execute a shell command and return output",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                },
            })
        if "file_writer" in self.skills:
            tools.append({
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write or update a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
            })
        if "file_reader" in self.skills:
            tools.append({
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file and return its content",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            })
        if "web_search" in self.skills:
            tools.append({
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for information",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            })
        if "web_fetch" in self.skills:
            tools.append({
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": "Fetch and parse content from a URL",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                },
            })
        if "code_executor" in self.skills:
            tools.append({
                "type": "function",
                "function": {
                    "name": "execute_code",
                    "description": "Execute Python code (for testing/validation only)",
                    "parameters": {
                        "type": "object",
                        "properties": {"code": {"type": "string"}},
                        "required": ["code"],
                    },
                },
            })
        return tools or None

    def _build_system(self, blackboard_data: Dict[str, Any]) -> str:
        """Construit le system prompt avec cache du blackboard."""
        if not blackboard_data:
            return self._base_system
        # Cache : on hash le dict pour détecter les changements
        key = hash(json.dumps(blackboard_data, sort_keys=True, default=str))
        if key != self._bb_cache_key:
            self._bb_cache_str = (
                f"\n\n[SHARED CONTEXT]\n"
                f"{json.dumps(blackboard_data, indent=2, default=str)}"
            )
            self._bb_cache_key = key
        return self._base_system + self._bb_cache_str

    def _build_messages(
        self, prompt: str, history: List[Dict[str, str]],
        blackboard_data: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Construit la liste de messages avec sliding window."""
        messages = [{"role": "system", "content": self._build_system(blackboard_data)}]
        # Sliding window : ne garder que les N derniers messages
        if history:
            # Filtrer les messages valides (role + content)
            valid_history = [
                m for m in history[-self.history_limit:]
                if m.get("role") in ("user", "assistant") and m.get("content")
            ]
            messages.extend(valid_history)
        messages.append({"role": "user", "content": prompt})
        return messages

    async def _read_file_async(self, path: str) -> str:
        """Lit un fichier de manière asynchrone."""
        try:
            import aiofiles
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
            return f"File content ({path}):\n{content}"
        except ImportError:
            import os
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                return f"File content ({path}):\n{content}"
            except Exception as e:
                return f"Error reading file: {e}"

    async def _web_fetch(self, url: str) -> str:
        """Récupère et parse le contenu d'une URL."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return f"Error: HTTP {resp.status}"
                    content = await resp.text()
                    # Extraire le texte brut (simple version)
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, "html.parser")
                    # Supprimer scripts et styles
                    for script in soup(["script", "style"]):
                        script.decompose()
                    text = soup.get_text()
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    return f"Content from {url} ({len(text)} chars):\n{text[:2000]}..."
        except Exception as e:
            return f"Error fetching URL: {e}"

    async def _execute_code(self, code: str) -> str:
        """Exécute du code Python de manière sécurisée."""
        try:
            import subprocess
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return f"Code error:\n{result.stderr}"
            return f"Code output:\n{result.stdout}"
        except subprocess.TimeoutExpired:
            return "Error: Code execution timeout"
        except Exception as e:
            return f"Error executing code: {e}"

    async def _execute_tool(self, fn_name: str, args: Dict[str, Any]) -> str:
        """Exécute un outil de manière asynchrone."""
        try:
            if fn_name == "execute_shell":
                t0 = time.time()
                chunks = []
                async for line in execute_shell_async(args["command"]):
                    chunks.append(line)
                duration = time.time() - t0
                return f"--- TERMINAL ({duration:.2f}s) ---\n{''.join(chunks)}\n---"
            elif fn_name == "write_file":
                return write_file(args["path"], args["content"])
            elif fn_name == "read_file":
                return await self._read_file_async(args["path"])
            elif fn_name == "web_search":
                return await search_duckduckgo(args["query"])
            elif fn_name == "web_fetch":
                return await self._web_fetch(args["url"])
            elif fn_name == "execute_code":
                return await self._execute_code(args["code"])
            else:
                return f"Error: unknown tool {fn_name}"
        except Exception as e:
            return f"Tool error ({fn_name}): {str(e)}"

    # ── API non-streaming (compatibilité) ──
    async def execute(
        self, prompt: str, history: List[Dict[str, str]],
        blackboard: Blackboard, model_override: Optional[str] = None,
    ) -> str:
        # Vérifier le cache
        if self.cache_manager:
            cached = await self.cache_manager.get_cached_response(prompt, self.name)
            if cached:
                response, confidence = cached
                if confidence > 0.7:
                    return response

        active_model = model_override or self.model
        bb_data = await blackboard.get_all()
        messages = self._build_messages(prompt, history, bb_data)

        try:
            response = await litellm.acompletion(
                model=active_model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto" if self.tools else None,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=60,
            )
        except Exception as e:
            return f"⚠ Erreur d'exécution : {str(e)}"

        msg = response.choices[0].message

        # Tool calls : exécution parallèle
        if msg.tool_calls:
            messages.append(msg.model_dump())
            tool_results = await asyncio.gather(*[
                self._execute_tool(tc.function.name, json.loads(tc.function.arguments))
                for tc in msg.tool_calls
            ])
            for tc, result in zip(msg.tool_calls, tool_results):
                messages.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "name": tc.function.name,
                    "content": result,
                })
            try:
                final = await litellm.acompletion(
                    model=active_model, messages=messages, timeout=60
                )
                content = final.choices[0].message.content or "Tâche traitée."
            except Exception as e:
                return f"⚠ Erreur après tool : {str(e)}"
        else:
            content = msg.content
            if not content or content.strip() in ("", "{}"):
                return "Aucune réponse générée."

        # Validation optionnelle
        if self.enable_validation:
            content, validation = await self.validator.validate_and_improve(
                prompt, content, self.name, max_retries=1
            )
            if self.cache_manager:
                await self.cache_manager.cache_response(
                    prompt, content, self.name, validation.get("confidence", 0.8)
                )
        else:
            if self.cache_manager:
                await self.cache_manager.cache_response(prompt, content, self.name, 0.8)

        return content

    # ── API streaming (clé pour la fluidité) ──
    async def execute_stream(
        self, prompt: str, history: List[Dict[str, str]],
        blackboard: Blackboard, model_override: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield {type: 'token'|'tool'|'done'|'error', data: ...}"""
        active_model = model_override or self.model
        bb_data = await blackboard.get_all()
        messages = self._build_messages(prompt, history, bb_data)

        try:
            stream = await litellm.acompletion(
                model=active_model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto" if self.tools else None,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
                timeout=60,
            )
        except Exception as e:
            yield {"type": "error", "data": f"Init stream error: {e}"}
            return

        # Accumulateurs
        full_content = []
        tool_calls_buf: Dict[int, Dict[str, Any]] = {}

        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue
                # Tokens texte
                if getattr(delta, "content", None):
                    full_content.append(delta.content)
                    yield {"type": "token", "data": delta.content}
                # Tool calls (accumulation par index)
                if getattr(delta, "tool_calls", None):
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {
                                "id": tc.id or f"call_{idx}",
                                "name": "",
                                "args": "",
                            }
                        if tc.function:
                            if tc.function.name:
                                tool_calls_buf[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_buf[idx]["args"] += tc.function.arguments
        except Exception as e:
            yield {"type": "error", "data": f"Stream error: {e}"}
            return

        # Pas de tool calls : c'est terminé
        if not tool_calls_buf:
            yield {"type": "done", "data": "".join(full_content)}
            return

        # Tool calls : on exécute en parallèle puis on streame la réponse finale
        tool_calls_list = [tool_calls_buf[k] for k in sorted(tool_calls_buf)]
        for tc in tool_calls_list:
            yield {"type": "tool", "data": {"name": tc["name"], "status": "running"}}

        try:
            tool_results = await asyncio.gather(*[
                self._execute_tool(tc["name"], json.loads(tc["args"] or "{}"))
                for tc in tool_calls_list
            ])
        except Exception as e:
            yield {"type": "error", "data": f"Tool exec error: {e}"}
            return

        # Reconstruire le message assistant avec tool_calls
        messages.append({
            "role": "assistant",
            "content": "".join(full_content) or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["args"]},
                }
                for tc in tool_calls_list
            ],
        })
        for tc, result in zip(tool_calls_list, tool_results):
            yield {"type": "tool", "data": {"name": tc["name"], "status": "done"}}
            messages.append({
                "tool_call_id": tc["id"],
                "role": "tool",
                "name": tc["name"],
                "content": result,
            })

        # Stream final
        final_content = []
        try:
            final_stream = await litellm.acompletion(
                model=active_model, messages=messages, stream=True, timeout=60
            )
            async for chunk in final_stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and getattr(delta, "content", None):
                    final_content.append(delta.content)
                    yield {"type": "token", "data": delta.content}
        except Exception as e:
            yield {"type": "error", "data": f"Final stream error: {e}"}
            return

        yield {"type": "done", "data": "".join(final_content)}
