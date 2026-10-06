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
