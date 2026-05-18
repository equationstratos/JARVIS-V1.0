"""
Shell utils — version optimisée avec streaming asyncio natif.

Optimisations :
- Vraie exécution async (asyncio.create_subprocess_exec / shell)
- Streaming ligne-par-ligne sans bloquer l'event loop
- Pas de subprocess.Popen synchrone qui bloque
"""
import asyncio
import os
import shlex
from typing import AsyncGenerator, Generator


# Commandes bloquées (commandes destructives évidentes)
_BLOCKLIST = ("rm -rf /", "mkfs", "dd if=/dev/", ":(){ :|:&", "> /dev/sda")


def _is_blocked(command: str) -> bool:
    cmd_lower = command.strip().lower()
    return any(b in cmd_lower for b in _BLOCKLIST)


async def execute_shell_async(
    command: str, timeout: int = 120
) -> AsyncGenerator[str, None]:
    """Exécute une commande shell en streamant la sortie ligne par ligne (async)."""
    if _is_blocked(command):
        yield "Error: Command blocked for security reasons.\n"
        return

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.getcwd(),
        )
    except Exception as e:
        yield f"Exception spawning process: {e}\n"
        return

    try:
        # Stream ligne par ligne avec timeout global
        async def _read_lines():
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield line.decode("utf-8", errors="replace")

        try:
            async for line in _read_with_timeout(_read_lines(), timeout):
                yield line
        except asyncio.TimeoutError:
            proc.kill()
            yield "\nError: Command timed out.\n"
            return

        rc = await proc.wait()
        if rc != 0:
            yield f"\n[exit code {rc}]\n"
    except Exception as e:
        yield f"\nException: {e}\n"
        try:
            proc.kill()
        except Exception:
            pass


async def _read_with_timeout(gen, timeout: int):
    """Wrap un async generator avec un timeout global."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise asyncio.TimeoutError()
        try:
            line = await asyncio.wait_for(gen.__anext__(), timeout=remaining)
        except StopAsyncIteration:
            return
        yield line


# ── Compatibilité avec l'ancienne API synchrone ──
def execute_shell(command: str, timeout: int = 120) -> Generator[str, None, None]:
    """Version synchrone pour compatibilité (à éviter dans le code async)."""
    import subprocess

    if _is_blocked(command):
        yield "Error: Command blocked for security reasons."
        return

    try:
        proc = subprocess.Popen(
            command, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=os.getcwd(), bufsize=1,
        )
        for line in iter(proc.stdout.readline, ""):
            yield line
        proc.stdout.close()
        rc = proc.wait(timeout=timeout)
        if rc != 0:
            yield f"\n[exit code {rc}]"
    except subprocess.TimeoutExpired:
        yield "\nError: Command timed out."
    except Exception as e:
        yield f"\nException: {e}"


def write_file(path: str, content: str) -> str:
    """Écrit un fichier de manière sécurisée."""
    try:
        abs_path = os.path.abspath(path)
        parent = os.path.dirname(abs_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File successfully written to {path}"
    except Exception as e:
        return f"Error writing file: {e}"
