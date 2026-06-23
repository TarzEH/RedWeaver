"""Markdown-aware chunking for the pgvector KB RAG, built on LangChain splitters.

Strategy (fence-safe, then packed to a size budget):

1. ``ExperimentalMarkdownSyntaxTextSplitter`` splits on headers AND treats every
   fenced code block as an atomic unit, so a command/payload is never cut in the
   middle -- critical for the OffSec playbook.
2. A packing pass greedily merges those (often small) structural pieces up toward
   ``size`` chars so we don't store hundreds of tiny embeddings, while still never
   merging across the budget. Oversized prose is sub-split with a recursive
   splitter; an oversized single code block is kept whole and only hard-split as a
   last resort (truly enormous dumps).

The section header breadcrumb ("H1 > H2 > H3") is prepended to each emitted chunk
so retrieval keeps section context even after sub-splitting.
"""
from langchain_text_splitters import (
    ExperimentalMarkdownSyntaxTextSplitter,
    RecursiveCharacterTextSplitter,
)

# Headers we split on, ordered shallow -> deep; second item is the metadata key.
_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


def _breadcrumb(metadata: dict) -> str:
    """Build a "H1 > H2 > H3" breadcrumb from header metadata, if any."""
    parts = [metadata.get(key) for _, key in _HEADERS_TO_SPLIT_ON]
    return " > ".join(p for p in parts if p)


def _with_prefix(prefix: str, content: str) -> str:
    """Prepend the section breadcrumb unless the content already opens with a
    markdown header (which already carries that context)."""
    content = content.strip()
    if prefix and not content.lstrip().startswith("#"):
        return f"{prefix}\n\n{content}"
    return content


def chunk_markdown(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    """Split markdown into ~``size``-char, fence-safe chunks using LangChain.

    Drop-in replacement for the previous hand-written chunker: same signature,
    returns a list of non-empty chunk strings.
    """
    structure_splitter = ExperimentalMarkdownSyntaxTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    prose_splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
    )

    chunks: list[str] = []
    buf = ""
    buf_prefix = ""

    def flush():
        nonlocal buf, buf_prefix
        if buf.strip():
            chunks.append(_with_prefix(buf_prefix, buf))
        buf, buf_prefix = "", ""

    for doc in structure_splitter.split_text(text):
        content = doc.page_content.strip()
        if not content:
            continue
        prefix = _breadcrumb(doc.metadata)
        is_code = "Code" in doc.metadata

        # A single piece that already blows the budget: flush, then emit it on
        # its own (sub-split prose; keep code whole, hard-split only if enormous).
        if len(content) > size:
            flush()
            if is_code:
                if len(content) > size * 2.5:  # last-resort split of a giant dump
                    for i in range(0, len(content), size):
                        chunks.append(_with_prefix(prefix, content[i:i + size]))
                else:
                    chunks.append(_with_prefix(prefix, content))
            else:
                for piece in prose_splitter.split_text(content):
                    chunks.append(_with_prefix(prefix, piece))
            continue

        # Pack: start a new chunk when adding this piece would exceed the budget.
        if buf and len(buf) + len(content) + 2 > size:
            flush()
        if not buf:
            buf_prefix = prefix
        buf = f"{buf}\n\n{content}" if buf else content

    flush()
    return [c for c in chunks if c.strip()]
