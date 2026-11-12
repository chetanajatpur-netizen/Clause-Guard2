"""Multilingual contract data audit script for ClauseWise.

Audits Hindi, Kannada, Telugu, and other Indic legal documents:
- File counts & types
- Scanned (% no text layer)
- Garbled non-Unicode extraction rate
- Document types & clause-level label presence
- PII-masked random text samples
- File size distribution & 10 largest files
"""
import argparse
import json
import logging
import os
import random
import re
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("multilingual_audit")

# Unicode Script Ranges
UNICODE_SCRIPTS = {
    "Hindi": (0x0900, 0x097F),       # Devanagari
    "Kannada": (0x0C80, 0x0CFF),     # Kannada
    "Telugu": (0x0C00, 0x0C7F),      # Telugu
    "Tamil": (0x0B80, 0x0BFF),       # Tamil
    "Malayalam": (0x0D00, 0x0D7F),   # Malayalam
    "Bengali": (0x0980, 0x09FF),     # Bengali
    "Gujarati": (0x0A80, 0x0AFF),    # Gujarati
    "English": (0x0020, 0x007F),     # Basic Latin
}

# Document Type Keywords (multilingual & English)
DOCTYPE_PATTERNS = {
    "Rental / Lease": [
        "lease", "rental", "rent agreement", "tenancy", "licence agreement", "leave and license",
        "किराया", "किरायेदार", "पट्टा", "भाड़ेदार", "भाड़ा",
        "ಬಾಡಿಗೆ", "ಗೇಣಿ", "ಕರಾರು", "ಬಾಡಿಗೆ ಕರಾರು",
        "అద్దె", "కౌలు", "అద్దె ఒప్పందం", "లీజు"
    ],
    "Property / Sale Deed": [
        "sale deed", "conveyance", "gift deed", "partition", "property", "title deed",
        "विक्रय विलेख", "बिक्री पत्र", "बैनामा", "संपत्ति", "स्वामित्व",
        "ಕ್ರಯ ಪತ್ರ", "ಖರೀದಿ", "ಆಸ್ತಿ", "ಹಕ್ಕು ಪತ್ರ",
        "విక్రయ పత్రం", "రిజిస్ట్రేషన్", "స్థిరాస్తి", "క్రయ పత్రము"
    ],
    "Court Order / Judgment": [
        "court", "order", "judgment", "decree", "petitioner", "respondent", "suit", "appeal",
        "न्यायालय", "आदेश", "फैसला", "निर्णय", "याचिकाकर्ता", "प्रतिवादी",
        "ನ್ಯಾಯಾಲಯ", "ತೀರ್ಪು", "ಆದೇಶ", "ಅರ್ಜಿದಾರ", "ಪ್ರತಿವಾದಿ",
        "న్యాయస్థానం", "తీర్పు", "ఆదేశం", "పిటిషనర్", "ప్రతివాది"
    ],
    "Employment / Service": [
        "employment", "appointment", "service agreement", "consultant", "contractor",
        "रोजगार", "नियुक्ति", "सेवा अनुबंध",
        "ಉದ್ಯೋಗ", "ನೇಮಕಾತಿ", "ಸೇವಾ ಒಪ್ಪಂದ",
        "ఉద్యోగం", "నియామక పత్రం", "సేవా ఒప్పందం"
    ]
}


def mask_pii(text: str) -> str:
    """Mask personally identifiable information (Names, Phones, IDs, Addresses)."""
    masked = text

    # Phone numbers (+91-XXXXX-XXXXX, 10-digit Indian mobiles)
    masked = re.sub(r"(?:\+91[\s\-]?)?[6789]\d{9}\b", "[PHONE]", masked)
    masked = re.sub(r"\b\d{3,5}[\s\-]\d{6,8}\b", "[PHONE]", masked)

    # PAN Card (5 letters, 4 digits, 1 letter)
    masked = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "[ID]", masked)

    # Aadhaar Number (12 digits, often grouped in 4s)
    masked = re.sub(r"\b\d{4}\s\d{4}\s\d{4}\b", "[ID]", masked)

    # Bank Account / Generic ID (9 to 18 digits)
    masked = re.sub(r"\b\d{10,18}\b", "[ID]", masked)

    # Indian Address / S/o / W/o / R/o patterns
    masked = re.sub(r"(?i)\b(?:S/o|D/o|W/o|R/o|c/o)\s+[A-Za-z\u0900-\u0D7F\s\.]+(?:,\s*|\n)", "[NAME], [ADDRESS], ", masked)
    masked = re.sub(r"(?i)\b(?:Mr\.|Mrs\.|Ms\.|Shri|Smt\.|Sri)\s+[A-Za-z\u0900-\u0D7F]+(?:\s+[A-Za-z\u0900-\u0D7F]+)*", "[NAME]", masked)

    # PIN codes (6 digits)
    masked = re.sub(r"\b[1-9][0-9]{5}\b", "[ADDRESS]", masked)

    return masked


def detect_dominant_script(text: str) -> str:
    """Detect dominant Indic script or English based on unicode codepoints."""
    counts = {lang: 0 for lang in UNICODE_SCRIPTS}
    for char in text:
        cp = ord(char)
        for lang, (start, end) in UNICODE_SCRIPTS.items():
            if start <= cp <= end:
                counts[lang] += 1
                break

    # Prioritize Indic scripts over Basic Latin if present
    indic_counts = {k: v for k, v in counts.items() if k != "English" and v > 0}
    if indic_counts:
        best_indic = max(indic_counts, key=lambda k: indic_counts[k])
        if indic_counts[best_indic] >= 20 or (indic_counts[best_indic] / max(1, len(text)) > 0.05):
            return best_indic

    if counts["English"] > 0:
        return "English"
    return "Unknown"


def is_garbled(text: str) -> bool:
    """Detect garbled extraction (mojibake, excessive replacement characters, unmapped glyphs)."""
    if not text:
        return False
    # Check for replacement character \ufffd
    if text.count("\ufffd") > 5 or (text.count("\ufffd") / len(text)) > 0.02:
        return True
    # Check for excessive unprintable / control characters
    control_count = sum(1 for c in text if ord(c) < 32 and c not in "\n\r\t")
    if control_count > 10 or (control_count / len(text)) > 0.05:
        return True
    return False


def extract_text_from_file(file_path: Path) -> tuple[str, bool]:
    """Extract raw text from PDF, TXT, DOCX, CSV, or JSON.
    
    Returns:
        (text, is_scanned)
    """
    suffix = file_path.suffix.lower()

    if suffix == ".txt":
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return content, False
        except Exception:
            return "", True

    elif suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages_text = []
            for p in reader.pages:
                t = p.extract_text() or ""
                pages_text.append(t)
            full_text = "\n".join(pages_text).strip()
            # If less than 50 chars extracted across all pages, it has no text layer (scanned)
            is_scanned = len(full_text) < 50
            return full_text, is_scanned
        except Exception as e:
            logger.warning("PDF extraction failed for %s: %s", file_path.name, e)
            return "", True

    elif suffix in (".csv", ".json", ".jsonl"):
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return content, False
        except Exception:
            return "", False

    return "", False


def unpack_archive_if_needed(data_path: Path, unpack_dir: Path) -> Path:
    """If data_path is an archive, unpack into a git-ignored directory."""
    if data_path.is_file():
        name = data_path.name.lower()
        if name.endswith(".zip"):
            logger.info("Unpacking ZIP archive %s to %s", data_path, unpack_dir)
            unpack_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(data_path, "r") as zf:
                zf.extractall(unpack_dir)
            return unpack_dir
        elif name.endswith((".tar.gz", ".tgz", ".tar")):
            logger.info("Unpacking TAR archive %s to %s", data_path, unpack_dir)
            unpack_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(data_path, "r:*") as tf:
                tf.extractall(unpack_dir)
            return unpack_dir
    return data_path


def audit_multilingual_dataset(root_path: Path) -> dict[str, Any]:
    """Audit all files in the provided path and generate report."""
    if not root_path.exists():
        raise FileNotFoundError(f"Provided data path does not exist: {root_path}")

    all_files: list[Path] = []
    if root_path.is_file():
        all_files = [root_path]
    else:
        for p in root_path.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                all_files.append(p)

    total_size_bytes = sum(f.stat().st_size for f in all_files)
    total_size_mb = total_size_bytes / (1024 * 1024)

    # 10 largest files
    sorted_by_size = sorted(all_files, key=lambda f: f.stat().st_size, reverse=True)
    top_10_largest = [
        {"name": f.name, "path": str(f), "size_mb": round(f.stat().st_size / (1024 * 1024), 2)}
        for f in sorted_by_size[:10]
    ]

    lang_stats: dict[str, dict[str, Any]] = {}
    lang_samples: dict[str, list[str]] = {}

    for f in all_files:
        ext = f.suffix.lower() or "no_ext"
        text, is_scanned = extract_text_from_file(f)
        garbled = is_garbled(text)
        char_len = len(text)

        dominant_lang = detect_dominant_script(text) if text else "Unknown (Scanned/Empty)"

        # Initialize language entry
        if dominant_lang not in lang_stats:
            lang_stats[dominant_lang] = {
                "file_count": 0,
                "file_types": {},
                "scanned_count": 0,
                "garbled_count": 0,
                "total_chars": 0,
                "document_types": {},
                "clause_columns": set(),
                "sources_found": set(),
                "licences_found": set(),
            }
            lang_samples[dominant_lang] = []

        st = lang_stats[dominant_lang]
        st["file_count"] += 1
        st["file_types"][ext] = st["file_types"].get(ext, 0) + 1
        if is_scanned:
            st["scanned_count"] += 1
        if garbled:
            st["garbled_count"] += 1
        st["total_chars"] += char_len

        # Document type inference
        text_lower = text.lower()
        matched_type = "Other / Uncategorized"
        for dtype, patterns in DOCTYPE_PATTERNS.items():
            if any(pat in text_lower for pat in patterns):
                matched_type = dtype
                break
        st["document_types"][matched_type] = st["document_types"].get(matched_type, 0) + 1

        # Check for clause-level columns if tabular
        if ext in (".csv", ".json", ".jsonl"):
            try:
                if ext == ".csv":
                    import pandas as pd
                    df_sample = pd.read_csv(f, nrows=2)
                    cols = list(df_sample.columns)
                    for c in cols:
                        if any(k in c.lower() for k in ["clause", "label", "span", "category", "target"]):
                            st["clause_columns"].add(c)
                elif ext == ".json":
                    with open(f, encoding="utf-8", errors="replace") as jf:
                        jdata = json.load(jf)
                    if isinstance(jdata, list) and jdata and isinstance(jdata[0], dict):
                        for k in jdata[0].keys():
                            if any(w in k.lower() for w in ["clause", "label", "span", "category"]):
                                st["clause_columns"].add(k)
            except Exception:
                pass

        # Collect text samples
        if text and len(text.strip()) > 30 and len(lang_samples[dominant_lang]) < 10:
            snippet = text.strip()[:300].replace("\n", " ")
            snippet_masked = mask_pii(snippet)
            lang_samples[dominant_lang].append(snippet_masked)

    # Summarize per language
    summary_report: dict[str, Any] = {
        "total_files": len(all_files),
        "total_size_mb": round(total_size_mb, 2),
        "top_10_largest_files": top_10_largest,
        "languages": {}
    }

    for lang, st in lang_stats.items():
        fc = st["file_count"]
        scanned_pct = round((st["scanned_count"] / fc) * 100, 2) if fc else 0.0
        garbled_pct = round((st["garbled_count"] / fc) * 100, 2) if fc else 0.0
        avg_len = round(st["total_chars"] / fc, 0) if fc else 0

        # Select 5 random samples
        avail_samples = lang_samples.get(lang, [])
        selected_samples = random.sample(avail_samples, min(5, len(avail_samples))) if avail_samples else []

        summary_report["languages"][lang] = {
            "file_count": fc,
            "file_types": st["file_types"],
            "pct_scanned_no_text": scanned_pct,
            "pct_garbled_non_unicode": garbled_pct,
            "average_length_chars": avg_len,
            "document_types": st["document_types"],
            "clause_level_labels_present": bool(st["clause_columns"]),
            "clause_columns": sorted(list(st["clause_columns"])),
            "source_and_licence": {
                "sources": sorted(list(st["sources_found"])),
                "licences": sorted(list(st["licences_found"])),
            },
            "samples_first_300_chars_pii_masked": selected_samples
        }

    return summary_report


def main():
    parser = argparse.ArgumentParser(description="Multilingual Data Audit for ClauseWise")
    parser.add_argument("--data-path", type=str, default=os.environ.get("MULTILINGUAL_DATA_PATH", ""), help="Path to multilingual contracts data or archive")
    parser.add_argument("--unpack-dir", type=str, default="ml/multilingual/data/unpacked", help="Directory to unpack archive into")
    args = parser.parse_args()

    if not args.data_path:
        print("\nERROR: No data path provided.")
        print("Usage: python ml/multilingual/audit_data.py --data-path <PATH_TO_DATA>")
        sys.exit(1)

    target_path = Path(args.data_path).resolve()
    unpack_dir = Path(args.unpack_dir).resolve()

    resolved_path = unpack_archive_if_needed(target_path, unpack_dir)
    report = audit_multilingual_dataset(resolved_path)

    print("\n" + "=" * 80)
    print("MULTILINGUAL CONTRACT DATA AUDIT REPORT")
    print("=" * 80)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
