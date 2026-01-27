"""Conversation endpoints - listing, viewing, and session resume."""
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Query, HTTPException

from searchat.api.models import (
    SearchResultResponse,
    ConversationMessage,
    ConversationResponse,
    ResumeRequest,
)
import searchat.api.dependencies as deps

from searchat.api.dependencies import get_platform_manager


router = APIRouter()
logger = logging.getLogger(__name__)


async def read_file_async(file_path: str, encoding: str = 'utf-8') -> str:
    """Read file asynchronously to avoid blocking event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: Path(file_path).read_text(encoding=encoding))


def _extract_vibe_messages(data: dict) -> List[ConversationMessage]:
    messages: List[ConversationMessage] = []
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


async def _load_opencode_messages(session_file_path: str, session_id: str) -> List[ConversationMessage]:
    data_root = _resolve_opencode_data_root(session_file_path)
    from searchat.config import PathResolver

    candidate_roots = [data_root]
    for opencode_dir in PathResolver.resolve_opencode_dirs(deps.get_config()):
        if opencode_dir not in candidate_roots:
            candidate_roots.append(opencode_dir)

    raw_messages: List[tuple[float | None, str, str, str]] = []
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

    messages: List[ConversationMessage] = []
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

    parts: List[str] = []
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


@router.get("/conversations/all")
async def get_all_conversations(
    sort_by: str = Query("length", description="Sort by: length, date_newest, date_oldest, title"),
    project: Optional[str] = Query(None, description="Filter by project"),
    date: Optional[str] = Query(None, description="Date filter: today, week, month, or custom"),
    date_from: Optional[str] = Query(None, description="Custom date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Custom date to (YYYY-MM-DD)"),
    tool: Optional[str] = Query(None, description="Filter by tool: claude, vibe, opencode"),
    limit: Optional[int] = Query(None, ge=1, le=5000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Get all conversations with sorting and filtering."""
    started = time.perf_counter()
    try:
        store = deps.get_duckdb_store()

        # Handle date filtering
        date_from_dt = None
        date_to_dt = None
        if date == "custom" and (date_from or date_to):
            # Custom date range
            if date_from:
                date_from_dt = datetime.fromisoformat(date_from)
            if date_to:
                # Add 1 day to include the entire end date
                date_to_dt = datetime.fromisoformat(date_to) + timedelta(days=1)
        elif date:
            # Preset date ranges
            now = datetime.now()
            if date == "today":
                date_from_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
                date_to_dt = now
            elif date == "week":
                date_from_dt = now - timedelta(days=7)
                date_to_dt = now
            elif date == "month":
                date_from_dt = now - timedelta(days=30)
                date_to_dt = now

        if tool:
            tool_value = tool.lower()
            if tool_value not in ("claude", "vibe", "opencode"):
                raise HTTPException(status_code=400, detail="Invalid tool filter")
            tool = tool_value

        total = store.count_conversations(
            project_id=project,
            date_from=date_from_dt,
            date_to=date_to_dt,
            tool=tool,
        )

        rows = store.list_conversations(
            sort_by=sort_by,
            project_id=project,
            date_from=date_from_dt,
            date_to=date_to_dt,
            tool=tool,
            limit=limit,
            offset=offset,
        )

        response_results = []
        for row in rows:
            file_path = row["file_path"]
            full_text = row.get("full_text") or ""
            file_path_lower = file_path.lower()
            if file_path.endswith('.jsonl'):
                tool_name = "claude"
            elif "/.local/share/opencode/" in file_path_lower:
                tool_name = "opencode"
            else:
                tool_name = "vibe"

            if "/home/" in file_path_lower or "wsl" in file_path_lower:
                source = "WSL"
            else:
                source = "WIN"

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
                    source=source,
                    tool=tool_name,
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
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all messages."""
    try:
        store = deps.get_duckdb_store()
        conv = store.get_conversation_meta(conversation_id)
        if conv is None:
            logger.warning(f"Conversation not found in index: {conversation_id}")
            raise HTTPException(status_code=404, detail="Conversation not found in index")
        file_path = conv["file_path"]

        # Check if file exists
        if not Path(file_path).exists():
            logger.error(f"Conversation file not found: {file_path} (conversation_id: {conversation_id})")
            raise HTTPException(
                status_code=404,
                detail=f"Conversation file not found. The file may have been moved or deleted: {file_path}"
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

        project_label = conv["project_id"]
        file_path_lower = file_path.lower()
        if file_path.endswith('.jsonl'):
            tool_name = "claude"
            tool_label = "Claude Code"
        elif "/.local/share/opencode/" in file_path_lower:
            tool_name = "opencode"
            tool_label = "OpenCode"
        else:
            tool_name = "vibe"
            tool_label = "Vibe"

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
async def resume_session(request: ResumeRequest):
    """Resume a conversation session in its original tool (Claude Code or Vibe)."""
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
