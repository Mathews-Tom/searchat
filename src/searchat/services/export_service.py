from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, XPreformatted

from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer
from pygments.styles import get_style_by_name

from searchat.api.models.responses import ConversationResponse


ExportFormat = Literal["json", "markdown", "text", "ipynb", "pdf"]


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    media_type: str
    filename: str


_FENCE_RE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)


def export_conversation(conversation: ConversationResponse, *, format: ExportFormat) -> ExportResult:
    if format == "json":
        return _export_json(conversation)
    if format == "markdown":
        return _export_markdown(conversation)
    if format == "text":
        return _export_text(conversation)
    if format == "ipynb":
        return _export_ipynb(conversation)
    if format == "pdf":
        return _export_pdf(conversation)
    raise ValueError("Unsupported export format")


def _export_json(conversation: ConversationResponse) -> ExportResult:
    content = json.dumps(
        {
            "conversation_id": conversation.conversation_id,
            "title": conversation.title,
            "project_id": conversation.project_id,
            "project_path": conversation.project_path,
            "tool": conversation.tool,
            "message_count": conversation.message_count,
            "messages": [
                {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp}
                for msg in conversation.messages
            ],
        },
        indent=2,
    ).encode("utf-8")
    return ExportResult(
        content=content,
        media_type="application/json",
        filename=f"{conversation.conversation_id}.json",
    )


def _export_markdown(conversation: ConversationResponse) -> ExportResult:
    lines = [
        f"# {conversation.title}",
        "",
        f"**Conversation ID:** {conversation.conversation_id}",
        f"**Project:** {conversation.project_id}",
        f"**Tool:** {conversation.tool}",
        f"**Messages:** {conversation.message_count}",
    ]

    if conversation.project_path:
        lines.insert(4, f"**Project Path:** {conversation.project_path}")

    lines.extend(["", "---", ""])
    for idx, msg in enumerate(conversation.messages, 1):
        role_label = msg.role.upper()
        lines.append(f"## Message {idx} - {role_label}")
        if msg.timestamp:
            lines.append(f"*{msg.timestamp}*")
            lines.append("")
        lines.append(msg.content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return ExportResult(
        content="\n".join(lines).encode("utf-8"),
        media_type="text/markdown",
        filename=f"{conversation.conversation_id}.md",
    )


def _export_text(conversation: ConversationResponse) -> ExportResult:
    lines = [
        f"{'=' * 80}",
        f"CONVERSATION: {conversation.title}",
        f"{'=' * 80}",
        "",
        f"ID: {conversation.conversation_id}",
        f"Project: {conversation.project_id}",
        f"Tool: {conversation.tool}",
        f"Messages: {conversation.message_count}",
    ]

    if conversation.project_path:
        lines.insert(7, f"Project Path: {conversation.project_path}")

    lines.extend(["", f"{'-' * 80}", ""])
    for idx, msg in enumerate(conversation.messages, 1):
        role_label = msg.role.upper()
        lines.append(f"[Message {idx} - {role_label}]")
        if msg.timestamp:
            lines.append(f"Time: {msg.timestamp}")
        lines.append("")
        lines.append(msg.content)
        lines.append("")
        lines.append(f"{'-' * 80}")
        lines.append("")

    return ExportResult(
        content="\n".join(lines).encode("utf-8"),
        media_type="text/plain",
        filename=f"{conversation.conversation_id}.txt",
    )


def _export_ipynb(conversation: ConversationResponse) -> ExportResult:
    cells: list[dict[str, Any]] = []
    header = [
        f"# {conversation.title}",
        "",
        f"Conversation ID: {conversation.conversation_id}",
        f"Project: {conversation.project_id}",
        f"Tool: {conversation.tool}",
        f"Messages: {conversation.message_count}",
    ]
    if conversation.project_path:
        header.insert(4, f"Project Path: {conversation.project_path}")
    cells.append(_nb_markdown_cell("\n".join(header)))

    for idx, msg in enumerate(conversation.messages, 1):
        title = f"## Message {idx} - {msg.role.upper()}"
        ts = f"\n\n*{msg.timestamp}*" if msg.timestamp else ""
        cells.append(_nb_markdown_cell(title + ts))

        for segment in _split_message(msg.content):
            if segment["kind"] == "code":
                cells.append(_nb_code_cell(segment["content"]))
            else:
                text = segment["content"].strip()
                if text:
                    cells.append(_nb_markdown_cell(text))

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    return ExportResult(
        content=json.dumps(notebook, indent=2).encode("utf-8"),
        media_type="application/x-ipynb+json",
        filename=f"{conversation.conversation_id}.ipynb",
    )


def _export_pdf(conversation: ConversationResponse) -> ExportResult:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=conversation.title,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    meta_style = styles["BodyText"]
    meta_style.spaceAfter = 8

    story: list[Any] = []
    story.append(Paragraph(conversation.title, title_style))

    meta_lines = [
        f"Conversation ID: {conversation.conversation_id}",
        f"Project: {conversation.project_id}",
        f"Tool: {conversation.tool}",
        f"Messages: {conversation.message_count}",
    ]
    if conversation.project_path:
        meta_lines.insert(2, f"Project Path: {conversation.project_path}")
    story.append(Paragraph("<br/>".join(_escape_xml(x) for x in meta_lines), meta_style))
    story.append(Spacer(1, 0.2 * inch))

    body_style = styles["BodyText"]
    body_style.leading = 14
    body_style.spaceAfter = 10

    heading = ParagraphStyle(
        "MsgHeading",
        parent=styles["Heading2"],
        spaceBefore=10,
        spaceAfter=6,
    )

    code_style = ParagraphStyle(
        "Code",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8.5,
        leading=10.5,
        spaceBefore=6,
        spaceAfter=10,
    )

    for idx, msg in enumerate(conversation.messages, 1):
        story.append(Paragraph(f"Message {idx} - {msg.role.upper()}", heading))
        if msg.timestamp:
            story.append(Paragraph(_escape_xml(msg.timestamp), meta_style))

        for segment in _split_message(msg.content):
            if segment["kind"] == "text":
                text = segment["content"].strip()
                if text:
                    story.append(Paragraph(_escape_xml(text).replace("\n", "<br/>") , body_style))
            else:
                story.append(XPreformatted(_highlight_code_markup(segment), code_style))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return ExportResult(
        content=pdf_bytes,
        media_type="application/pdf",
        filename=f"{conversation.conversation_id}.pdf",
    )


def _nb_markdown_cell(text: str) -> dict[str, Any]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text,
    }


def _nb_code_cell(code: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": code,
    }


def _split_message(content: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    cursor = 0
    for match in _FENCE_RE.finditer(content):
        start, end = match.span()
        if start > cursor:
            segments.append({"kind": "text", "content": content[cursor:start]})

        fence_lang_raw = match.group(1).strip()
        fence_lang = fence_lang_raw or None
        code = match.group(2).strip("\n")
        segments.append({"kind": "code", "content": code, "fence_language": fence_lang})
        cursor = end

    if cursor < len(content):
        segments.append({"kind": "text", "content": content[cursor:]})
    return segments


def _highlight_code_markup(segment: dict[str, Any]) -> str:
    code = segment.get("content", "")
    fence_language = segment.get("fence_language")
    lexer = None
    if isinstance(fence_language, str) and fence_language:
        try:
            lexer = get_lexer_by_name(fence_language)
        except Exception:
            lexer = None

    if lexer is None:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = TextLexer()

    style = get_style_by_name("friendly")
    parts: list[str] = []
    for tok_type, tok_text in lex(code, lexer):
        style_def = style.style_for_token(tok_type)
        color = style_def.get("color")

        escaped = _escape_xml(tok_text)
        escaped = escaped.replace(" ", "&nbsp;")
        escaped = escaped.replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
        escaped = escaped.replace("\n", "<br/>")

        if color:
            parts.append(f"<font color='#{color}'>{escaped}</font>")
        else:
            parts.append(escaped)

    return "".join(parts)


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
