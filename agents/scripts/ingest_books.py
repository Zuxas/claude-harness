"""
ingest_books.py — Parse all PDFs and EPUBs into searchable knowledge chunks

Scans E:\\vscode ai project\\books for PDFs and EPUBs, extracts text,
chunks into ~2000 char segments, saves as a JSON index.

USAGE:
  python ingest_books.py                  # ingest all books
  python ingest_books.py --query "python"  # search the index
  python ingest_books.py --stats          # show index stats
"""

import sys, os, json, re, time, argparse
from pathlib import Path
from datetime import datetime

BOOKS_DIR = Path("E:/vscode ai project/books")
LIBRARY_DIR = Path("E:/vscode ai project/harness/knowledge/library")
INDEX_FILE = LIBRARY_DIR / "book_index.json"
CHUNK_SIZE = 2000  # chars per chunk
CHUNK_OVERLAP = 200  # overlap between chunks

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ---------------------------------------------------------------------------
# PDF Extraction
# ---------------------------------------------------------------------------

def extract_pdf(path):
    """Extract text from a PDF file."""
    try:
        import pdfplumber
        text = []
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages):
                try:
                    t = page.extract_text()
                    if t:
                        text.append(t)
                except Exception:
                    continue
                if i >= 500:  # cap at 500 pages
                    break
        return "\n\n".join(text)
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# EPUB Extraction
# ---------------------------------------------------------------------------

def extract_epub(path):
    """Extract text from an EPUB file."""
    try:
        import ebooklib
        from ebooklib import epub
        from html.parser import HTMLParser
        
        class HTMLStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
            def handle_data(self, data):
                self.text.append(data)
            def get_text(self):
                return " ".join(self.text)
        
        book = epub.read_epub(str(path), options={"ignore_ncx": True})
        text = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                try:
                    content = item.get_content().decode("utf-8", errors="ignore")
                    stripper = HTMLStripper()
                    stripper.feed(content)
                    t = stripper.get_text().strip()
                    if t and len(t) > 50:
                        text.append(t)
                except Exception:
                    continue
        return "\n\n".join(text)
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text, title, source_path, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks with metadata."""
    if not text or text.startswith("ERROR:"):
        return []
    
    # Clean the text
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) < 100:
        return []
    
    chunks = []
    pos = 0
    idx = 0
    while pos < len(text):
        end = min(pos + chunk_size, len(text))
        # Try to break at sentence boundary
        if end < len(text):
            for sep in ['. ', '.\n', '\n\n', '\n', ' ']:
                brk = text.rfind(sep, pos + chunk_size // 2, end)
                if brk > pos:
                    end = brk + len(sep)
                    break
        
        chunk_text_str = text[pos:end].strip()
        if len(chunk_text_str) > 50:
            # Extract keywords for search
            words = set(re.findall(r'[a-zA-Z]{4,}', chunk_text_str.lower()))
            chunks.append({
                "title": title,
                "source": str(source_path),
                "chunk_id": idx,
                "text": chunk_text_str,
                "keywords": list(words)[:50],  # top 50 keywords
                "chars": len(chunk_text_str),
            })
            idx += 1
        
        pos = end - overlap if end < len(text) else end
    
    return chunks


# ---------------------------------------------------------------------------
# Ingestion — scan books directory and build index
# ---------------------------------------------------------------------------

def ingest_all():
    """Scan books directory, extract text, chunk, and build index."""
    log(f"Scanning {BOOKS_DIR}...")
    
    # Find all PDFs and EPUBs
    files = []
    for ext in ["*.pdf", "*.epub"]:
        files.extend(BOOKS_DIR.rglob(ext))
    
    log(f"Found {len(files)} files to process")
    
    # Load existing index to skip already-processed files
    existing = {}
    if INDEX_FILE.exists():
        try:
            data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            for chunk in data.get("chunks", []):
                existing[chunk.get("source", "")] = True
            log(f"  Existing index: {len(data.get('chunks', []))} chunks from {len(data.get('books', []))} books")
        except Exception:
            pass
    
    all_chunks = []
    books_processed = []
    skipped = 0
    errors = 0
    start = time.time()
    
    for i, fpath in enumerate(sorted(files)):
        src = str(fpath)
        if src in existing:
            skipped += 1
            continue
        
        # Title from directory name or filename
        title = fpath.parent.name if fpath.parent != BOOKS_DIR else fpath.stem
        title = re.sub(r'\s+', ' ', title).strip()
        
        pct = (i + 1) / len(files) * 100
        log(f"  [{i+1}/{len(files)} {pct:.0f}%] {title[:60]}...")
        
        # Extract
        if fpath.suffix.lower() == ".pdf":
            text = extract_pdf(fpath)
        elif fpath.suffix.lower() == ".epub":
            text = extract_epub(fpath)
        else:
            continue
        
        if not text or text.startswith("ERROR:"):
            errors += 1
            log(f"    SKIP: {text[:60] if text else 'empty'}")
            continue
        
        # Chunk
        chunks = chunk_text(text, title, src)
        if chunks:
            all_chunks.extend(chunks)
            books_processed.append({
                "title": title,
                "source": src,
                "chunks": len(chunks),
                "chars": sum(c["chars"] for c in chunks),
            })
            log(f"    OK: {len(chunks)} chunks, {len(text):,} chars")
        else:
            log(f"    SKIP: no usable text")
    
    elapsed = time.time() - start
    
    # Save index
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    index = {
        "created": datetime.now().isoformat(),
        "books": books_processed,
        "total_books": len(books_processed),
        "total_chunks": len(all_chunks),
        "total_chars": sum(c["chars"] for c in all_chunks),
        "chunks": all_chunks,
    }
    
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    
    log(f"")
    log(f"{'='*60}")
    log(f"  INGESTION COMPLETE")
    log(f"  Books processed: {len(books_processed)}")
    log(f"  Chunks created: {len(all_chunks)}")
    log(f"  Total chars: {sum(c['chars'] for c in all_chunks):,}")
    log(f"  Skipped (already indexed): {skipped}")
    log(f"  Errors: {errors}")
    log(f"  Time: {elapsed:.0f}s")
    log(f"  Index: {INDEX_FILE}")
    log(f"  Size: {INDEX_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    log(f"{'='*60}")


# ---------------------------------------------------------------------------
# Search — keyword search across all chunks
# ---------------------------------------------------------------------------

def search_index(query, top_k=5):
    """Search the book index by keyword matching."""
    if not INDEX_FILE.exists():
        print("No index found. Run: python ingest_books.py")
        return []
    
    data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    chunks = data.get("chunks", [])
    
    # Tokenize query
    query_words = set(re.findall(r'[a-zA-Z]{3,}', query.lower()))
    if not query_words:
        print("No valid search terms.")
        return []
    
    # Score each chunk by keyword overlap
    scored = []
    for chunk in chunks:
        kw = set(chunk.get("keywords", []))
        overlap = query_words & kw
        if overlap:
            # Score: number of matching keywords + bonus for title match
            score = len(overlap)
            title_words = set(re.findall(r'[a-zA-Z]{3,}', chunk["title"].lower()))
            title_overlap = query_words & title_words
            score += len(title_overlap) * 3  # title matches worth 3x
            scored.append((score, chunk))
    
    # Sort by score descending
    scored.sort(key=lambda x: -x[0])
    results = scored[:top_k]
    
    print(f"\nSearch: '{query}' ({len(scored)} matches, showing top {top_k})")
    print("-" * 60)
    for score, chunk in results:
        print(f"\n[{score}] {chunk['title']}")
        print(f"    Chunk {chunk['chunk_id']} | {chunk['chars']} chars")
        # Show first 200 chars of the chunk
        preview = chunk["text"][:200].replace("\n", " ")
        print(f"    {preview}...")
    
    return [c for _, c in results]


# ---------------------------------------------------------------------------
# Context retrieval — for injection into AI prompts
# ---------------------------------------------------------------------------

def get_context(query, max_chars=4000):
    """Retrieve relevant chunks as a text block for AI prompt injection."""
    results = search_index(query, top_k=10)
    context = []
    total = 0
    for chunk in results:
        if total + chunk["chars"] > max_chars:
            break
        context.append(f"[{chunk['title']}]\n{chunk['text']}")
        total += chunk["chars"]
    return "\n\n---\n\n".join(context)


def show_stats():
    """Show index statistics."""
    if not INDEX_FILE.exists():
        print("No index found. Run: python ingest_books.py")
        return
    
    data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    books = data.get("books", [])
    chunks = data.get("chunks", [])
    total_chars = data.get("total_chars", 0)
    
    print(f"\n{'='*60}")
    print(f"  LIBRARY INDEX STATS")
    print(f"{'='*60}")
    print(f"  Books: {len(books)}")
    print(f"  Chunks: {len(chunks)}")
    print(f"  Total chars: {total_chars:,}")
    print(f"  Total words: ~{total_chars // 5:,}")
    print(f"  Index size: {INDEX_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"{'='*60}")
    print(f"\n  Top books by chunk count:")
    for b in sorted(books, key=lambda x: -x["chunks"])[:15]:
        print(f"    {b['chunks']:4d} chunks | {b['title'][:55]}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Book Ingestion Pipeline")
    parser.add_argument("--query", "-q", help="Search the index")
    parser.add_argument("--stats", "-s", action="store_true", help="Show index stats")
    parser.add_argument("--context", "-c", help="Get AI context for a query")
    args = parser.parse_args()
    
    if args.query:
        search_index(args.query)
    elif args.stats:
        show_stats()
    elif args.context:
        print(get_context(args.context))
    else:
        ingest_all()
