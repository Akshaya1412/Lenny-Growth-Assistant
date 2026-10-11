from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, List, Optional, Set

from app.config import settings


@dataclass
class TranscriptChunk:
    source: str
    text: str
    section: str


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def chunk_document(source_name: str, text: str, max_chars: int = 800) -> List[TranscriptChunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    chunks: List[TranscriptChunk] = []
    current = ""
    section = "intro"
    for paragraph in paragraphs:
        candidate = f"{current}\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(TranscriptChunk(source=source_name, text=normalize_text(current), section=section))
        section = source_name
        current = paragraph
    if current:
        chunks.append(TranscriptChunk(source=source_name, text=normalize_text(current), section=section))
    return chunks or [TranscriptChunk(source=source_name, text=normalize_text(text), section="intro")]


def load_transcripts(base_dir: Optional[Path] = None) -> List[TranscriptChunk]:
    base_path = base_dir or Path(__file__).resolve().parents[2] / "data" / "transcripts"
    documents: List[TranscriptChunk] = []
    if not base_path.exists():
        return documents
    for file_path in sorted(base_path.glob("*.txt")):
        content = file_path.read_text(encoding="utf-8")
        documents.extend(chunk_document(file_path.stem, content))
    return documents


_TRANSCRIPTS: Optional[List[TranscriptChunk]] = None


def get_transcripts() -> List[TranscriptChunk]:
    global _TRANSCRIPTS
    if _TRANSCRIPTS is None:
        _TRANSCRIPTS = load_transcripts()
    return _TRANSCRIPTS


def tokenize(value: str) -> Set[str]:
    return {token.lower() for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9/-]{2,}", value)}


def score_chunk(query: str, chunk: TranscriptChunk) -> float:
    query_tokens = tokenize(query)
    text_tokens = tokenize(chunk.text)
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens)
    if overlap == 0:
        return 0.0
    return overlap + (0.25 * len(text_tokens.intersection(query_tokens)) / max(1, len(query_tokens)))


def retrieve_documents(query: str, top_k: Optional[int] = None) -> List[TranscriptChunk]:
    docs = get_transcripts()
    if not docs:
        return []
    top_k = top_k or settings.max_retrieval_chunks
    scored = sorted(
        docs,
        key=lambda doc: score_chunk(query, doc),
        reverse=True,
    )
    filtered = [doc for doc in scored if score_chunk(query, doc) > 0]
    if not filtered:
        return scored[:top_k]
    return filtered[:top_k]


def build_context_for_prompt(query: str, docs: Iterable[TranscriptChunk]) -> str:
    text_blocks: List[str] = []
    for idx, doc in enumerate(docs, start=1):
        text_blocks.append(f"[Source {idx}: {doc.source}]\n{doc.text}\n")
    return "\n\n".join(text_blocks) if text_blocks else "No transcript context was available for this query."
