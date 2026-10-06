"""API integration tests for ClauseGuard."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.services.classifier import classifier
from app.services.embedder import embedder

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def setup_models_for_testing():
    """Ensure classifier and embedder are available during API tests."""
    if not embedder.is_loaded:
        embedder.load("sentence-transformers/all-MiniLM-L6-v2")
        
    if not classifier.is_loaded:
        # If fine-tuned model checkpoint is not yet saved, provide a lightweight mock
        classifier._loaded = True
        classifier.id2label = {
            0: "Anti-Assignment",
            1: "Audit Rights",
            2: "Cap on Liability",
            3: "Change of Control",
            4: "Exclusivity",
            5: "IP Ownership Assignment",
            6: "Liquidated Damages",
            7: "No Clause",
            8: "Non-Compete",
            9: "Termination for Convenience",
            10: "Uncapped Liability",
        }
        def mock_predict(texts, **kwargs):
            results = []
            for t in texts:
                tl = t.lower()
                if "compete" in tl:
                    label = "Non-Compete"
                elif "uncapped" in tl or "no liability cap" in tl:
                    label = "Uncapped Liability"
                elif "assign" in tl:
                    label = "Anti-Assignment"
                elif "audit" in tl:
                    label = "Audit Rights"
                elif "terminate" in tl:
                    label = "Termination for Convenience"
                elif "intellectual property" in tl or "inventions" in tl:
                    label = "IP Ownership Assignment"
                elif "exclusiv" in tl:
                    label = "Exclusivity"
                elif "cap" in tl or "limited" in tl:
                    label = "Cap on Liability"
                elif "liquidated" in tl:
                    label = "Liquidated Damages"
                elif "control" in tl:
                    label = "Change of Control"
                else:
                    label = "No Clause"
                results.append({"label": label, "confidence": 0.92})
            return results
        classifier.predict = mock_predict


def test_health_check(client: TestClient) -> None:
    """Test health check returns liveness and model readiness."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "classifier_loaded" in data
    assert "embedder_loaded" in data


def test_insights_endpoint(client: TestClient) -> None:
    """Test insights returns metrics dictionary."""
    response = client.get("/api/v1/insights")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "baseline" in data["metrics"]


def test_analyze_valid_txt(client: TestClient) -> None:
    """Test uploading and analyzing a real sample NDA text contract."""
    nda_path = FIXTURES_DIR / "nda_sample.txt"
    assert nda_path.exists(), "nda_sample.txt fixture missing"
    
    with open(nda_path, "rb") as f:
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("nda_sample.txt", f, "text/plain")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert data["filename"] == "nda_sample.txt"
    assert len(data["clauses"]) > 0
    assert data["risk_summary"]["overall_risk"] in ("High", "Medium", "Low")
    assert data["risk_summary"]["high_count"] >= 1  # NDA contains Non-Compete and Uncapped Liability


def test_analyze_valid_pdf(client: TestClient) -> None:
    """Test uploading and analyzing a real sample freelance agreement PDF."""
    pdf_path = FIXTURES_DIR / "freelance_agreement.pdf"
    assert pdf_path.exists(), "freelance_agreement.pdf fixture missing"
    
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("freelance_agreement.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert data["filename"] == "freelance_agreement.pdf"
    assert len(data["clauses"]) > 0


def test_analyze_empty_file(client: TestClient) -> None:
    """Test empty file returns 422 NoTextExtractedError."""
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "NO_TEXT_EXTRACTED"


def test_analyze_wrong_file_type(client: TestClient) -> None:
    """Test unsupported file extension returns 400."""
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("table.csv", b"a,b,c\n1,2,3", "text/csv")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_analyze_file_too_large(client: TestClient) -> None:
    """Test file exceeding 10 MB returns 413 FileTooLargeError."""
    # 11 MB dummy payload
    oversized_data = b"X" * (11 * 1024 * 1024)
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("large_contract.txt", oversized_data, "text/plain")},
    )
    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "FILE_TOO_LARGE"


def test_analyze_scanned_pdf_no_text(client: TestClient, scanned_pdf_bytes: bytes) -> None:
    """Test empty/scanned PDF without text layer returns 422."""
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("scanned.pdf", scanned_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "NO_TEXT_EXTRACTED"


def test_analyze_non_contract_text(client: TestClient) -> None:
    """Test non-contract text (recipe) processes gracefully."""
    recipe_text = b"""
    Classic Chocolate Chip Cookies Recipe
    Ingredients: 2 cups flour, 1 cup butter, 1 cup brown sugar, 2 eggs, 2 cups chocolate chips.
    Instructions:
    Preheat oven to 375 degrees F.
    In a bowl, cream together butter and sugar until smooth.
    Beat in eggs one at a time. Gradually blend in flour.
    Stir in chocolate chips by hand. Drop by large spoonfuls onto ungreased pans.
    Bake for 10 minutes or until edges are golden brown. Cool on wire racks.
    """
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("recipe.txt", recipe_text, "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["clauses"]) > 0


def test_analyze_unicode_text(client: TestClient) -> None:
    """Test contract with unicode and multi-lingual characters."""
    unicode_text = """
    CONTRAT DE CONFIDENTIALITÉ ET ACCORD COMMERCIAL
    Article 1. Non-concurrence (Non-Compete)
    Le prestataire s'engage à ne pas concurrencer l'entreprise pendant 2 ans.
    Article 2. Audit et vérification (Audit Rights)
    Die Gesellschaft ist berechtigt, die Geschäftsunterlagen jederzeit zu prüfen.
    Article 3. Juridiction (Delaware, Tokyo 東京都)
    """.encode("utf-8")
    
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("international_contract.txt", unicode_text, "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["clauses"]) > 0


def test_semantic_search_and_unknown_doc(client: TestClient) -> None:
    """Test semantic search over analyzed document and 404 on missing document."""
    nda_path = FIXTURES_DIR / "nda_sample.txt"
    with open(nda_path, "rb") as f:
        upload_resp = client.post(
            "/api/v1/analyze",
            files={"file": ("nda_sample.txt", f, "text/plain")},
        )
    doc_id = upload_resp.json()["document_id"]
    
    # Valid search
    search_resp = client.post(
        "/api/v1/search",
        json={"document_id": doc_id, "query": "can I work for a competitor after leaving?", "top_k": 3},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert len(results) > 0
    assert results[0]["similarity"] > 0.0
    
    # Unknown document search
    fake_id = "00000000-0000-0000-0000-000000000000"
    missing_resp = client.post(
        "/api/v1/search",
        json={"document_id": fake_id, "query": "liability limits", "top_k": 3},
    )
    assert missing_resp.status_code == 404
    assert missing_resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_history_and_deletion_lifecycle(client: TestClient) -> None:
    """Test listing documents, retrieving detail, and deleting document."""
    nda_path = FIXTURES_DIR / "nda_sample.txt"
    with open(nda_path, "rb") as f:
        upload_resp = client.post(
            "/api/v1/analyze",
            files={"file": ("nda_sample.txt", f, "text/plain")},
        )
    doc_id = upload_resp.json()["document_id"]
    
    # List documents
    list_resp = client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()["documents"]
    assert any(d["id"] == doc_id for d in docs)
    
    # Get document detail
    detail_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == doc_id
    assert len(detail_resp.json()["clauses"]) > 0
    
    # Delete document
    del_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"
    
    # Verify 404 after deletion
    after_del = client.get(f"/api/v1/documents/{doc_id}")
    assert after_del.status_code == 404


def test_regression_config_paths_resolved() -> None:
    """Regression test: verify artifact and model paths resolve to real files."""
    from app.config import settings
    assert Path(settings.model_path).exists(), f"model_path not found: {settings.model_path}"
    assert Path(settings.label_map_path).exists(), f"label_map_path not found: {settings.label_map_path}"
    assert Path(settings.metrics_path).exists(), f"metrics_path not found: {settings.metrics_path}"


def test_regression_model_not_loaded_envelope(client: TestClient) -> None:
    """Regression test: verify model not loaded returns structured 503 JSON envelope."""
    was_loaded = classifier._loaded
    try:
        classifier._loaded = False
        nda_path = FIXTURES_DIR / "nda_sample.txt"
        with open(nda_path, "rb") as f:
            resp = client.post(
                "/api/v1/analyze",
                files={"file": ("nda_sample.txt", f, "text/plain")},
            )
        assert resp.status_code == 503
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "MODEL_NOT_LOADED"
        assert "message" in data["error"]
        assert "ML model is not loaded" in data["error"]["message"]
    finally:
        classifier._loaded = was_loaded


def test_regression_http_error_structured_envelope(client: TestClient) -> None:
    """Regression test: verify 404 and HTTP exceptions return structured error envelope."""
    resp = client.get("/api/v1/nonexistent_endpoint")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "message" in data["error"]


def test_regression_validation_error_structured_envelope(client: TestClient) -> None:
    """Regression test: verify Pydantic validation errors return structured 422 envelope."""
    resp = client.post("/api/v1/search", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in data["error"]


def test_regression_analyze_freelance_agreement_txt(client: TestClient) -> None:
    """Regression test: verify DOC-01 freelance agreement upload succeeds end-to-end."""
    contract_path = Path(__file__).resolve().parent.parent.parent / "clauseguard-testkit" / "contracts" / "DOC-01_freelance_agreement.txt"
    assert contract_path.exists(), f"Test contract missing at {contract_path}"

    with open(contract_path, "rb") as f:
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("DOC-01_freelance_agreement.txt", f, "text/plain")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "document_id" in data
    assert data["filename"] == "DOC-01_freelance_agreement.txt"
    assert len(data["clauses"]) > 0
    assert data["risk_summary"]["overall_risk"] in ("High", "Medium", "Low")
    assert data["risk_summary"]["total_clauses"] == len(data["clauses"])

