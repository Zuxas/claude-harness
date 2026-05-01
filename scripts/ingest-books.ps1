# ingest-books.ps1 — Parse all books into searchable knowledge
#
# USAGE:
#   .\ingest-books.ps1              # ingest all PDFs and EPUBs
#   .\ingest-books.ps1 -Query "python networking"   # search
#   .\ingest-books.ps1 -Stats       # show index stats

param(
    [string]$Query = "",
    [switch]$Stats
)

$Script = "E:\vscode ai project\harness\agents\scripts\ingest_books.py"

if ($Query) {
    python $Script --query $Query
} elseif ($Stats) {
    python $Script --stats
} else {
    python $Script
}
