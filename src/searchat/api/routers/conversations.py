"""Conversation endpoints - listing, viewing, and session resume."""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re
import time
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from searchat.api.models import (
    SearchResultResponse,
    ConversationMessage,
    ConversationResponse,
    ResumeRequest,
)
from searchat.api.utils import detect_tool_from_path, detect_source_from_path, parse_date_filter
import searchat.api.dependencies as deps

from searchat.services.export_service import export_conversation as render_export

from searchat.api.dependencies import get_platform_manager


router = APIRouter()
logger = logging.getLogger(__name__)


def _resolve_dataset(snapshot: str | None) -> tuple[Path, str | None]:
    if snapshot is None or snapshot == "":
        raise RuntimeError("_resolve_dataset called without snapshot")

    config = deps.get_config()
    if not config.snapshots.enabled:
        raise HTTPException(status_code=404, detail="Snapshot mode is disabled")

    try:
        return deps.resolve_dataset_search_dir(snapshot)
    except ValueError as exc:
        msg = str(exc)
        if msg == "Snapshot not found":
            raise HTTPException(status_code=404, detail="Snapshot not found") from exc
        raise HTTPException(status_code=400, detail=msg) from exc


def _messages_from_parquet(value) -> list[ConversationMessage]:
    if not value:
        return []

    messages: list[ConversationMessage] = []
    for entry in value:
        role = None
        content = None
        ts = None

        if isinstance(entry, dict):
            role = entry.get("role")
            content = entry.get("content")
            ts = entry.get("timestamp")
        elif isinstance(entry, (list, tuple)):
            # Expected schema order: sequence, role, content, timestamp, ...
            if len(entry) >= 4:
                role = entry[1]
                content = entry[2]
                ts = entry[3]

        if isinstance(ts, datetime):
            ts_value = ts.isoformat()
        elif ts is None:
            ts_value = ""
        else:
            ts_value = str(ts)

        messages.append(
            ConversationMessage(
                role=str(role) if role is not None else "",
                content=str(content) if content is not None else "",
                timestamp=ts_value,
            )
        )

    return messages


async def read_file_async(file_path: str, encoding: str = 'utf-8') -> str:
    """Read file asynchronously to avoid blocking event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: Path(file_path).read_text(encoding=encoding))


def _extract_vibe_messages(data: dict) -> list[ConversationMessage]:
    messages: list[ConversationMessage] = []
    for entry in data.get('messages', []):
        role = entry.get('role')
        if role not in ('user', 'assistant'):
            continue
        content = entry.get('content') or entry.get('text') or ''
        if not isinstance(content, str) or not content.strip():
            continue
        timestamp = entry.get('timestamp', '')
        messages.append(ConversationMessage(
            role=role,
            content=content,
            timestamp=timestamp,
        ))
    return messages


async def _load_opencode_messages(session_file_path: str, session_id: str) -> list[ConversationMessage]:
    data_root = _resolve_opencode_data_root(session_file_path)
    from searchat.config import PathResolver

    candidate_roots = [data_root]
    for opencode_dir in PathResolver.resolve_opencode_dirs(deps.get_config()):
        if opencode_dir not in candidate_roots:
            candidate_roots.append(opencode_dir)

    raw_messages: list[tuple[float | None, str, str, str]] = []
    for root in candidate_roots:
        messages_dir = root / "storage" / "message" / session_id
        if not messages_dir.exists():
            continue

        for message_file in messages_dir.glob("*.json"):
            try:
                content = await read_file_async(str(message_file))
                message = json.loads(content)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            role = message.get("role") or message.get("type")
            if role not in ("user", "assistant"):
                continue

            text = _extract_opencode_message_text(root, message)
            if not text:
                continue

            created = message.get("time", {}).get("created")
            created_ts = None
            if isinstance(created, (int, float)):
                created_ts = created / 1000
            raw_messages.append((created_ts, message_file.name, text, role))

        if raw_messages:
            break

    if not raw_messages:
        try:
            session_content = await read_file_async(session_file_path)
            session_data = json.loads(session_content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            session_data = None

        if isinstance(session_data, dict):
            session_messages = session_data.get("messages")
            if isinstance(session_messages, list):
                for index, entry in enumerate(session_messages):
                    if not isinstance(entry, dict):
                        continue
                    role = entry.get("role") or entry.get("type")
                    if role not in ("user", "assistant"):
                        continue
                    text = _extract_opencode_message_text(data_root, entry)
                    if not text:
                        continue
                    created = entry.get("time", {}).get("created")
                    created_ts = None
                    if isinstance(created, (int, float)):
                        created_ts = created / 1000
                    raw_messages.append((created_ts, f"{index:06d}", text, role))

    raw_messages.sort(key=lambda item: (item[0] or 0.0, item[1]))

    messages: list[ConversationMessage] = []
    for created_ts, _name, text, role in raw_messages:
        timestamp = ""
        if created_ts is not None:
            timestamp = datetime.fromtimestamp(created_ts).isoformat()
        messages.append(ConversationMessage(
            role=role,
            content=text,
            timestamp=timestamp,
        ))
    return messages


def _extract_opencode_message_text(data_root: Path, message: dict) -> str:
    def _normalize_text(value: object) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            text = value.get("text") or value.get("content") or value.get("value")
            if isinstance(text, str) and text.strip():
                return text.strip()
        if isinstance(value, list):
            parts = []
            for block in value:
                if not isinstance(block, dict):
                    continue
                text = block.get("text") or block.get("content") or block.get("value")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n\n".join(parts)
        return ""

    content_text = _normalize_text(message.get("content"))
    if content_text:
        return content_text

    text_text = _normalize_text(message.get("text"))
    if text_text:
        return text_text

    message_text = _normalize_text(message.get("message"))
    if message_text:
        return message_text

    message_id = message.get("id")
    if isinstance(message_id, str):
        parts_text = _load_opencode_parts_text(data_root, message_id)
        if parts_text:
            return parts_text

    summary = message.get("summary")
    if isinstance(summary, dict):
        body = summary.get("body")
        if isinstance(body, str) and body.strip():
            return body.strip()

        title = summary.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()

    return ""


def _load_opencode_parts_text(data_root: Path, message_id: str) -> str:
    parts_dir = data_root / "storage" / "part" / message_id
    if not parts_dir.exists():
        return ""

    parts: list[str] = []
    for part_file in sorted(parts_dir.glob("*.json")):
        try:
            content = part_file.read_text(encoding="utf-8")
            part = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        text = part.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
            continue

        state = part.get("state")
        if isinstance(state, dict):
            output = state.get("output")
            if isinstance(output, str) and output.strip():
                parts.append(output.strip())

    return "\n\n".join(parts)


def _resolve_opencode_data_root(session_file_path: str) -> Path:
    session_path = Path(session_file_path)
    if "storage" in session_path.parts:
        storage_index = session_path.parts.index("storage")
        return Path(*session_path.parts[:storage_index])
    if len(session_path.parents) >= 4:
        return session_path.parents[3]
    return session_path.parent


def _load_opencode_project_path(session_file_path: str) -> str | None:
    session_path = Path(session_file_path)
    try:
        content = session_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    project_id = data.get("projectID")
    if not isinstance(project_id, str):
        return None

    data_root = _resolve_opencode_data_root(session_file_path)
    project_file = data_root / "storage" / "project" / f"{project_id}.json"
    if not project_file.exists():
        return None

    try:
        project_content = project_file.read_text(encoding="utf-8")
        project_data = json.loads(project_content)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    worktree = project_data.get("worktree")
    if isinstance(worktree, str) and worktree.strip():
        return worktree
    return None


def _load_vibe_project_path(session_file_path: str) -> str | None:
    session_path = Path(session_file_path)
    try:
        content = session_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    working_dir = data.get('metadata', {}).get('environment', {}).get('working_directory')
    if isinstance(working_dir, str) and working_dir.strip():
        return working_dir
    return None


def _slice_messages(
    messages: list[ConversationMessage],
    start: int | None,
    end: int | None,
) -> list[ConversationMessage]:
    if start is None or end is None:
        return messages

    start_index = max(start, 0)
    end_index = min(end, len(messages) - 1)
    if start_index > end_index:
        return []
    return messages[start_index:end_index + 1]


def _messages_to_lines(messages: list[ConversationMessage]) -> list[str]:
    lines: list[str] = []
    for idx, message in enumerate(messages, start=1):
        role_label = (message.role or "unknown").upper()
        lines.append(f"{role_label} #{idx}")
        content = message.content or ""
        if content:
            lines.extend(content.splitlines())
        else:
            lines.append("")
        lines.append("")
    return lines


@router.get("/conversations/all")
async def get_all_conversations(
    sort_by: str = Query("length", description="Sort by: length, date_newest, date_oldest, title"),
    project: str | None = Query(None, description="Filter by project"),
    date: str | None = Query(None, description="Date filter: today, week, month, or custom"),
    date_from: str | None = Query(None, description="Custom date from (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Custom date to (YYYY-MM-DD)"),
    tool: str | None = Query(None, description="Filter by tool: claude, vibe, opencode, codex, gemini, continue, cursor, aider"),
    limit: int | None = Query(None, ge=1, le=5000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get all conversations with sorting and filtering."""
    started = time.perf_counter()
    try:
        if snapshot is None:
            store = deps.get_duckdb_store()
        else:
            search_dir, _snapshot_name = _resolve_dataset(snapshot)
            store = deps.get_duckdb_store_for(search_dir)

        # Handle date filtering
        date_from_dt, date_to_dt = parse_date_filter(date, date_from, date_to)

        if tool:
            tool_value = tool.lower()
            if tool_value not in ("claude", "vibe", "opencode", "codex", "gemini", "continue", "cursor", "aider"):
                raise HTTPException(status_code=400, detail="Invalid tool filter")
            tool = tool_value

        count_kwargs: dict = {
            "project_id": project,
            "date_from": date_from_dt,
            "date_to": date_to_dt,
        }
        if tool is not None:
            count_kwargs["tool"] = tool
        total = store.count_conversations(**count_kwargs)

        list_kwargs: dict = {
            "sort_by": sort_by,
            "project_id": project,
            "date_from": date_from_dt,
            "date_to": date_to_dt,
            "limit": limit,
            "offset": offset,
        }
        if tool is not None:
            list_kwargs["tool"] = tool
        rows = store.list_conversations(**list_kwargs)

        response_results = []
        for row in rows:
            file_path = row["file_path"]
            full_text = row.get("full_text") or ""

            response_results.append(
                SearchResultResponse(
                    conversation_id=row["conversation_id"],
                    project_id=row["project_id"],
                    title=row["title"],
                    created_at=row["created_at"].isoformat(),
                    updated_at=row["updated_at"].isoformat(),
                    message_count=row["message_count"],
                    file_path=file_path,
                    snippet=full_text[:200] + ("..." if len(full_text) > 200 else ""),
                    score=0.0,
                    message_start_index=None,
                    message_end_index=None,
                    source=detect_source_from_path(file_path),
                    tool=detect_tool_from_path(file_path),
                )
            )

        return {
            "results": response_results,
            "total": total,
            "search_time_ms": int((time.perf_counter() - started) * 1000.0),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get a specific conversation with all messages."""
    try:
        if snapshot is None:
            store = deps.get_duckdb_store()
            snapshot_name = None
        else:
            search_dir, snapshot_name = _resolve_dataset(snapshot)
            store = deps.get_duckdb_store_for(search_dir)
        conv = store.get_conversation_meta(conversation_id)
        if conv is None:
            logger.warning(f"Conversation not found in index: {conversation_id}")
            raise HTTPException(status_code=404, detail="Conversation not found in index")
        file_path = conv["file_path"]

        if snapshot_name is not None:
            record = store.get_conversation_record(conversation_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Conversation not found in snapshot")
            messages = _messages_from_parquet(record.get("messages"))
            tool_name = detect_tool_from_path(file_path)
            return ConversationResponse(
                conversation_id=conversation_id,
                title=conv["title"],
                project_id=conv["project_id"],
                project_path=None,
                file_path=file_path,
                message_count=int(record.get("message_count") or len(messages)),
                tool=tool_name,
                messages=messages,
            )

        # Check if file exists. If missing, fall back to parquet (safer for moved/deleted sources).
        if not Path(file_path).exists():
            record = store.get_conversation_record(conversation_id)
            if record is None:
                logger.error(
                    "Conversation file not found and no parquet record available: %s (conversation_id: %s)",
                    file_path,
                    conversation_id,
                )
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Conversation file not found and no indexed record is available. "
                        f"The file may have been moved or deleted: {file_path}"
                    ),
                )

            try:
                messages = _messages_from_parquet(record.get("messages"))
            except TypeError:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation file not found. The file may have been moved or deleted: {file_path}",
                )
            tool_name = detect_tool_from_path(file_path)
            return ConversationResponse(
                conversation_id=conversation_id,
                title=conv["title"],
                project_id=conv["project_id"],
                project_path=None,
                file_path=conv["file_path"],
                message_count=int(record.get("message_count") or len(messages)),
                tool=tool_name,
                messages=messages,
            )

        messages = []
        if file_path.endswith('.jsonl'):
            # Claude Code JSONL
            try:
                content = await read_file_async(file_path)
                lines = [json.loads(line) for line in content.splitlines() if line.strip()]
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in conversation file {file_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to parse conversation file (invalid JSON)"
                )
            except UnicodeDecodeError as e:
                logger.error(f"Encoding error reading {file_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to read conversation file (encoding error)"
                )

            for entry in lines:
                if entry.get('type') in ('user', 'assistant'):
                    raw_content = entry.get('message', {}).get('content', '')
                    if isinstance(raw_content, str):
                        content = raw_content
                    elif isinstance(raw_content, list):
                        content = '\n\n'.join(
                            block.get('text', '')
                            for block in raw_content
                            if block.get('type') == 'text'
                        )
                    else:
                        content = ''

                    if content:
                        messages.append(ConversationMessage(
                            role=entry.get('type'),
                            content=content,
                            timestamp=entry.get('timestamp', '')
                        ))
        elif file_path.endswith('.json'):
            # Vibe or OpenCode
            try:
                content = await read_file_async(file_path)
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in conversation file {file_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to parse conversation file (invalid JSON)"
                )
            except UnicodeDecodeError as e:
                logger.error(f"Encoding error reading {file_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to read conversation file (encoding error)"
                )

            file_path_lower = file_path.lower()
            is_opencode = "projectID" in data or "/.local/share/opencode/" in file_path_lower
            if is_opencode:
                session_id = data.get("id") or data.get("sessionID") or conversation_id
                messages = await _load_opencode_messages(file_path, session_id)
            else:
                messages = _extract_vibe_messages(data)

        logger.info(f"Successfully loaded conversation {conversation_id} with {len(messages)} messages")

        tool_name = detect_tool_from_path(file_path)

        project_path = None
        if tool_name == "opencode":
            project_path = _load_opencode_project_path(file_path)
        elif tool_name == "vibe":
            project_path = _load_vibe_project_path(file_path)

        return ConversationResponse(
            conversation_id=conversation_id,
            title=conv["title"],
            project_id=conv["project_id"],
            project_path=project_path,
            file_path=conv["file_path"],
            message_count=len(messages),
            tool=tool_name,
            messages=messages
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/resume")
async def resume_session(
    request: ResumeRequest,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Resume a conversation session in its original tool (Claude Code or Vibe)."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Resume is disabled in snapshot mode")
    try:
        store = deps.get_duckdb_store()
        platform_manager = get_platform_manager()

        conv = store.get_conversation_meta(request.conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        file_path = conv["file_path"]
        session_id = conv["conversation_id"]

        # Extract working directory from conversation file
        cwd = None

        if file_path.endswith('.jsonl'):
            # Claude Code - read lines until we find one with cwd (async)
            tool = 'claude'
            content = await read_file_async(file_path)
            for line in content.splitlines():
                if line.strip():
                    entry = json.loads(line)
                    if 'cwd' in entry:
                        cwd = entry['cwd']
                        break
            command = f'claude --resume {session_id}'
        elif file_path.endswith('.json'):
            # Vibe or OpenCode - inspect JSON structure (async)
            content = await read_file_async(file_path)
            data = json.loads(content)
            if 'projectID' in data and 'sessionID' in data:
                tool = 'opencode'
                cwd = data.get('directory')
                command = f'opencode --resume {session_id}'
            else:
                tool = 'vibe'
                cwd = data.get('metadata', {}).get('environment', {}).get('working_directory', None)
                command = f'vibe --resume {session_id}'
        else:
            raise HTTPException(status_code=400, detail=f"Unknown conversation format: {file_path}")

        # Normalize path for current platform
        if cwd:
            cwd = platform_manager.normalize_path(cwd)

        logger.info(f"Resuming {tool} session {session_id}")
        logger.info(f"  Platform: {platform_manager.platform}")
        logger.info(f"  Original CWD: {cwd}")
        logger.info(f"  Command: {command}")

        # Open terminal with command using platform-specific implementation
        # Path translation happens automatically in open_terminal_with_command
        platform_manager.open_terminal_with_command(command, cwd)

        return {
            "success": True,
            "tool": tool,
            "cwd": cwd,
            "command": command,
            "platform": platform_manager.platform
        }

    except HTTPException:
        raise
    except FileNotFoundError as e:
        # Command not found (claude or vibe not installed)
        logger.error(f"Command not found: {e}")
        tool_name = locals().get('tool', 'claude/vibe')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute command. Make sure {tool_name} is installed and in PATH."
        )
    except Exception as e:
        logger.error(f"Failed to resume session {request.conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{conversation_id}/code")
async def get_conversation_code(
    conversation_id: str,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Extract code blocks from a conversation."""
    try:
        # Get full conversation with messages
        if snapshot is None:
            conv_response = await get_conversation(conversation_id)
        else:
            conv_response = await get_conversation(conversation_id, snapshot=snapshot)

        code_blocks = []
        for msg_idx, message in enumerate(conv_response.messages):
            # Extract code blocks with language detection
            # Pattern: ```language\ncode\n``` or just ```\ncode\n```
            pattern = r'```(\w*)\n(.*?)```'
            matches = re.findall(pattern, message.content, re.DOTALL)

            for block_idx, (language, code) in enumerate(matches):
                fence_language = language.strip() if isinstance(language, str) else ""
                # Clean up code (remove leading/trailing whitespace)
                code = code.strip()
                if not code:
                    continue

                language_source = "fence" if fence_language else "detected"
                # Detect language if not specified
                if not fence_language:
                    language = _detect_language(code)
                else:
                    language = fence_language

                code_blocks.append({
                    'message_index': msg_idx,
                    'block_index': block_idx,
                    'role': message.role,
                    'fence_language': fence_language or None,
                    'language': language or 'plaintext',
                    'language_source': language_source,
                    'code': code,
                    'timestamp': message.timestamp,
                    'lines': len(code.splitlines())
                })

        return {
            'conversation_id': conversation_id,
            'title': conv_response.title,
            'total_blocks': len(code_blocks),
            'code_blocks': code_blocks
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extract code from conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _detect_language(code: str) -> str:
    """Detect programming language from code content."""
    code_lower = code.lower().strip()

    # SQL indicators (check before Python to avoid 'from' keyword collision)
    if any(kw in code_lower for kw in ['select ', 'insert ', 'update ', 'delete ', 'create table']):
        return 'sql'

    # Python indicators
    if any(kw in code_lower for kw in ['def ', 'import ', 'from ', 'class ', 'if __name__']):
        return 'python'

    # JavaScript/TypeScript indicators
    if any(kw in code_lower for kw in ['function ', 'const ', 'let ', 'var ', '=>', 'console.log']):
        if 'interface ' in code_lower or ': ' in code and 'type ' in code_lower:
            return 'typescript'
        return 'javascript'

    # Shell/Bash indicators
    if code.startswith('#!') or any(kw in code_lower for kw in ['#!/bin/', 'echo ', 'export ', '${']):
        return 'bash'

    # JSON indicator
    if code.strip().startswith('{') and ':' in code:
        try:
            json.loads(code)
            return 'json'
        except json.JSONDecodeError:
            pass

    # HTML indicator
    if '<' in code and '>' in code and any(tag in code_lower for tag in ['<div', '<html', '<body', '<p>']):
        return 'html'

    # CSS indicator
    if '{' in code and '}' in code and ':' in code and ';' in code:
        return 'css'

    # Go indicators
    if any(kw in code_lower for kw in ['package ', 'func ', 'import (']):
        return 'go'

    # Rust indicators
    if any(kw in code_lower for kw in ['fn ', 'let mut', 'impl ', 'use ']):
        return 'rust'

    # Java indicators
    if any(kw in code_lower for kw in ['public class', 'private ', 'public static void main']):
        return 'java'

    # Default
    return 'plaintext'


@router.get("/conversation/{conversation_id}/similar")
async def get_similar_conversations(
    conversation_id: str,
    limit: int = Query(5, description="Max similar conversations to return (1-20)", ge=1, le=20),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Get conversations similar to the specified conversation using FAISS embeddings."""
    try:
        if snapshot is None:
            try:
                search_engine = deps.get_search_engine()
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

            store = deps.get_duckdb_store()
        else:
            search_dir, _snapshot_name = _resolve_dataset(snapshot)
            store = deps.get_duckdb_store_for(search_dir)
            search_engine = deps.get_or_create_search_engine_for(search_dir)

        # Verify conversation exists
        conv_meta = store.get_conversation_meta(conversation_id)
        if not conv_meta:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found"
            )

        # Ensure FAISS and embedder are ready
        search_engine.ensure_faiss_loaded()
        search_engine.ensure_embedder_loaded()

        faiss_index = search_engine.faiss_index
        if faiss_index is None:
            raise HTTPException(
                status_code=503,
                detail="FAISS index not available"
            )

        # Get representative text from the conversation to generate embedding
        import numpy as np

        # Get the conversation's title and some content
        metadata_path = search_engine.metadata_path
        conn = store._connect()

        try:
            # Get chunk text for this conversation
            query = """
                SELECT chunk_text
                FROM parquet_scan(?)
                WHERE conversation_id = ?
                ORDER BY vector_id
                LIMIT 1
            """
            result = conn.execute(query, [str(metadata_path), conversation_id]).fetchone()

            if not result:
                raise HTTPException(
                    status_code=404,
                    detail="No embeddings found for this conversation"
                )

            chunk_text = result[0]

            # Generate embedding from the conversation's representative text
            embedder = search_engine.embedder
            if embedder is None:
                raise HTTPException(
                    status_code=503,
                    detail="Embedder not available"
                )

            # Combine title and chunk text for better representation
            representative_text = f"{conv_meta['title']} {chunk_text}"
            query_embedding = np.asarray(
                embedder.encode(representative_text),
                dtype=np.float32
            )

            # Search for similar vectors
            # Request more than needed to filter out the original conversation
            k = limit + 10
            distances, labels = faiss_index.search(  # type: ignore
                query_embedding.reshape(1, -1),
                k
            )

            # Build results
            valid_mask = labels[0] >= 0
            hits = []
            for vid, distance in zip(labels[0][valid_mask], distances[0][valid_mask]):
                hits.append((int(vid), float(distance)))

            if not hits:
                return {
                    'conversation_id': conversation_id,
                    'similar_conversations': []
                }

            # Query metadata and conversations to get details
            values_clause = ", ".join(["(?, ?)"] * len(hits))
            params = []
            for vid, distance in hits:
                params.extend([vid, distance])

            params.append(str(metadata_path))
            params.append(search_engine.conversations_glob)

            sql = f"""
                WITH hits(vector_id, distance) AS (
                    VALUES {values_clause}
                )
                SELECT
                    m.conversation_id,
                    c.project_id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    c.message_count,
                    c.file_path,
                    hits.distance
                FROM hits
                JOIN parquet_scan(?) AS m
                    ON m.vector_id = hits.vector_id
                JOIN parquet_scan(?) AS c
                    ON c.conversation_id = m.conversation_id
                WHERE m.conversation_id != ?
                QUALIFY row_number() OVER (PARTITION BY m.conversation_id ORDER BY hits.distance) = 1
                ORDER BY hits.distance
                LIMIT ?
            """
            params.append(conversation_id)  # Filter out original conversation
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

        finally:
            conn.close()

        # Format results
        similar_conversations = []
        for (
            sim_conv_id,
            project_id,
            title,
            created_at,
            updated_at,
            message_count,
            file_path,
            distance,
        ) in rows:
            # Calculate similarity score (inverse of distance)
            score = 1.0 / (1.0 + float(distance))

            # Handle both string and datetime types for timestamps
            created_at_str = created_at if isinstance(created_at, str) else created_at.isoformat()
            updated_at_str = updated_at if isinstance(updated_at, str) else updated_at.isoformat()

            similar_conversations.append({
                'conversation_id': sim_conv_id,
                'project_id': project_id,
                'title': title,
                'created_at': created_at_str,
                'updated_at': updated_at_str,
                'message_count': message_count,
                'similarity_score': round(score, 3),
                'tool': detect_tool_from_path(file_path)
            })

        return {
            'conversation_id': conversation_id,
            'title': conv_meta['title'],
            'similar_count': len(similar_conversations),
            'similar_conversations': similar_conversations
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find similar conversations for {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/conversation/{conversation_id}/diff")
async def get_conversation_diff(
    conversation_id: str,
    target_id: str | None = Query(None, description="Target conversation to diff against"),
    source_start: int | None = Query(None, description="Source message start index"),
    source_end: int | None = Query(None, description="Source message end index"),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Compute a line diff between two conversations."""
    try:
        if target_id is None:
            similar_payload = await get_similar_conversations(conversation_id, limit=1, snapshot=snapshot)
            similar_list = similar_payload.get("similar_conversations", [])
            if not similar_list:
                raise HTTPException(status_code=404, detail="No similar conversation found")
            target_id = similar_list[0]["conversation_id"]

        if target_id is None:
            raise HTTPException(status_code=404, detail="Target conversation not found")
        if not isinstance(target_id, str):
            raise HTTPException(status_code=400, detail="Invalid target conversation id")

        source_conv = await get_conversation(conversation_id, snapshot=snapshot)
        target_conv = await get_conversation(target_id, snapshot=snapshot)

        source_messages = _slice_messages(source_conv.messages, source_start, source_end)
        target_messages = _slice_messages(target_conv.messages, None, None)

        source_lines = _messages_to_lines(source_messages)
        target_lines = _messages_to_lines(target_messages)

        added: list[str] = []
        removed: list[str] = []
        unchanged: list[str] = []

        for line in difflib.ndiff(source_lines, target_lines):
            if line.startswith("+ "):
                added.append(line[2:])
            elif line.startswith("- "):
                removed.append(line[2:])
            elif line.startswith("  "):
                unchanged.append(line[2:])

        return {
            "source_conversation_id": conversation_id,
            "target_conversation_id": target_id,
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "unchanged": len(unchanged),
            },
            "added": added,
            "removed": removed,
            "unchanged": unchanged,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to build diff for {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/conversation/{conversation_id}/export")
async def export_conversation(
    conversation_id: str,
    format: str = Query("json", description="Export format: json, markdown, text, ipynb, pdf"),
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Export a conversation in various formats."""
    try:
        # Get full conversation
        if snapshot is None:
            conv_response = await get_conversation(conversation_id)
        else:
            conv_response = await get_conversation(conversation_id, snapshot=snapshot)

        format_lower = format.lower()
        if format_lower in ("ipynb", "pdf"):
            config = deps.get_config()
            if format_lower == "ipynb" and not config.export.enable_ipynb:
                raise HTTPException(status_code=404, detail="Notebook export is disabled")
            if format_lower == "pdf" and not config.export.enable_pdf:
                raise HTTPException(status_code=404, detail="PDF export is disabled")

        if format_lower not in ("json", "markdown", "text", "ipynb", "pdf"):
            raise HTTPException(
                status_code=400,
                detail="Invalid format. Use: json, markdown, text, ipynb, or pdf",
            )

        exported = render_export(conv_response, format=format_lower)  # type: ignore[arg-type]

        return Response(
            content=exported.content,
            media_type=exported.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{exported.filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


class BulkExportRequest(BaseModel):
    """Request model for bulk export."""

    conversation_ids: list[str]
    format: str = "json"


@router.post("/conversations/bulk-export")
async def bulk_export_conversations(
    request: BulkExportRequest,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Export multiple conversations as a ZIP archive."""
    try:
        import io
        import zipfile
        from datetime import datetime

        if not request.conversation_ids:
            raise HTTPException(status_code=400, detail="No conversation IDs provided")

        if len(request.conversation_ids) > 100:
            raise HTTPException(
                status_code=400,
                detail="Too many conversations (max 100)"
            )

        format_lower = request.format.lower()
        if format_lower in ("ipynb", "pdf"):
            config = deps.get_config()
            if format_lower == "ipynb" and not config.export.enable_ipynb:
                raise HTTPException(status_code=404, detail="Notebook export is disabled")
            if format_lower == "pdf" and not config.export.enable_pdf:
                raise HTTPException(status_code=404, detail="PDF export is disabled")

        if format_lower not in ("json", "markdown", "text", "ipynb", "pdf"):
            raise HTTPException(
                status_code=400,
                detail="Invalid format. Use: json, markdown, text, ipynb, or pdf"
            )

        # Determine file extension
        ext_map = {
            "json": "json",
            "markdown": "md",
            "text": "txt",
            "ipynb": "ipynb",
            "pdf": "pdf",
        }
        ext = ext_map[format_lower]

        # Create ZIP file in memory
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for conv_id in request.conversation_ids:
                try:
                    if snapshot is None:
                        conv_response = await get_conversation(conv_id)
                    else:
                        conv_response = await get_conversation(conv_id, snapshot=snapshot)
                    exported = render_export(conv_response, format=format_lower)  # type: ignore[arg-type]

                    safe_title = "".join(
                        c for c in conv_response.title[:50]
                        if c.isalnum() or c in (" ", "-", "_")
                    ).strip()
                    if not safe_title:
                        safe_title = conv_id

                    filename = f"{safe_title}_{conv_id[:8]}.{ext}"
                    zip_file.writestr(filename, exported.content)

                except HTTPException:
                    # Skip conversations that can't be loaded
                    logger.warning(f"Skipping conversation {conv_id} in bulk export")
                    continue
                except Exception as e:
                    logger.error(f"Error exporting {conv_id}: {e}")
                    continue

        # Prepare ZIP for download
        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"searchat_export_{timestamp}.zip"

        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bulk export conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
