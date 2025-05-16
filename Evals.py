import asyncio
import subprocess
import multiprocessing
import os
import sys
import tempfile
import time
from typing import List, Tuple
from enum import Enum
from pathlib import Path
import docker
import redis
import ray
import pydantic
import structlog
import loguru
from prometheus_client import Counter, Histogram, start_http_server
from rich.console import Console
from rich.table import Table
from cachetools import TTLCache
import orjson
import msgpack
import bleach
from tenacity import retry, stop_after_attempt, wait_exponential
import psutil
import resource
import typer
from tqdm import tqdm
import humanize
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from concurrent.futures import ThreadPoolExecutor
import pyinstrument
from pyrogram import Client, filters
import platform
import shlex

structlog.configure(processors=[structlog.processors.JSONRenderer()])
logger = structlog.get_logger()
loguru.logger.add("execution.log", rotation="10 MB")
EXECUTION_COUNT = Counter("code_executions_total", "Total code executions", ["language"])
EXECUTION_TIME = Histogram("code_execution_duration_seconds", "Execution duration", ["language"])
console = Console()
redis_client = redis.Redis(host="localhost", port=6379, db=0)
cache = TTLCache(maxsize=1000, ttl=3600)
app = typer.Typer()

class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    SHELL = "shell"
    BASH = "bash"

class ExecutionResult(pydantic.BaseModel):
    stdout: str
    stderr: str
    returncode: int
    language: Language
    execution_time: float
    success: bool = pydantic.Field(default_factory=lambda: False)

class CodeSnippet(pydantic.BaseModel):
    code: str
    language: Language

class ExecutionConfig(pydantic.BaseModel):
    timeout: float = 10.0
    max_processes: int = multiprocessing.cpu_count()
    use_docker: bool = False
    max_memory_mb: int = 512
    retry_attempts: int = 3
    cache_results: bool = True

class CodeExecutor:
    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.process_pool = multiprocessing.Pool(processes=config.max_processes)
        self.docker_client = docker.from_env() if config.use_docker else None
        self.loop = asyncio.get_event_loop()
        self.thread_pool = ThreadPoolExecutor(max_workers=config.max_processes)
        ray.init(ignore_reinit_error=True)
        start_http_server(8001)
        self._setup_resource_limits()
        self.env = {}
        self.history = []
        self.platform = self._detect_platform()

    def _detect_platform(self):
        plat = platform.system().lower()
        if "linux" in plat:
            if "com.termux" in os.environ.get("PREFIX", ""):
                return "termux"
            if os.environ.get("CODESPACES") == "true":
                return "codespaces"
        if "windows" in plat:
            return "windows"
        if "darwin" in plat:
            return "macos"
        return "unknown"

    def _setup_resource_limits(self):
        memory_bytes = self.config.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

    def _generate_secure_filename(self, code: str) -> str:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=16,
            salt=os.urandom(16),
            iterations=100000,
        )
        return kdf.derive(code.encode()).hex()

    def _sanitize_code(self, code: str) -> str:
        return bleach.clean(code, tags=[], attributes={})

    def _write_temp_file(self, code: str, lang: Language) -> str:
        suffix = {
            Language.PYTHON: ".py",
            Language.JAVASCRIPT: ".js",
            Language.SHELL: ".sh",
            Language.BASH: ".bash"
        }[lang]
        file_name = self._generate_secure_filename(code)
        file_path = Path(tempfile.gettempdir()) / f"{file_name}{suffix}"
        file_path.write_text(code)
        if lang in (Language.SHELL, Language.BASH):
            file_path.chmod(0o755)
        return str(file_path)

    def _cleanup_temp_file(self, file_path: str):
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError as e:
            logger.error(f"Failed to delete {file_path}: {e}")

    def _auto_detect_language(self, code: str) -> str:
        code = code.strip()
        py_keywords = ["def ", "import ", "print(", "class ", "async ", "await "]
        js_keywords = ["console.log", "function ", "var ", "let ", "const ", "=>", "import ", "export "]
        bash_keywords = ["echo ", "ls", "pwd", "cd ", "cat ", "grep ", "rm "]
        if any(kw in code for kw in py_keywords):
            return "python"
        if any(kw in code for kw in js_keywords):
            return "javascript"
        if any(kw in code for kw in bash_keywords):
            return "bash"
        return "python"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _execute_single(self, code: str, lang: Language) -> ExecutionResult:
        start_time = time.time()
        code = self._sanitize_code(code)
        cache_key = f"{lang.value}:{hash(code)}"
        self.history.append((lang.value, code))

        if self.config.cache_results and cache_key in cache:
            logger.info(f"Cache hit for {cache_key}")
            return ExecutionResult(**cache[cache_key])

        with pyinstrument.Profiler():
            try:
                if lang == Language.PYTHON:
                    result = await self._run_python(code)
                elif lang == Language.JAVASCRIPT:
                    result = await self._execute_local(code, lang)
                else:
                    result = await self._run_bash(code) if self.platform != "windows" else await self._execute_local(code, lang)
                
                EXECUTION_COUNT.labels(language=lang.value).inc()
                EXECUTION_TIME.labels(language=lang.value).observe(time.time() - start_time)
                
                if self.config.cache_results:
                    cache[cache_key] = result.dict()
                    redis_client.setex(cache_key, 3600, msgpack.packb(result.dict()))
                
                logger.info(f"Executed {lang.value} code", result=result.dict())
                return result
            
            except Exception as e:
                logger.error(f"Execution failed: {str(e)}", exc_info=True)
                return ExecutionResult(
                    stdout="", stderr=str(e), returncode=1, language=lang,
                    execution_time=time.time() - start_time, success=False
                )

    async def _run_python(self, code: str) -> ExecutionResult:
        start_time = time.time()
        try:
            local_env = {}
            compiled = compile(code, "<string>", "exec")
            exec(compiled, self.env, local_env)
            if "result" in local_env:
                return ExecutionResult(
                    stdout=str(local_env["result"]), stderr="", returncode=0, language=Language.PYTHON,
                    execution_time=time.time() - start_time, success=True
                )
            try:
                val = eval(code, self.env, local_env)
                if val is not None:
                    return ExecutionResult(
                        stdout=str(val), stderr="", returncode=0, language=Language.PYTHON,
                        execution_time=time.time() - start_time, success=True
                    )
            except:
                pass
            return ExecutionResult(
                stdout="[Python] Executed", stderr="", returncode=0, language=Language.PYTHON,
                execution_time=time.time() - start_time, success=True
            )
        except Exception as e:
            return ExecutionResult(
                stdout="", stderr=f"[Python Error] {e}", returncode=1, language=Language.PYTHON,
                execution_time=time.time() - start_time, success=False
            )

    async def _run_bash(self, code: str) -> ExecutionResult:
        start_time = time.time()
        try:
            proc = await asyncio.create_subprocess_shell(
                code, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.config.timeout)
            return ExecutionResult(
                stdout=out.decode().strip(), stderr=err.decode().strip(), returncode=proc.returncode,
                language=Language.BASH, execution_time=time.time() - start_time, success=proc.returncode == 0
            )
        except Exception as e:
            return ExecutionResult(
                stdout="", stderr=f"[Bash Error] {e}", returncode=1, language=Language.BASH,
                execution_time=time.time() - start_time, success=False
            )

    async def _execute_local(self, code: str, lang: Language) -> ExecutionResult:
        start_time = time.time()
        try:
            if lang == Language.JAVASCRIPT:
                file_path = self._write_temp_file(code, lang)
                cmd = ["node", file_path]
            else:
                file_path = self._write_temp_file(code, lang)
                cmd = [file_path]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.config.timeout)
            result = ExecutionResult(
                stdout=out.decode().strip(), stderr=err.decode().strip(), returncode=proc.returncode,
                language=lang, execution_time=time.time() - start_time, success=proc.returncode == 0
            )
            return result
        
        except Exception as e:
            return ExecutionResult(
                stdout="", stderr=f"[Error] {e}", returncode=1, language=lang,
                execution_time=time.time() - start_time, success=False
            )
        finally:
            self._cleanup_temp_file(file_path)

    @ray.remote
    def _execute_distributed(self, code: str, lang: str) -> ExecutionResult:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._execute_single(code, Language[lang.upper()]))
        finally:
            loop.close()

    async def execute_batch(self, snippets: List[CodeSnippet]) -> List[ExecutionResult]:
        results = []
        if os.getenv("USE_RAY", "0") == "1":
            futures = [self._execute_distributed.remote(self, s.code, s.language.value) for s in snippets]
            results = ray.get(futures)
        else:
            tasks = [self._execute_single(s.code, s.language) for s in snippets]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        table = Table(title="Execution Results")
        table.add_column("Language", style="cyan")
        table.add_column("Success", style="green")
        table.add_column("Time", style="magenta")
        table.add_column("Output", style="white", overflow="fold")
        for r in results:
            table.add_row(
                r.language.value, str(r.success), humanize.naturaldelta(r.execution_time), r.stdout or r.stderr
            )
        console.print(table)
        return results

    def get_history(self):
        return self.history

    def __del__(self):
        if hasattr(self, 'process_pool'):
            self.process_pool.close()
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown()
        ray.shutdown()

bot = Client("code_executor_bot", api_id="YOUR_API_ID", api_hash="YOUR_API_HASH", bot_token="YOUR_BOT_TOKEN")
executor = CodeExecutor(ExecutionConfig())

@bot.on_message(filters.command("ex") & filters.private)
async def execute(client, message):
    text = message.text or ""
    if len(text.split(None, 1)) < 2:
        await message.reply("Use /ex <language?> <code> or just /ex <code>. Language auto-detected.")
        return
    parts = text.split(None, 2)
    if len(parts) == 3 and parts[1].lower() in ["python", "py", "js", "javascript", "bash"]:
        lang = parts[1].lower()
        if lang == "py":
            lang = "python"
        code = parts[2]
    else:
        lang = executor._auto_detect_language(text.split(None, 1)[1])
        code = text.split(None, 1)[1]

    await message.reply("Executing your code...")
    snippet = CodeSnippet(code=code, language=Language[lang.upper()])
    results = await executor.execute_batch([snippet])
    result = results[0]
    output = result.stdout or result.stderr
    if len(output) > 4000:
        await message.reply("Output too long to display.")
    else:
        await message.reply(f"Output:\n{output}")

class ConfigReloadHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("config.json"):
            console.print("[bold green]Config updated, reloading...[/bold green]")

if __name__ == "__main__":
    observer = Observer()
    observer.schedule(ConfigReloadHandler(), path=".", recursive=False)
    observer.start()
    bot.run()
    observer.stop()
    observer.join()
