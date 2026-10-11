"""Verify post-patch state of ChromaDB SQLite and backend init."""
import sys, os, json, sqlite3
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, 'core'))
os.chdir(_HERE)

from config import get_settings
settings = get_settings()

# ── DB state ─────────────────────────────────────────────────────────────────
print("Post-patch DB state:")
db_file = os.path.join(settings.CHROMA_LOCAL_PATH, 'chroma.sqlite3')
db = sqlite3.connect(db_file)
db.row_factory = sqlite3.Row
cur = db.cursor()
cur.execute("SELECT id, name, config_json_str FROM collections")
rows = cur.fetchall()
from chromadb.api.configuration import CollectionConfigurationInternal
for r in rows:
    cfg_str = r["config_json_str"]
    parsed = json.loads(cfg_str)
    space = parsed.get("hnsw_configuration", {}).get("space", "?")
    col_type = parsed.get("_type", "MISSING")
    # Verify it round-trips through 0.6.3
    try:
        CollectionConfigurationInternal.from_json_str(cfg_str)
        roundtrip = "OK"
    except Exception as e:
        roundtrip = f"FAIL: {e}"
    print(f"  {r['name']}: _type={col_type}, space={space}, roundtrip={roundtrip}")
db.close()
print()

# ── ChromaDB client ──────────────────────────────────────────────────────────
import chromadb

class _DummyEF:
    def __call__(self, input): return []

print("Opening PersistentClient...")
client = chromadb.PersistentClient(path=settings.CHROMA_LOCAL_PATH)
print("  PersistentClient: OK")

ef = _DummyEF()
expected = {'text_chunks': 2519, 'table_data': 1057, 'visual_summaries': 0}
all_pass = True
for col_name, exp_count in expected.items():
    try:
        col = client.get_collection(col_name, embedding_function=ef)
        count = col.count()
        ok = count == exp_count
        if not ok:
            all_pass = False
        print(f"  [{('PASS' if ok else 'FAIL')}] {col_name}: count={count} (expected {exp_count})")
    except Exception as e:
        print(f"  [FAIL] {col_name}: {type(e).__name__}: {e}")
        all_pass = False

print()
print("Result:", "ALL PASS" if all_pass else "SOME FAILURES")
