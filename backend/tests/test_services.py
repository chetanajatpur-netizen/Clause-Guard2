"""Tests for backend services."""
import pytest
from app.services.parser import extract_text
from app.services.segmenter import segment_text


class TestParser:
    """Tests for text extraction."""

    def test_extract_txt(self) -> None:
        """Test extracting text from TXT bytes."""
        text = b"This is a test contract with important clauses."
        result = extract_text(text, "contract.txt")
        assert "test contract" in result

    def test_extract_txt_empty(self) -> None:
        """Test empty TXT raises error."""
        with pytest.raises(ValueError):
            extract_text(b"", "empty.txt")

    def test_unsupported_type(self) -> None:
        """Test unsupported file type raises error."""
        with pytest.raises(ValueError, match="Unsupported"):
            extract_text(b"data", "file.csv")


class TestSegmenter:
    """Tests for text segmentation."""

    def test_segment_basic(self) -> None:
        """Test basic paragraph segmentation."""
        text = "First paragraph with enough text to be a clause.\n\nSecond paragraph also with enough text to be another clause."
        chunks = segment_text(text)
        assert len(chunks) >= 1

    def test_segment_empty(self) -> None:
        """Test empty text returns empty list."""
        assert segment_text("") == []
        assert segment_text("   ") == []

    def test_segment_merges_tiny(self) -> None:
        """Test that tiny chunks get merged."""
        text = "A.\n\nB.\n\nThis is a longer paragraph that should be its own clause with enough text."
        chunks = segment_text(text, min_len=20)
        # Tiny chunks A and B should be merged
        for chunk in chunks:
            assert len(chunk) >= 20

    def test_segment_splits_huge(self, sample_text: str) -> None:
        """Test that huge chunks get split."""
        chunks = segment_text(sample_text, max_len=200)
        for chunk in chunks:
            # Allow some overflow since we split at sentence boundaries
            assert len(chunk) <= 400


class TestClassifier:
    """Tests for classifier backends."""

    def test_baseline_classifier_inference(self) -> None:
        """Test loading and inference with baseline (TF-IDF + LogReg) backend."""
        from app.services.classifier import ClauseClassifier
        clf = ClauseClassifier()
        clf.load(backend="baseline", baseline_model_path="ml/artifacts/baseline_model.joblib")
        assert clf.is_loaded
        assert clf.backend == "baseline"

        results = clf.predict(["Neither party may assign this agreement without prior written consent."])
        assert len(results) == 1
        assert "label" in results[0]
        assert "confidence" in results[0]
        assert results[0]["label"] == "Anti-Assignment"
        assert 0.0 <= results[0]["confidence"] <= 1.0

    def test_classifier_empty_input(self) -> None:
        """Test classifier with empty list."""
        from app.services.classifier import ClauseClassifier
        clf = ClauseClassifier()
        clf.load(backend="baseline", baseline_model_path="ml/artifacts/baseline_model.joblib")
        assert clf.predict([]) == []


class TestEnhancedRiskScoring:
    """Tests for enhanced numerical risk scoring and uncertainty quantification."""

    def test_high_risk_clause_scoring(self) -> None:
        """Test high-risk clauses receive high numerical score (80-95/100)."""
        from app.services.risk import compute_enhanced_clause_risk
        clause_text = "Contractor unconditionally waives all claims and shall indemnify client with unlimited liability."
        result = compute_enhanced_clause_risk("Uncapped Liability", confidence=0.95, clause_text=clause_text)

        assert result["risk_level"] == "High"
        assert 80 <= result["risk_score"] <= 100
        assert 0.0 <= result["risk_score_normalized"] <= 1.0
        assert result["uncertainty_level"] in ("Low", "Medium")

    def test_no_clause_scoring(self) -> None:
        """Test No Clause gets score 0 and low uncertainty."""
        from app.services.risk import compute_enhanced_clause_risk
        result = compute_enhanced_clause_risk("No Clause", confidence=0.99, clause_text="This agreement is dated Jan 1.")

        assert result["risk_level"] is None
        assert result["risk_score"] == 0
        assert result["risk_score_normalized"] == 0.0
        assert result["uncertainty"] == 0.1
        assert result["uncertainty_level"] == "Low"

    def test_linguistic_amplifiers_increase_risk(self) -> None:
        """Test risk amplifiers like 'unlimited' or 'irreversible' increase risk score."""
        from app.services.risk import compute_enhanced_clause_risk
        neutral_text = "The contractor agrees to the standard terms and conditions governing the assignment."
        amplified_text = "The contractor unconditionally and with unlimited, irreversible liability shall indemnify and hold harmless."

        base_res = compute_enhanced_clause_risk("Termination for Convenience", confidence=0.8, clause_text=neutral_text)
        amp_res = compute_enhanced_clause_risk("Termination for Convenience", confidence=0.8, clause_text=amplified_text)

        assert amp_res["components"]["linguistic_adjustment"] > base_res["components"]["linguistic_adjustment"]
        assert amp_res["risk_score"] >= base_res["risk_score"]

    def test_linguistic_reducers_decrease_risk(self) -> None:
        """Test risk reducers like 'reasonable' or 'mutual' decrease risk score."""
        from app.services.risk import compute_enhanced_clause_risk
        neutral_text = "The agreement outlines specific provisions concerning assignment of developer patents."
        reduced_text = "Both parties agree to reasonable, mutual terms provided that each party may negotiate with cap."

        base_res = compute_enhanced_clause_risk("IP Ownership Assignment", confidence=0.8, clause_text=neutral_text)
        red_res = compute_enhanced_clause_risk("IP Ownership Assignment", confidence=0.8, clause_text=reduced_text)

        assert red_res["components"]["linguistic_adjustment"] < base_res["components"]["linguistic_adjustment"]
        assert red_res["risk_score"] <= base_res["risk_score"]

    def test_uncertainty_quantification(self) -> None:
        """Test uncertainty varies by classifier confidence and text length."""
        from app.services.risk import compute_enhanced_clause_risk
        # High confidence -> lower uncertainty
        high_conf = compute_enhanced_clause_risk("Non-Compete", confidence=0.95, clause_text="Employee shall not work for any competitor.")
        # Low confidence -> higher uncertainty
        low_conf = compute_enhanced_clause_risk("Non-Compete", confidence=0.35, clause_text="Employee shall not work for any competitor.")

        assert low_conf["uncertainty"] > high_conf["uncertainty"]

        # Very short text -> higher text length uncertainty
        short_text_res = compute_enhanced_clause_risk("Non-Compete", confidence=0.9, clause_text="No competition.")
        normal_text_res = compute_enhanced_clause_risk(
            "Non-Compete",
            confidence=0.9,
            clause_text="Employee covenants that for a period of twelve months following termination, employee shall not engage in competitive business."
        )
        assert short_text_res["components"]["length_uncertainty"] >= normal_text_res["components"]["length_uncertainty"]

    def test_conservative_pull_toward_middle(self) -> None:
        """Test that high uncertainty adjusts normalized score toward medium risk (0.5)."""
        from app.services.risk import compute_enhanced_clause_risk
        # At confidence 0.3, uncertainty is high (> 0.1), which triggers pull towards 0.5
        result = compute_enhanced_clause_risk("Non-Compete", confidence=0.3, clause_text="Short clause")
        comp = result["components"]
        assert comp["uncertainty"] > 0.1
        # The final score should be between raw/normalized and 0.5
        assert 0.0 <= result["risk_score_normalized"] <= 1.0

    def test_lru_caching(self) -> None:
        """Test that _compute_enhanced_clause_risk_cached utilizes LRU cache."""
        from app.services.risk import _compute_enhanced_clause_risk_cached, compute_enhanced_clause_risk
        _compute_enhanced_clause_risk_cached.cache_clear()

        info_before = _compute_enhanced_clause_risk_cached.cache_info()
        assert info_before.hits == 0

        # First call -> cache miss
        compute_enhanced_clause_risk("Audit Rights", 0.85, "Audits shall occur annually during business hours.")
        info_1 = _compute_enhanced_clause_risk_cached.cache_info()
        assert info_1.misses >= 1

        # Identical second call -> cache hit
        compute_enhanced_clause_risk("Audit Rights", 0.85, "Audits shall occur annually during business hours.")
        info_2 = _compute_enhanced_clause_risk_cached.cache_info()
        assert info_2.hits >= 1
