"""ingest_all() must carry the existing index forward, not overwrite it with
only this run's chunks (#13).

Done-when (from the issue):
  - running ingest twice in a row leaves total_chunks unchanged;
  - adding one book increases total_chunks by exactly that book's chunks;
  - a book whose source file is gone drops out.

Run: python agents/scripts/test_ingest_books_incremental.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest_books


def _run(tmp, make_books):
    """Point the module at a scratch dir, lay down the given book files, stub
    extraction, run ingest_all(), and return the written index dict."""
    books = Path(tmp) / "books"
    lib = Path(tmp) / "lib"
    books.mkdir(exist_ok=True)
    for name in make_books:
        (books / name).write_text("x", encoding="utf-8")   # content unused (stubbed)
    index_file = lib / "book_index.json"
    with mock.patch.object(ingest_books, "BOOKS_DIR", books), \
         mock.patch.object(ingest_books, "LIBRARY_DIR", lib), \
         mock.patch.object(ingest_books, "INDEX_FILE", index_file), \
         mock.patch.object(ingest_books, "extract_pdf", lambda p: "some text " * 600):
        ingest_books.ingest_all()
    return json.loads(index_file.read_text(encoding="utf-8"))


def test_rerun_is_stable_and_add_is_incremental():
    with tempfile.TemporaryDirectory() as tmp:
        # Run 1: two books.
        idx1 = _run(tmp, ["a.pdf", "b.pdf"])
        assert idx1["total_chunks"] > 0
        assert idx1["total_books"] == 2
        n1 = idx1["total_chunks"]

        # Run 2: no change -> identical chunk count (the bug produced 0 here).
        idx2 = _run(tmp, [])  # files already on disk from run 1
        assert idx2["total_chunks"] == n1, f"re-run changed total_chunks {n1} -> {idx2['total_chunks']}"
        assert idx2["total_books"] == 2

        # Per-book chunk count, to assert the exact delta next.
        per_book = idx2["total_chunks"] // 2

        # Run 3: add one book -> up by exactly that book's chunks.
        idx3 = _run(tmp, ["c.pdf"])
        assert idx3["total_books"] == 3
        assert idx3["total_chunks"] == n1 + per_book, \
            f"adding a book changed total by {idx3['total_chunks'] - n1}, expected {per_book}"


def test_missing_source_file_is_dropped():
    with tempfile.TemporaryDirectory() as tmp:
        idx1 = _run(tmp, ["a.pdf", "b.pdf"])
        assert idx1["total_books"] == 2
        # Delete one book's source, re-run: it drops out, the other stays.
        (Path(tmp) / "books" / "a.pdf").unlink()
        idx2 = _run(tmp, [])
        assert idx2["total_books"] == 1
        sources = {b["source"] for b in idx2["books"]}
        assert not any("a.pdf" in s for s in sources)
        assert any("b.pdf" in s for s in sources)
        assert all("a.pdf" not in c["source"] for c in idx2["chunks"])


def test_write_is_atomic_no_tmp_left():
    with tempfile.TemporaryDirectory() as tmp:
        _run(tmp, ["a.pdf"])
        leftovers = list((Path(tmp) / "lib").glob("*.tmp"))
        assert not leftovers, f"temp file left behind: {leftovers}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
    print("test_ingest_books_incremental: OK")
