import io
import re
import os
import sys
import json
import html
import httpx
import aiohttp
import asyncio
import requests
import traceback
import contextlib
import cloudscraper
from time import time
from os import environ as env
from pyrogram import Client, filters, idle
from bs4 import BeautifulSoup
from inspect import getfullargspec
from pyrogram.enums import ParseMode
from typing import Optional, Tuple, Any, List
from pyrogram.errors import MessageTooLong
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import ast
import subprocess
import tempfile
from pathlib import Path
import redis
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
from tqdm import tqdm
import humanize
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import pyinstrument
import platform
import shlex
from datetime import datetime

structlog.configure(processors=[structlog.processors.JSONRenderer()])
logger = structlog.get_logger()
loguru.logger.add("execution.log", rotation="10 MB")
EXECUTION_COUNT = Counter("code_executions_total", "Total code executions", ["language"])
EXECUTION_TIME = Histogram("code_execution_duration_seconds", "Execution duration", ["language"])
console = Console()
try:
    redis_client = redis.Redis(host="localhost", port=6379, db=0)
    redis_client.ping()
except redis.ConnectionError as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None
cache = TTLCache(maxsize=1000, ttl=3600)

var = {}
teskode = {}

class Config:
    try:
        SUDOERS = list(map(int, env.get("SUDOERS", "6505111743 6517565595 5896960462 5220416927").split()))
        PREFIXS = list(env.get("PREFIXS", "? * $ . ! /").split())
        API_ID = int(env.get("API_ID", "29400566"))
        API_HASH = str(env.get("API_HASH", "8fd30dc496aea7c14cf675f59b74ec6f"))
        BOT_TOKEN = str(env.get("BOT_TOKEN", "8054875786:AAG3YDeTKlFJv9tvXJuQQUABECmYI9gFbJk"))
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to load environment variables: {e}")
        raise SystemExit("Please set API_ID, API_HASH, BOT_TOKEN, SUDOERS, and PREFIXS environment variables.")

app = Client(
    name="CodeExecutorBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

async def WebScrap(Link: str, *args, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.get(Link, *args, **kwargs) as response:
            try:
                data = await response.json()
            except Exception:
                data = await response.text()
    return data

Fetch = httpx.AsyncClient(
    http2=True,
    verify=False,
    headers={
        "Accept-Language": "en-US,en;q=0.9,id-ID;q=0.8,id;q=0.7",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edge/107.0.1418.42"
    },
    timeout=httpx.Timeout(20)
)

async def myEval(code, globs, **kwargs):
    locs = {}
    globs = globs.copy()
    global_args = "_globs"
    while global_args in globs.keys():
        global_args = f"_{global_args}"
    kwargs[global_args] = {}
    for glob in ["__name__", "__package__"]:
        kwargs[global_args][glob] = globs[glob]
    root = ast.parse(code, "exec")
    code_nodes = root.body
    ret_name = "_ret"
    ok = False
    while True:
        if ret_name in globs.keys():
            ret_name = f"_{ret_name}"
            continue
        for node in ast.walk(root):
            if isinstance(node, ast.Name) and node.id == ret_name:
                ret_name = f"_{ret_name}"
                break
            ok = True
        if ok:
            break
    if not code_nodes:
        return None
    if not any(isinstance(node, ast.Return) for node in code_nodes):
        for i in range(len(code_nodes)):
            if isinstance(code_nodes[i], ast.Expr) and (
                i == len(code_nodes) - 1 or not isinstance(code_nodes[i].value, ast.Call)
            ):
                code_nodes[i] = ast.copy_location(
                    ast.Expr(
                        ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id=ret_name, ctx=ast.Load()),
                                attr="append",
                                ctx=ast.Load(),
                            ),
                            args=[code_nodes[i].value],
                            keywords=[],
                        )
                    ),
                    code_nodes[-1],
                )
    else:
        for node in code_nodes:
            if isinstance(node, ast.Return):
                node.value = ast.List(elts=[node.value], ctx=ast.Load())
    code_nodes.append(
        ast.copy_location(
            ast.Return(value=ast.Name(id=ret_name, ctx=ast.Load())), code_nodes[-1]
        )
    )
    glob_copy = ast.Expr(
        ast.Call(
            func=ast.Attribute(
                value=ast.Call(
                    func=ast.Name(id="globals", ctx=ast.Load()), args=[], keywords=[]
                ),
                attr="update",
                ctx=ast.Load(),
            ),
            args=[],
            keywords=[
                ast.keyword(arg=None, value=ast.Name(id=global_args, ctx=ast.Load()))
            ],
        )
    )
    ast.fix_missing_locations(glob_copy)
    code_nodes.insert(0, glob_copy)
    ret_decl = ast.Assign(
        targets=[ast.Name(id=ret_name, ctx=ast.Store())],
        value=ast.List(elts=[], ctx=ast.Load()),
    )
    ast.fix_missing_locations(ret_decl)
    code_nodes.insert(1, ret_decl)
    args = []
    for a in list(map(lambda x: ast.arg(x, None), kwargs.keys())):
        ast.fix_missing_locations(a)
        args += [a]
    args = ast.arguments(
        args=[],
        vararg=None,
        kwonlyargs=args,
        kwarg=None,
        defaults=[],
        kw_defaults=[None for _ in range(len(args))],
    )
    args.posonlyargs = []
    fun = ast.AsyncFunctionDef(
        name="tmp", args=args, body=code_nodes, decorator_list=[], returns=None
    )
    ast.fix_missing_locations(fun)
    mod = ast.parse("")
    mod.body = [fun]
    comp = compile(mod, "<string>", "exec")
    exec(comp, {}, locs)
    r = await locs["tmp"](**kwargs)
    for i in range(len(r)):
        if hasattr(r[i], "__await__"):
            r[i] = await r[i]
    i = 0
    while i < len(r) - 1:
        if r[i] is None:
            del r[i]
        else:
            i += 1
    if len(r) == 1:
        [r] = r
    elif not r:
        r = None
    return r

def format_exception(exp: BaseException, tb: Optional[List[traceback.FrameSummary]] = None) -> str:
    if tb is None:
        tb = traceback.extract_tb(exp.__traceback__)
    cwd = os.getcwd()
    for frame in tb:
        if cwd in frame.filename:
            frame.filename = os.path.relpath(frame.filename)
    stack = "".join(traceback.format_list(tb))
    msg = str(exp)
    if msg:
        msg = f": {msg}"
    return f"Traceback (most recent call last):\n{stack}{type(exp).__name__}{msg}"

def readable_Time(seconds: float) -> str:
    result = ""
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f"{days}d:"
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f"{hours}h:"
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f"{minutes}m:"
    seconds = int(seconds)
    result += f"{seconds}s"
    return result or "0.1s"

async def eos_Send(msg, **kwargs):
    func = msg.edit if msg.from_user.is_self else msg.reply
    spec = getfullargspec(func.__wrapped__).args
    await func(**{k: v for k, v in kwargs.items() if k in spec})

class Language:
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    SHELL = "shell"
    BASH = "bash"

class ExecutionResult(pydantic.BaseModel):
    stdout: str
    stderr: str
    returncode: int
    language: str
    execution_time: float
    success: bool = pydantic.Field(default_factory=lambda: False)

    @pydantic.validator("language")
    def validate_language(cls, v):
        valid_languages = {Language.PYTHON, Language.JAVASCRIPT, Language.SHELL, Language.BASH}
        if v not in valid_languages:
            raise ValueError(f"Language must be one of {valid_languages}")
        return v

class CodeSnippet(pydantic.BaseModel):
    code: str
    language: str

    @pydantic.validator("language")
    def validate_language(cls, v):
        valid_languages = {Language.PYTHON, Language.JAVASCRIPT, Language.SHELL, Language.BASH}
        if v not in valid_languages:
            raise ValueError(f"Language must be one of {valid_languages}")
        return v

class ExecutionConfig(pydantic.BaseModel):
    timeout: float = 10.0
    max_memory_mb: int = 512
    retry_attempts: int = 3
    cache_results: bool = True

class CodeExecutor:
    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.loop = asyncio.get_event_loop()
        try:
            start_http_server(8001)
        except Exception as e:
            logger.error(f"Prometheus server failed to start: {e}")
        self._setup_resource_limits()
        self.env = {}
        self.history = []
        self.platform = self._detect_platform()
        self.eval_vars = {
            "app": app,
            "humantime": readable_Time,
            "msg": None,
            "m": None,
            "var": var,
            "teskode": teskode,
            "re": re,
            "os": os,
            "user": None,
            "sticker": None,
            "ParseMode": ParseMode,
            "sendMsg": app.send_message,
            "copyMsg": app.copy_message,
            "forwardMsg": app.forward_messages,
            "sendPhoto": app.send_photo,
            "sendVideo": app.send_video,
            "deleteMsg": app.delete_messages,
            "pinMsg": app.pin_chat_message,
            "MARKDOWN": ParseMode.MARKDOWN,
            "HTML": ParseMode.HTML,
            "IKB": InlineKeyboardButton,
            "IKM": InlineKeyboardMarkup,
            "asyncio": asyncio,
            "cloudscraper": cloudscraper,
            "json": json,
            "aiohttp": aiohttp,
            "send": None,
            "stdout": None,
            "traceback": traceback,
            "webscrap": WebScrap,
            "fetch": Fetch,
            "requests": requests,
            "soup": BeautifulSoup,
        }

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
        try:
            memory_bytes = self.config.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except Exception as e:
            logger.error(f"Failed to set resource limits: {e}")

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

    def _write_temp_file(self, code: str, lang: str) -> str:
        suffix = {
            Language.PYTHON: ".py",
            Language.JAVASCRIPT: ".js",
            Language.SHELL: ".sh",
            Language.BASH: ".bash"
        }[lang]
        file_name = self._generate_secure_filename(code)
        file_path = Path(tempfile.gettempdir()) / f"{file_name}{suffix}"
        file_path.write_text(code)
        if lang in (Language.SHELL, Language.BASH) and self.platform != "windows":
            try:
                file_path.chmod(0o755)
            except Exception as e:
                logger.error(f"Failed to set file permissions for {file_path}: {e}")
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
            return Language.PYTHON
        if any(kw in code for kw in js_keywords):
            return Language.JAVASCRIPT
        if any(kw in code for kw in bash_keywords):
            return Language.BASH
        return Language.PYTHON

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _execute_single(self, code: str, lang: str, msg: Message = None) -> ExecutionResult:
        start_time = time()
        code = self._sanitize_code(code)
        cache_key = f"{lang}:{hash(code)}"
        self.history.append((lang, code))

        if self.config.cache_results and cache_key in cache:
            logger.info(f"Cache hit for {cache_key}")
            return ExecutionResult(**cache[cache_key])

        with pyinstrument.Profiler():
            try:
                if lang == Language.PYTHON:
                    result = await self._run_python(code, msg)
                elif lang == Language.JAVASCRIPT:
                    result = await self._execute_local(code, lang)
                else:
                    result = await self._run_bash(code) if self.platform != "windows" else await self._execute_local(code, lang)
                
                EXECUTION_COUNT.labels(language=lang).inc()
                EXECUTION_TIME.labels(language=lang).observe(time() - start_time)
                
                if self.config.cache_results and redis_client:
                    try:
                        redis_client.setex(cache_key, 3600, msgpack.packb(result.dict()))
                    except Exception as e:
                        logger.error(f"Redis cache set failed: {e}")
                    cache[cache_key] = result.dict()
                
                logger.info(f"Executed {lang} code", result=result.dict())
                return result
            
            except Exception as e:
                logger.error(f"Execution failed: {str(e)}", exc_info=True)
                return ExecutionResult(
                    stdout="", stderr=format_exception(e), returncode=1, language=lang,
                    execution_time=time() - start_time, success=False
                )

    async def _run_python(self, code: str, msg: Message) -> ExecutionResult:
        start_time = time()
        out_code = io.StringIO()
        async def send(*args, **kwargs) -> Message:
            return await msg.reply(*args, **kwargs)
        self.eval_vars.update({
            "msg": msg,
            "m": msg,
            "user": msg.from_user,
            "sticker": msg.reply_to_message.sticker.file_id if msg.reply_to_message and hasattr(msg.reply_to_message, 'sticker') else None,
            "send": send,
            "stdout": out_code,
            "reply": msg.reply_to_message
        })
        try:
            result = await myEval(code, globals(), **self.eval_vars)
            output = out_code.getvalue() or str(result) if result is not None else "[Python] Executed"
            return ExecutionResult(
                stdout=output, stderr="", returncode=0, language=Language.PYTHON,
                execution_time=time() - start_time, success=True
            )
        except Exception as e:
            return ExecutionResult(
                stdout="", stderr=format_exception(e), returncode=1, language=Language.PYTHON,
                execution_time=time() - start_time, success=False
            )

    async def _run_bash(self, code: str) -> ExecutionResult:
        start_time = time()
        try:
            proc = await asyncio.create_subprocess_shell(
                code, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.config.timeout)
            return ExecutionResult(
                stdout=out.decode().strip(), stderr=err.decode().strip(), returncode=proc.returncode,
                language=Language.BASH, execution_time=time() - start_time, success=proc.returncode == 0
            )
        except Exception as e:
            return ExecutionResult(
                stdout="", stderr=f"[Bash Error] {e}", returncode=1, language=Language.BASH,
                execution_time=time() - start_time, success=False
            )

    async def _execute_local(self, code: str, lang: str) -> ExecutionResult:
        start_time = time()
        file_path = None
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
                language=lang, execution_time=time() - start_time, success=proc.returncode == 0
            )
            return result
        
        except Exception as e:
            return ExecutionResult(
                stdout="", stderr=f"[Error] {e}", returncode=1, language=lang,
                execution_time=time() - start_time, success=False
            )
        finally:
            if file_path:
                self._cleanup_temp_file(file_path)

    async def execute_batch(self, snippets: List[CodeSnippet], msg: Message = None) -> List[ExecutionResult]:
        tasks = [self._execute_single(s.code, s.language, msg) for s in snippets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        table = Table(title="Execution Results")
        table.add_column("Language", style="cyan")
        table.add_column("Success", style="green")
        table.add_column("Time", style="magenta")
        table.add_column("Output", style="white", overflow="fold")
        for r in results:
            table.add_row(
                r.language, str(r.success), humanize.naturaldelta(r.execution_time), r.stdout or r.stderr
            )
        console.print(table)
        return results

    async def aexec(self, code: str, msg: Message):
        exec(
            "async def __aexec(app, msg): "
            + "\n p = print"
            + "\n replied = msg.reply_to_message"
            + "".join(f"\n {l_}" for l_ in code.split("\n"))
        )
        return await locals()["__aexec"](app, msg)

    def get_history(self):
        return self.history

executor = CodeExecutor(ExecutionConfig(cache_results=False))

@app.on_message((filters.command("ex", Config.PREFIXS) | filters.regex(r"app.run\(\)$")))
async def execute(app, msg: Message):
    if (msg.command and len(msg.command) == 1) or msg.text == "app.run()":
        return await eos_Send(msg, text="**No evaluate message found!**")
    message = await msg.reply("**Processing code...**")
    code = msg.text.split(maxsplit=1)[1] if msg.command else msg.text.split("\napp.run()")[0]
    parts = code.split(None, 1)
    lang = None
    if len(parts) == 2 and parts[0].lower() in ["python", "py", "js", "javascript", "bash"]:
        lang = parts[0].lower()
        if lang == "py":
            lang = Language.PYTHON
        elif lang == "js":
            lang = Language.JAVASCRIPT
        else:
            lang = Language.BASH
        code = parts[1]
    else:
        lang = executor._auto_detect_language(code)
    
    try:
        snippet = CodeSnippet(code=code, language=lang)
    except pydantic.ValidationError as e:
        logger.error(f"CodeSnippet validation failed: {e}")
        await message.edit(f"**Validation Error:** {e}")
        return
    
    results = await executor.execute_batch([snippet], msg)
    result = results[0]
    output = result.stdout or result.stderr
    el_str = readable_Time(result.execution_time)
    success = f"**Input:**\n<pre>{code}</pre>\n**Output:**\n<pre>{output}</pre>\n**Executed Time:** {el_str}"
    try:
        await eos_Send(message, text=success)
        await message.delete()
    except MessageTooLong:
        with io.BytesIO(str.encode(success)) as Zeep:
            Zeep.name = "ExecutionResult.txt"
            await msg.reply_document(
                document=Zeep,
                caption=f"**Eval:**\n<pre language='python'>{code}</pre>\n\n**Result:**\nAttached document in file!",
                disable_notification=True,
                reply_to_message_id=msg.id
            )
        await message.delete()

@app.on_message(filters.command("p2", Config.PREFIXS))
async def runPyro_Funcs(app, msg: Message):
    code = msg.text.split(None, 1)
    if len(code) == 1:
        return await msg.reply("Code not found!")
    message = await msg.reply("Running...")
    soac = datetime.now()
    osder = sys.stderr
    osdor = sys.stdout
    redr_opu = sys.stdout = io.StringIO()
    redr_err = sys.stderr = io.StringIO()
    stdout, stderr, exc = None, None, None
    try:
        vacue = await executor.aexec(code[1], msg)
    except Exception as e:
        exc = traceback.format_exc()
        logger.error(f"Error in aexec: {exc}")
    stdout = redr_opu.getvalue()
    stderr = redr_err.getvalue()
    sys.stdout = osdor
    sys.stderr = osder
    evason = exc or stderr or stdout or vacue or "No output"
    eoac = datetime.now()
    runcs = (eoac - soac).microseconds / 1000
    oucode = f"📎 Code:\n{code[1]}\n📒 Output:\n{evason}\n✨ Time Taken: {runcs}ms"
    if len(oucode) > 4000:
        await message.edit("⚠️ Output too long...")
    else:
        await message.edit(oucode)

def main():
    try:
        app.start()
        idle()
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        print(f"Error starting bot: {e}")
    finally:
        app.stop()

main()  
