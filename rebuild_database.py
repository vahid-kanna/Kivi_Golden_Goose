import os
from data.generate_corpus import generate_500_corpus
from backend.database import reset_db
from import_corpus import import_corpus

if __name__ == "__main__":
    corpus_file = os.path.join("data", "corpus_500.jsonl")
    print("[1] Generating 500 authentic narrative records...")
    generate_500_corpus(corpus_file)

    print("[2] Resetting SQLite schema...")
    reset_db()

    print("[3] Ingesting corpus into Kivi Memory Engine...")
    stats = import_corpus(corpus_file, verbose=True)
    print("[✓] Rebuild successfully completed!")
