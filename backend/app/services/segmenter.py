"""Segment contract text into clause-sized chunks.

Provides slice-based resegmentation for training and production inference,
guaranteeing exact character offset matches with context text.
"""
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

MIN_CHUNK_LEN = 50
MAX_CHUNK_LEN = 2000

# Lazy global tokenizer cache
_TOKENIZER: Any = None


def get_default_tokenizer() -> Any:
    """Return cached legal-bert tokenizer or fallback whitespace tokenizer."""
    global _TOKENIZER
    if _TOKENIZER is None:
        try:
            from transformers import AutoTokenizer
            _TOKENIZER = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
        except Exception:
            _TOKENIZER = None
    return _TOKENIZER


def strip_headers_footers_offset_preserving(text: str) -> str:
    """Strip repeated page headers and footers while preserving exact character offsets.
    
    Replaces matched header/footer lines with spaces instead of deleting them.
    """
    lines = text.split("\n")
    new_chars = list(text)
    
    header_footer_patterns = [
        re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*-\s*\d+\s*-\s*$"),
        re.compile(r"^\s*\[\s*\d+\s*\]\s*$"),
        re.compile(r"^\s*confidential\s*$", re.IGNORECASE),
        re.compile(r"^\s*execution\s+copy\s*$", re.IGNORECASE),
        re.compile(r"^\s*exhibit\s+\d+(\.\d+)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*table\s+of\s+contents\s*$", re.IGNORECASE),
    ]
    
    curr_pos = 0
    for line in lines:
        line_len = len(line)
        is_hf = False
        for pat in header_footer_patterns:
            if pat.match(line):
                is_hf = True
                break
        if is_hf:
            for i in range(curr_pos, curr_pos + line_len):
                if new_chars[i] != "\n":
                    new_chars[i] = " "
        curr_pos += line_len + 1
    return "".join(new_chars)


def is_placeholder_or_table(text: str) -> bool:
    """Drop units that are mostly placeholders ([], [***], {}), table fragments, or TOC/dot-leader lines."""
    clean = text.strip()
    if len(clean) < 25:
        return True
    
    # Drop Table of Contents and dot-leader lines
    if re.search(r"(\.{4,}\s*\d+)|(\.\s*\.\s*\.\s*\.\s*\.\s*\d+)|(\.{6,})|^\s*TABLE OF CONTENTS", clean, re.IGNORECASE | re.MULTILINE):
        return True

    # Redaction / placeholder check: chars like *, _, -, [, ], {, }, #, =, |
    placeholder_chars = sum(1 for c in clean if c in "*_-[]{}#=|")
    non_ws = sum(1 for c in clean if not c.isspace())
    if non_ws > 0 and (placeholder_chars / non_ws) >= 0.30:
        return True
    
    words = clean.split()
    if not words:
        return True
    alpha_words = [w for w in words if any(c.isalpha() for c in w)]
    if len(alpha_words) / len(words) < 0.45 and len(words) > 6:
        return True
        
    redacted_count = len(re.findall(r"\[\*+\]|\{\*+\}", clean))
    if redacted_count >= 3 and redacted_count / len(words) >= 0.25:
        return True
        
    return False


def resegment_contract(
    text: str,
    tokenizer: Any = None,
    max_tokens: int = 256,
) -> list[dict[str, Any]]:
    """Segment contract into numbered paragraphs as units (<= 256 tokens).
    Section numbers (11.6, ARTICLE 10, 10.1) start a new unit.
    Longer paragraphs are split at sentence boundaries using direct slice bounds.
    
    Returns list of dicts:
        {
            "text_raw": exact verbatim slice clean_text[char_start:char_end],
            "text": whitespace-normalized text for models,
            "char_start": start character index in raw/clean context,
            "char_end": end character index in raw/clean context,
        }
    """
    if not text or not text.strip():
        return []
        
    if tokenizer is None:
        tokenizer = get_default_tokenizer()

    def count_tokens(s: str) -> int:
        if tokenizer is not None:
            return len(tokenizer(s, truncation=False, add_special_tokens=False)["input_ids"])
        return int(len(s.split()) * 1.3)

    clean_text = strip_headers_footers_offset_preserving(text)
    
    # Split regex on section numbers or paragraph breaks
    sec_regex = re.compile(
        r'(?:\n\s*\n|\n\s*(?=(?:ARTICLE|Article|SECTION|Section|[0-9]{1,3}\.[0-9]{1,3}|\b[0-9]{1,3}\.\s+|\([a-z0-9]+\)\s+))|(?<=[.!?])\s+(?=(?:ARTICLE|Article|SECTION|Section)\s+[A-Za-z0-9]+|[0-9]{1,3}\.[0-9]{1,3}(?:\.[0-9]{1,3})*|\b[0-9]{1,3}\.\s+))',
        re.MULTILINE,
    )
    
    split_indices = [0]
    for m in sec_regex.finditer(clean_text):
        split_indices.append(m.start())
        split_indices.append(m.end())
    split_indices.append(len(clean_text))
    
    raw_paras: list[tuple[int, int]] = []
    for i in range(0, len(split_indices) - 1, 2):
        s, e = split_indices[i], split_indices[i + 1]
        raw_slice = clean_text[s:e]
        m_strip = re.search(r'\S.*\S', raw_slice, re.DOTALL)
        if m_strip:
            raw_paras.append((s + m_strip.start(), s + m_strip.end()))
        elif raw_slice.strip():
            pos = s + re.search(r'\S', raw_slice).start()
            raw_paras.append((pos, pos + 1))
            
    final_units: list[dict[str, Any]] = []
    
    for p_s, p_e in raw_paras:
        para_raw = clean_text[p_s:p_e]
        para_norm = " ".join(para_raw.split())
        tok_len = count_tokens(para_norm)
        
        if tok_len <= max_tokens:
            if not is_placeholder_or_table(para_raw):
                final_units.append({
                    "text_raw": para_raw,
                    "text": para_norm,
                    "char_start": p_s,
                    "char_end": p_e,
                })
        else:
            boundary_regex = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'\(\[])')
            split_pos = [0]
            for m in boundary_regex.finditer(para_raw):
                split_pos.append(m.start())
                split_pos.append(m.end())
            split_pos.append(len(para_raw))
            
            sents: list[tuple[int, int]] = []
            for i in range(0, len(split_pos), 2):
                rel_s = split_pos[i]
                rel_e = split_pos[i+1] if i+1 < len(split_pos) else len(para_raw)
                s_raw = para_raw[rel_s:rel_e]
                m_s = re.search(r'\S.*\S', s_raw, re.DOTALL)
                if m_s:
                    sents.append((p_s + rel_s + m_s.start(), p_s + rel_s + m_s.end()))
                elif s_raw.strip():
                    pos = p_s + rel_s + re.search(r'\S', s_raw).start()
                    sents.append((pos, pos + 1))
                    
            curr_sents: list[tuple[int, int]] = []
            for s_start, s_end in sents:
                cand_sents = curr_sents + [(s_start, s_end)]
                cand_raw = clean_text[cand_sents[0][0] : cand_sents[-1][1]]
                cand_norm = " ".join(cand_raw.split())
                cand_len = count_tokens(cand_norm)
                
                if cand_len <= max_tokens:
                    curr_sents = cand_sents
                else:
                    if curr_sents:
                        u_s = curr_sents[0][0]
                        u_e = curr_sents[-1][1]
                        u_raw = clean_text[u_s:u_e]
                        u_norm = " ".join(u_raw.split())
                        if not is_placeholder_or_table(u_raw):
                            final_units.append({
                                "text_raw": u_raw,
                                "text": u_norm,
                                "char_start": u_s,
                                "char_end": u_e,
                            })
                        curr_sents = []
                        
                    single_raw = clean_text[s_start:s_end]
                    single_norm = " ".join(single_raw.split())
                    s_len = count_tokens(single_norm)
                    
                    if s_len > max_tokens:
                        word_matches = list(re.finditer(r'\S+', single_raw))
                        w_start_idx = 0
                        while w_start_idx < len(word_matches):
                            w_end_idx = w_start_idx
                            while w_end_idx < len(word_matches):
                                w_s = s_start + word_matches[w_start_idx].start()
                                w_e = s_start + word_matches[w_end_idx].end()
                                w_block_raw = clean_text[w_s:w_e]
                                w_block_norm = " ".join(w_block_raw.split())
                                w_tok_len = count_tokens(w_block_norm)
                                if w_tok_len >= max_tokens - 10:
                                    break
                                w_end_idx += 1
                                
                            if w_end_idx == w_start_idx:
                                w_end_idx += 1
                                
                            b_s = s_start + word_matches[w_start_idx].start()
                            b_e = s_start + word_matches[min(w_end_idx, len(word_matches) - 1)].end()
                            b_raw = clean_text[b_s:b_e]
                            b_norm = " ".join(b_raw.split())
                            if not is_placeholder_or_table(b_raw):
                                final_units.append({
                                    "text_raw": b_raw,
                                    "text": b_norm,
                                    "char_start": b_s,
                                    "char_end": b_e,
                                })
                            w_start_idx = w_end_idx + 1
                        curr_sents = []
                    else:
                        curr_sents = [(s_start, s_end)]
                        
            if curr_sents:
                u_s = curr_sents[0][0]
                u_e = curr_sents[-1][1]
                u_raw = clean_text[u_s:u_e]
                u_norm = " ".join(u_raw.split())
                if not is_placeholder_or_table(u_raw):
                    final_units.append({
                        "text_raw": u_raw,
                        "text": u_norm,
                        "char_start": u_s,
                        "char_end": u_e,
                    })
                    
    return final_units


def segment_text(
    text: str,
    min_len: int = MIN_CHUNK_LEN,
    max_len: int = MAX_CHUNK_LEN,
) -> list[str]:
    """Split contract text into clause-sized chunks for inference.
    
    Uses resegment_contract with backwards-compatible min_len / max_len merging.
    """
    if not text or not text.strip():
        return []
        
    units = resegment_contract(text)
    if units:
        raw_chunks = [u["text"] for u in units]
    else:
        # Fallback for plain unpunctuated snippets
        raw_chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
        
    # Merge tiny chunks (< min_len)
    merged: list[str] = []
    buffer = ""
    for chunk in raw_chunks:
        if len(buffer) + len(chunk) < min_len:
            buffer = (buffer + " " + chunk).strip()
        else:
            if buffer:
                merged.append(buffer)
            buffer = chunk
    if buffer:
        merged.append(buffer)
        
    # Split huge chunks (> max_len)
    final: list[str] = []
    for chunk in merged:
        if len(chunk) <= max_len:
            final.append(chunk)
        else:
            sentences = re.split(r'(?<=[.!?])\s+', chunk)
            sub_buf = ""
            for sent in sentences:
                if len(sub_buf) + len(sent) > max_len and sub_buf:
                    final.append(sub_buf.strip())
                    sub_buf = sent
                else:
                    sub_buf = (sub_buf + " " + sent).strip()
            if sub_buf:
                final.append(sub_buf.strip())
                
    result = [c for c in final if len(c) >= 20]
    logger.info("Segmented text into %d chunks (from %d chars)", len(result), len(text))
    return result
