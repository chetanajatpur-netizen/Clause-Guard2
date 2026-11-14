"""Unit tests for Indic sentence segmenter on real Hindi and Kannada legal documents."""
import pytest
from app.services.indic_segmenter import (
    split_indic_sentences,
    split_indic_sentences_with_spans,
)

# 10 Real Hindi Legal Sentences extracted from Delhi High Court judgments
REAL_HINDI_SENTENCES = [
    "अͬधकरण सुधार अͬधǓनयम, 2021 के अनुसरण मɅ त×कालȣन बौɮͬधक संपदा अपील बोड[ के उÛमूलन के बाद वत[मान अपील Ʌ èथानांतरण पर ĤाÜत हुई थीं।",
    "यह अपील Ʌ åयापार ͬचéन अͬधǓनयम, 1999 कȧ धारा 91 के तहत Ĥ×यथȸ ɮवारा पाǐरत 31 अगèत 2018 के दो आदेश ɉ के ͪवरूɮध दायर कȧ गई हɇ।",
    "अपीलाथȸ कȧ ओर से वǐरçठ अͬधवÈता ने तक[ Ǒदया Ǒक Ĥ×यथȸ का आदेश Ǔनयमɉ के Ĥितकूल है।",
    "माननीय ÛयायमूǓत[ ने दोनɉ पआयɉ कȧ बहस सुनने के पæचात Ǔनण[य सुरिक्षत रख ͧलया।",
    "Ĥèतुत वाद मɅ वादी ने अपने åयापार ͬचéन के उãलंघन का आरोप लगाया है।",
    "कɅġ सरकार के èथायी अͬधवÈता ने Ĥितवादȣ कȧ ओर से अपना पआय Ĥèतुत Ǒकया।",
    "Ǒदãलȣ उÍच Ûयायालय ने अपीलाथȸ कȧ अपील को आंͧशक रूप से èवीकार Ǒकया।",
    "आदेश कȧ Ĥित उभय पआयɉ को Ǔनःशुãक उपलÞध कराई जाए।",
    "अधीनèथ अͬधकरण का आदेश Ǔनरèत Ǒकया जाता है और मामला पुनः ͪवचार हेतु वापस भेजा जाता है।",
    "सभी संबंͬधत आवेदन भी इसी आदेश के अनुसार Ǔनèताǐरत ͩकए जाते हɇ।",
]

# 10 Real Kannada Legal Sentences extracted from Karnataka State Gazette notifications
REAL_KANNADA_SENTENCES = [
    "ಕರ್ನಾಟಕ ರಾಜ್ಯ ಗ್ರಾಮ ಸ್ವರಾಜ್ ಮತ್ತು ಪಂಚಾಯತ್ ರಾಜ್ ಅಧಿನಿಯಮ 2020ರ 18ನೇ ಪ್ರಕರಣದ ಮೇರೆಗೆ ಈ ನಿಯಮಗಳನ್ನು ರಚಿಸಲಾಗಿದೆ.",
    "ಈ ನಿಯಮಗಳನ್ನು ಕರ್ನಾಟಕ ರಾಜ್ಯ ಗ್ರಾಮ ಸ್ವರಾಜ್ ಮತ್ತು ಪಂಚಾಯತ್ ರಾಜ್ (ತಿದ್ದುಪಡಿ) ನಿಯಮಗಳು, 2026 ಎಂದು ಕರೆಯತಕ್ಕದ್ದು.",
    "ಸದರಿ ಕರಡು ನಿಯಮಗಳ ಕುರಿತು ಬಾಧಿತರಾಗಬಹುದಾದ ಯಾವುದೇ ವ್ಯಕ್ತಿಯು ಆಕ್ಷೇಪಣೆ ಅಥವಾ ಸಲಹೆಗಳನ್ನು ಸಲ್ಲಿಸಬಹುದು.",
    "ಆಕ್ಷೇಪಣೆ ಮತ್ತು ಸಲಹೆಗಳನ್ನು ಸರ್ಕಾರದ ಅಪರ ಮುಖ್ಯ ಕಾರ್ಯದರ್ಶಿಗಳಿಗೆ ನಿಗದಿತ ಅವಧಿಯೊಳಗೆ ಕಳುಹಿಸತಕ್ಕದ್ದು.",
    "ರಾಜ್ಯ ಸರ್ಕಾರವು ನಿಗದಿತ ಅವಧಿಯಲ್ಲಿ ಸ್ವೀಕೃತವಾಗುವ ಎಲ್ಲಾ ಸಲಹೆಗಳನ್ನು ಪರಿಗಣಿಸಿ ಅಂತಿಮ ಆದೇಶ ಹೊರಡಿಸುತ್ತದೆ.",
    "ಈ ಅಧಿಸೂಚನೆಯು ಕರ್ನಾಟಕ ರಾಜ್ಯಪತ್ರದಲ್ಲಿ ಅಧಿಕೃತವಾಗಿ ಪ್ರಕಟವಾದ ದಿನಾಂಕದಿಂದ ಜಾರಿಗೆ ಬರತಕ್ಕದ್ದು.",
    "ಭೂಸ್ವಾಧೀನ ಪ್ರಕ್ರಿಯೆಯು ಸಾರ್ವಜನಿಕ ಉದ್ದೇಶಕ್ಕಾಗಿ ಮಾತ್ರವೇ ಕೈಗೊಳ್ಳಲ್ಪಡುತ್ತದೆ ಎಂದು ದೃಢೀಕರಿಸಲಾಗಿದೆ.",
    "ಸಕ್ಷಮ ಪ್ರಾಧಿಕಾರವು ಪರಿಹಾರ ಮೊತ್ತವನ್ನು 60 ದಿನಗಳ ಒಳಗೆ ಅರ್ಹ ಫಲಾನುಭವಿಗಳಿಗೆ ಪಾವತಿಸತಕ್ಕದ್ದು.",
    "ಯಾವುದೇ ವಿವಾದ ಉದ್ಭವಿಸಿದಲ್ಲಿ ಸಂಬಂಧಪಟ್ಟ ಜಿಲ್ಲಾ ನ್ಯಾಯಾಲಯದ ವ್ಯಾಪ್ತಿಗೆ ಒಳಪಟ್ಟಿರುತ್ತದೆ.",
    "ಸರ್ಕಾರದ ಆದೇಶದಂತೆ ಮತ್ತು ರಾಜ್ಯಪಾಲರ ಆಜ್ಞಾನುಸಾರ ಈ ಅಧಿಸೂಚನೆಯನ್ನು ಹೊರಡಿಸಲಾಗಿದೆ.",
]


def test_hindi_ten_real_sentences_single_corpus():
    # Concatenate 10 real Hindi sentences separated by dandas and newlines
    full_text = " ".join(REAL_HINDI_SENTENCES)
    result = split_indic_sentences(full_text)
    assert len(result) == 10
    for original, extracted in zip(REAL_HINDI_SENTENCES, result):
        assert original.strip() in extracted or extracted in original


def test_kannada_ten_real_sentences_single_corpus():
    # Concatenate 10 real Kannada sentences separated by full stops and spaces
    full_text = " ".join(REAL_KANNADA_SENTENCES)
    result = split_indic_sentences(full_text)
    assert len(result) == 10
    for original, extracted in zip(REAL_KANNADA_SENTENCES, result):
        assert original.strip() in extracted or extracted in original


def test_danda_and_double_danda_splitting():
    text = "प्रथमं वाक्यम् अत्र अस्ति। द्वितीयं वाक्यम् अत्र वर्तते॥ तृतीयं वाक्यम् अपि अस्ति।"
    sentences = split_indic_sentences(text)
    assert len(sentences) == 3
    assert "प्रथमं" in sentences[0]
    assert "द्वितीयं" in sentences[1]
    assert "तृतीयं" in sentences[2]


def test_decimal_preservation():
    text = "दिनांक 12.11.2026 को ब्याज दर 8.75% निर्धारित की गई। यह अंतिम दर है।"
    sentences = split_indic_sentences(text)
    assert len(sentences) == 2
    assert "12.11.2026" in sentences[0]
    assert "8.75%" in sentences[0]


def test_abbreviation_preservation():
    text = (
        "In D.H.C. case No. 128 under Sec. 91 of Trade Marks Act v. Registrar. "
        "The judgment was pronounced at 10.30 a.m. today."
    )
    sentences = split_indic_sentences(text)
    # Should not split on D.H.C., No., Sec., v., or a.m.
    assert len(sentences) == 2
    assert "D.H.C." in sentences[0]
    assert "Sec. 91" in sentences[0]


def test_numbered_lists_preservation():
    text = (
        "1. This is the first clause of the contract.\n"
        "2. This is the second clause of the contract."
    )
    sentences = split_indic_sentences(text)
    assert len(sentences) == 2
    assert sentences[0].startswith("1. This is the first")
    assert sentences[1].startswith("2. This is the second")


def test_indic_numbered_lists():
    text = (
        "१. प्रथम नियम लागू होगा।\n"
        "२. द्वितीय नियम प्रभावी होगा।"
    )
    sentences = split_indic_sentences(text)
    assert len(sentences) == 2
    assert "१." in sentences[0]
    assert "२." in sentences[1]


def test_split_with_character_spans():
    text = "पहला वाक्य यहाँ है। दूसरा वाक्य यहाँ है।"
    spans = split_indic_sentences_with_spans(text)
    assert len(spans) == 2
    assert spans[0]["text"] == "पहला वाक्य यहाँ है।"
    assert spans[0]["start"] == 0
    assert spans[1]["text"] == "दूसरा वाक्य यहाँ है।"
    assert spans[1]["start"] > spans[0]["end"] - 5
