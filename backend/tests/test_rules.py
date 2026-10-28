"""Unit tests for rule-based heuristics:
1. Carve-out detection -> Uncapped Liability
2. Change of control in assignment -> Change of Control
3. Invariance for unrelated clauses (zero false positives on clean text)
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from app.services.classifier import LIABILITY_GUARD_PATTERN, apply_liability_guard
from ml.src.audit_advanced_eval import apply_rules, CARVEOUT_PATTERN, COC_IN_ASSIGN_PATTERN


def test_doc01_section8_liability_guard():
    """DOC-01 section 8 explicitly waives caps ('shall not be subject to any limit or cap') -> Uncapped Liability."""
    text = (
        "8. Liability. Contractor shall be liable for, and shall indemnify Client against, all losses, damages, costs and "
        "expenses of any kind arising out of the Services, and Contractor's liability under this Agreement shall not be subject "
        "to any limit or cap."
    )
    assert LIABILITY_GUARD_PATTERN.search(text) is not None
    result = apply_liability_guard("Cap on Liability", text)
    assert result == "Uncapped Liability"


def test_normal_cap_stays_cap_on_liability():
    """Standard liability cap without carveout ('shall not exceed the fees paid') remains Cap on Liability."""
    normal_cap = "Contractor's total liability under this Agreement shall not exceed the fees paid by Client in the preceding twelve (12) months."
    assert LIABILITY_GUARD_PATTERN.search(normal_cap) is None
    result = apply_liability_guard("Cap on Liability", normal_cap)
    assert result == "Cap on Liability"

    normal_cap_2 = "In no event shall either party's aggregate liability exceed the total amounts paid hereunder."
    assert LIABILITY_GUARD_PATTERN.search(normal_cap_2) is None
    assert apply_liability_guard("Cap on Liability", normal_cap_2) == "Cap on Liability"


def test_carveout_rule_triggers():
    """Carve-outs inside limitation of liability clauses should override to Uncapped Liability."""
    text = (
        "12. Limitation of Liability. EXCEPT WITH RESPECT TO INDEMNIFICATION OBLIGATIONS, "
        "in no event shall either party be liable for consequential, incidental, or special damages."
    )
    assert CARVEOUT_PATTERN.search(text) is not None
    # When initial prediction was Cap on Liability, rule overrides to Uncapped Liability
    result = apply_rules("Cap on Liability", text)
    assert result == "Uncapped Liability"


def test_carveout_rule_express_waiver():
    """Express waivers of liability caps trigger Uncapped Liability."""
    text = "Buyer expressly waives any and all limitations or liability caps on Buyer's liability to Seller."
    assert CARVEOUT_PATTERN.search(text) is not None
    assert apply_rules("Cap on Liability", text) == "Uncapped Liability"


def test_change_of_control_in_assignment_triggers():
    """Change-of-control language embedded in assignment clauses overrides Anti-Assignment."""
    text = (
        "15.8 Assignment. Neither party shall assign this Agreement without consent; "
        "provided that either party may assign in connection with a merger, consolidation or change of control."
    )
    assert COC_IN_ASSIGN_PATTERN.search(text) is not None
    result = apply_rules("Anti-Assignment", text)
    assert result == "Change of Control"


def test_clean_assignment_does_not_trigger():
    """Clean Anti-Assignment clause without change-of-control wording remains Anti-Assignment."""
    clean_assignment = (
        "15.8 Assignment. Neither party may assign, delegate, or transfer its rights "
        "under this Agreement without the prior written consent of the other party."
    )
    assert COC_IN_ASSIGN_PATTERN.search(clean_assignment) is None
    result = apply_rules("Anti-Assignment", clean_assignment)
    assert result == "Anti-Assignment"


def test_clean_cap_on_liability_does_not_trigger():
    """Clean Cap on Liability without carve-outs remains Cap on Liability."""
    clean_cap = (
        "10. Limitation of Liability. In no event shall either party's aggregate liability "
        "exceed the total fees paid by customer under this agreement in the twelve months preceding the claim."
    )
    assert CARVEOUT_PATTERN.search(clean_cap) is None
    result = apply_rules("Cap on Liability", clean_cap)
    assert result == "Cap on Liability"


def test_unrelated_clauses_untouched():
    """Rules never mutate unrelated predictions like Non-Compete or Audit Rights."""
    non_compete_text = "Employee shall not directly or indirectly compete with the Company for two years."
    assert apply_rules("Non-Compete", non_compete_text) == "Non-Compete"

    audit_text = "Customer shall have the right to inspect and audit books and records annually."
    assert apply_rules("Audit Rights", audit_text) == "Audit Rights"
