"""
RAG knowledge base: loads IST data files and provides hybrid search
using TF-IDF vectors + keyword matching. No external embedding deps needed.
"""

import os
import re
import math
import hashlib
from pathlib import Path
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

_documents = []
_tfidf_vectors = []
_idf = {}
_vocab = []


def _chunk_text(text, title, max_chars=800):
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 > max_chars and buf:
            chunks.append({"text": buf.strip(), "title": title})
            buf = p + "\n\n"
        else:
            buf += p + "\n\n"
    if buf.strip():
        chunks.append({"text": buf.strip(), "title": title})
    return chunks


def _load_documents():
    docs = []
    for fname in sorted(os.listdir(DATA_DIR)):
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        if fname.endswith(".json"):
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            continue
        title = Path(fname).stem.replace("_", " ").title()
        docs.extend(_chunk_text(text, title))
    return docs


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_tfidf():
    global _tfidf_vectors, _idf, _vocab

    doc_freq = Counter()
    token_lists = []
    for doc in _documents:
        tokens = set(_tokenize(doc["text"]))
        token_lists.append(tokens)
        for t in tokens:
            doc_freq[t] += 1

    n = len(_documents)
    _idf = {}
    for term, freq in doc_freq.items():
        _idf[term] = math.log((n + 1) / (freq + 1)) + 1

    _vocab = sorted(_idf.keys())
    vocab_idx = {t: i for i, t in enumerate(_vocab)}

    _tfidf_vectors = []
    for doc in _documents:
        tokens = _tokenize(doc["text"])
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1
        vec = {}
        for t, count in tf.items():
            if t in vocab_idx:
                vec[vocab_idx[t]] = (count / total) * _idf.get(t, 1)
        _tfidf_vectors.append(vec)

    print("[KB] TF-IDF index built with {} terms".format(len(_vocab)))


def _cosine_sim(vec_a, vec_b):
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _tfidf_search(query, top_k=6):
    tokens = _tokenize(query)
    if not tokens:
        return []
    tf = Counter(tokens)
    total = len(tokens)
    vocab_idx = {t: i for i, t in enumerate(_vocab)}
    q_vec = {}
    for t, count in tf.items():
        if t in vocab_idx:
            q_vec[vocab_idx[t]] = (count / total) * _idf.get(t, 1)
    if not q_vec:
        return []

    scored = []
    for i, doc_vec in enumerate(_tfidf_vectors):
        sim = _cosine_sim(q_vec, doc_vec)
        if sim > 0.01:
            scored.append((sim, i))
    scored.sort(key=lambda x: -x[0])
    return [_documents[i] for _, i in scored[:top_k]]


def _keyword_search(query, top_k=5):
    query_lower = query.lower()
    tokens = set(re.findall(r"\w+", query_lower))
    scored = []
    for doc in _documents:
        text_lower = doc["text"].lower()
        score = sum(2 for t in tokens if t in text_lower)
        if any(phrase in text_lower for phrase in [query_lower, query_lower.replace(" ", "")]):
            score += 5
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:top_k]]


def init_kb():
    global _documents
    _documents = _load_documents()
    print("[KB] Loaded {} chunks from {}".format(len(_documents), DATA_DIR))
    _build_tfidf()


def search(query, top_k=8):
    results = []

    tfidf_results = _tfidf_search(query, top_k=6)
    for r in tfidf_results:
        results.append(r)

    kw_results = _keyword_search(query, top_k=5)
    seen_texts = set()
    for r in results:
        seen_texts.add(r["text"][:100])
    for kw in kw_results:
        if kw["text"][:100] not in seen_texts:
            results.append(kw)
            seen_texts.add(kw["text"][:100])

    if not results:
        fallback_q = "admission programs fee merit IST eligibility"
        results = _keyword_search(fallback_q, top_k=4)

    results = results[:top_k]
    context_parts = []
    for r in results:
        context_parts.append("[{}]\n{}".format(r["title"], r["text"]))
    return "\n\n---\n\n".join(context_parts) if context_parts else "No relevant information found in the knowledge base."
