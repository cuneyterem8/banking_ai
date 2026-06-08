from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.use_cases.support_chatbot.raw_data import load_document_manifest
from app.use_cases.support_chatbot.schemas import RetrievedSource, SupportKnowledgeChunk
from app.use_cases.support_chatbot.data_generation import support_data_root

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _checksum_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_pdf_text(path: Path) -> str:
    try:
        import pdfplumber
    except ModuleNotFoundError:
        return ""
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        return ""


def _read_source_text(path: Path, source_type: str) -> str:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return _read_pdf_text(path)
    if extension == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        blocks = []
        for item in payload.get("items", []):
            question = item.get("question", "")
            answer = item.get("answer", "")
            tags = ", ".join(item.get("tags", []))
            blocks.append(f"FAQ: {question}\nAnswer: {answer}\nTags: {tags}")
        return "\n\n".join(blocks)
    return path.read_text(encoding="utf-8")


def _split_sections(text: str, default_title: str) -> list[tuple[str, str, int, int]]:
    lines = text.splitlines()
    sections: list[tuple[str, list[str], int]] = []
    current_title = default_title
    current_lines: list[str] = []
    current_start = 0
    cursor = 0
    for line in lines:
        stripped = line.strip()
        is_heading = (
            stripped.startswith("SECTION: ")
            or stripped.startswith("## ")
            or stripped.startswith("FAQ: ")
            or (stripped.startswith("# ") and not stripped.startswith("## "))
        )
        if is_heading:
            if current_lines:
                sections.append((current_title, current_lines, current_start))
            current_title = (
                stripped.removeprefix("SECTION: ")
                .removeprefix("## ")
                .removeprefix("# ")
                .removeprefix("FAQ: ")
                .strip()
            )
            current_lines = [line]
            current_start = cursor
        else:
            if not current_lines:
                current_start = cursor
            current_lines.append(line)
        cursor += len(line) + 1
    if current_lines:
        sections.append((current_title, current_lines, current_start))

    output: list[tuple[str, str, int, int]] = []
    for title, section_lines, start in sections:
        body = "\n".join(section_lines).strip()
        is_content_section = body.startswith("SECTION:") or body.startswith("## ") or body.startswith("FAQ:")
        if not body or not is_content_section:
            continue
        output.append((title, body, start, start + len(body)))
    return output


def _chunk_section(
    *,
    source_id: str,
    source_file: str,
    source_type: str,
    topic: str,
    title: str,
    body: str,
    char_start: int,
    base_index: int,
) -> list[SupportKnowledgeChunk]:
    target_size = 900
    overlap = 120
    if len(body) <= target_size:
        text = body.strip()
        return [
            SupportKnowledgeChunk(
                chunk_id=f"{source_id}-CH-{base_index:03d}",
                source_id=source_id,
                source_file=source_file,
                source_type=source_type,
                topic=topic,
                title=title,
                text=text,
                char_start=char_start,
                char_end=char_start + len(text),
                checksum=_checksum_text(text),
            )
        ]
    chunks: list[SupportKnowledgeChunk] = []
    start = 0
    chunk_index = base_index
    while start < len(body):
        end = min(len(body), start + target_size)
        text = body[start:end].strip()
        chunks.append(
            SupportKnowledgeChunk(
                chunk_id=f"{source_id}-CH-{chunk_index:03d}",
                source_id=source_id,
                source_file=source_file,
                source_type=source_type,
                topic=topic,
                title=title,
                text=text,
                char_start=char_start + start,
                char_end=char_start + start + len(text),
                checksum=_checksum_text(text),
            )
        )
        chunk_index += 1
        if end >= len(body):
            break
        start = max(0, end - overlap)
    return chunks


def build_knowledge_chunks() -> list[SupportKnowledgeChunk]:
    chunks: list[SupportKnowledgeChunk] = []
    for source in load_document_manifest():
        path = support_data_root() / source.relative_path
        text = _read_source_text(path, source.source_type)
        sections = _split_sections(text, source.title)
        for index, (title, body, char_start, _char_end) in enumerate(sections, start=1):
            chunks.extend(
                _chunk_section(
                    source_id=source.source_id,
                    source_file=source.source_file,
                    source_type=source.source_type,
                    topic=source.topic,
                    title=title,
                    body=body,
                    char_start=char_start,
                    base_index=index,
                )
            )
    return chunks


def retrieve_chunks(question: str, *, top_k: int = 5, chunks: list[SupportKnowledgeChunk] | None = None) -> tuple[list[RetrievedSource], list[SupportKnowledgeChunk], float, bool]:
    chunk_list = chunks if chunks is not None else build_knowledge_chunks()
    if not chunk_list:
        return [], [], 0, True
    corpus = [tokenize(chunk.text) for chunk in chunk_list]
    query = tokenize(question)
    if not query:
        return [], chunk_list, 0, True
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(query)
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
    top = [(chunk_list[index], float(score)) for index, score in ranked[:top_k] if score > 0]
    if not top:
        return [], chunk_list, 0, True
    top_score = top[0][1]
    second_score = top[1][1] if len(top) > 1 else 0
    retrieval_confidence = round(min(1.0, top_score / (top_score + second_score + 1e-9)), 4)
    no_answer = top_score < 1.0
    retrieved = [
        RetrievedSource(
            source_id=chunk.source_id,
            source_file=chunk.source_file,
            chunk_id=chunk.chunk_id,
            title=chunk.title,
            quote=chunk.text[:280],
            score=round(score, 4),
        )
        for chunk, score in top
    ]
    return retrieved, chunk_list, retrieval_confidence, no_answer


def source_recall_for_answer(answer_sources: list[RetrievedSource], expected_source_ids: list[str]) -> float:
    if not expected_source_ids:
        return 1.0
    actual = {source.source_id for source in answer_sources}
    return len(actual.intersection(expected_source_ids)) / len(set(expected_source_ids))


def citation_contains_required_text(answer_sources: list[RetrievedSource], must_cite: list[str]) -> float:
    if not must_cite:
        return 1.0
    cited = " ".join(source.quote.lower() for source in answer_sources)
    matched = sum(1 for snippet in must_cite if snippet.lower() in cited)
    return matched / len(must_cite)
