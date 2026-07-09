#!/usr/bin/env python3
"""Vision RAG smoke tests.

Verifies:
1. Health endpoint
2. Text search (guest memories)
3. Hybrid search
4. Vision RAG documents endpoint
5. Vision RAG query endpoint
6. Langfuse observability wiring
7. Stats endpoint with docs namespace

Run:
    uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
import requests

BASE_URL = "http://127.0.0.1:8000"


def test_health():
    """Test health endpoint."""
    resp = requests.get(f"{BASE_URL}/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mongodb"] == "up"
    print("[PASS] Health: MongoDB up")


def test_text_search():
    """Test text search over guest memories."""
    resp = requests.get(f"{BASE_URL}/api/search?q=rain+hospitality+problems&namespace=guests")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    top = data["results"][0]
    assert top["score"] >= 0.6
    print(f"[PASS] Text search: {top['id']} ({top['score']:.3f})")


def test_hybrid_search():
    """Test hybrid vector + lexical search over guest memories."""
    resp = requests.get(
        f"{BASE_URL}/api/hybrid-search",
        params={"q": "rain hospitality reservation", "namespace": "guests"},
    )
    assert resp.status_code == 200, (
        f"Hybrid search returned HTTP {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data["count"] >= 1
    top = data["results"][0]
    assert top["hybrid_score"] > 0
    assert "vector_score" in top
    assert "lexical_score" in top
    print(
        "[PASS] Hybrid search: "
        f"{top['id']} (hybrid={top['hybrid_score']:.3f}, "
        f"lexical={top['lexical_score']:.3f})"
    )


def test_vision_documents():
    """Test vision RAG documents listing."""
    resp = requests.get(f"{BASE_URL}/api/vision-rag/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 5
    keys = [d["key"] for d in data["documents"]]
    assert "visual_allergen_matrix" in keys
    assert "visual_weather_response" in keys
    print(f"[PASS] Vision docs: {data['count']} documents indexed")


def test_vision_query():
    """Test vision RAG query endpoint."""
    resp = requests.post(
        f"{BASE_URL}/api/vision-rag/query",
        json={"query": "Which venues accommodate peanut allergies?", "limit": 1},
    )
    assert resp.status_code == 200, (
        f"Vision query returned HTTP {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "answer" in data, f"Vision query response missing answer: {data}"
    assert len(data["sources"]) >= 1, f"Vision query response missing sources: {data}"
    top = data["sources"][0]
    assert top["doc_type"] == "allergen_matrix", (
        f"Expected allergen_matrix as top source, got {top}"
    )
    assert top["score"] >= 0.7, f"Expected top source score >= 0.7, got {top}"
    print(f"[PASS] Vision query: {top['doc_type']} ({top['score']:.3f})")
    print(f"       Answer: {data['answer'][:100]}...")


def test_observability_status():
    """Test Langfuse observability status endpoint."""
    resp = requests.get(f"{BASE_URL}/api/observability/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "langfuse_enabled" in data
    assert "langfuse_host" in data
    print(
        "[PASS] Observability: "
        f"Langfuse {'enabled' if data['langfuse_enabled'] else 'not configured'}"
    )


def test_stats():
    """Test stats endpoint includes docs namespace."""
    resp = requests.get(f"{BASE_URL}/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    ns = data["memory_namespaces"]
    assert "docs_event_001" in ns
    assert ns["docs_event_001"] == 5
    print(f"[PASS] Stats: docs_event_001 = {ns['docs_event_001']}")


def main():
    print("\n=== Vision RAG Smoke Tests ===\n")

    try:
        test_health()
        test_text_search()
        test_hybrid_search()
        test_vision_documents()
        test_vision_query()
        test_observability_status()
        test_stats()
        print("\n[ALL PASS] Vision RAG is working correctly.\n")
        return 0
    except Exception as e:
        print(f"\n[FAIL] {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
