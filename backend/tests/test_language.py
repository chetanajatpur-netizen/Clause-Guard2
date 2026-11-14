"""Unit tests for language and script detection service."""
import pytest
from app.services.language import (
    analyze_scripts,
    detect_language,
    LanguageDetectionResult,
)


def test_pure_hindi_devanagari():
    text = "अͬधकरण सुधार अͬधǓनयम, 2021 के अनुसरण मɅ अपील ĤाÜत हुई थीं।"
    res = detect_language(text)
    assert res.language == "hindi"
    assert res.script == "Devanagari"
    assert res.confidence >= 0.80
    assert not res.is_mixed
    assert "Devanagari" in res.script_distribution


def test_pure_kannada():
    text = "ಕನಾ೯ಟಕ ರಾಜ್ಯ ಪಂಚಾಯತ್ ರಾಜ್ ನಿಯಮಗಳು, 2020 ಮತ್ತು ತಿದ್ದುಪಡಿ ನಿಯಮಗಳು."
    res = detect_language(text)
    assert res.language == "kannada"
    assert res.script == "Kannada"
    assert res.confidence >= 0.80
    assert not res.is_mixed
    assert res.script_distribution.get("Kannada", 0) > 80.0


def test_pure_english_latin():
    text = "This Agreement shall be governed by and construed in accordance with the laws of India."
    res = detect_language(text)
    assert res.language == "english"
    assert res.script == "Latin"
    assert res.confidence >= 0.80
    assert not res.is_mixed
    assert res.script_distribution.get("Latin", 0) > 80.0


def test_pure_telugu():
    text = "ఈ ఒప్పందము ప్రకారం కౌలుదారు ప్రతి నెలా క్రమం తప్పకుండా అద్దె చెల్లించవలెను."
    res = detect_language(text)
    assert res.language == "telugu"
    assert res.script == "Telugu"
    assert res.confidence >= 0.80
    assert not res.is_mixed
    assert "Telugu" in res.script_distribution


def test_mixed_hindi_english_detection():
    # Document excerpt with both Devanagari and Latin citations
    text = (
        "माननीय ÛयायमूǓत[ Įी अͧमत बंसल, Delhi High Court order in C.A.(COMM.IPD-TM) 5/2022 "
        "under Trade Marks Act, 1999."
    )
    res = detect_language(text)
    assert res.is_mixed is True
    assert "Devanagari" in res.script_distribution
    assert "Latin" in res.script_distribution
    assert res.language in ["hindi", "english"]


def test_empty_and_whitespace_text():
    res_empty = detect_language("")
    assert res_empty.language == "unknown"
    assert res_empty.confidence == 0.0

    res_spaces = detect_language("   \n\t  ")
    assert res_spaces.language == "unknown"
    assert res_spaces.confidence == 0.0


def test_numeric_only_text():
    res = detect_language("1234567890 2026.11.12")
    assert res.language == "unknown"
    assert res.confidence == 0.0


def test_script_frequency_analysis():
    text = "ಕನ್ನಡ Hindi हिंदी English"
    counts = analyze_scripts(text)
    assert counts["Kannada"] > 0
    assert counts["Devanagari"] > 0
    assert counts["Latin"] > 0
