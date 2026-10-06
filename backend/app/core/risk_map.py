"""Risk mapping: clause type -> risk level.

This is a HEURISTIC table, not legal advice.
Single source of truth for risk classification.
"""
from typing import Optional

RISK_MAP: dict[str, str] = {
    "Non-Compete": "High",
    "Exclusivity": "High",
    "Uncapped Liability": "High",
    "Liquidated Damages": "High",
    "Termination for Convenience": "Medium",
    "Anti-Assignment": "Medium",
    "Change of Control": "Medium",
    "IP Ownership Assignment": "Medium",
    "Cap on Liability": "Low",
    "Audit Rights": "Low",
}

ALL_CLAUSE_TYPES: list[str] = list(RISK_MAP.keys()) + ["No Clause"]
NUM_LABELS: int = len(ALL_CLAUSE_TYPES)


def get_risk_level(clause_type: str) -> Optional[str]:
    """Return risk level for a clause type.
    
    Args:
        clause_type: One of the known clause type strings.
        
    Returns:
        'High', 'Medium', 'Low', or None for 'No Clause'.
    """
    if clause_type == "No Clause":
        return None
    return RISK_MAP.get(clause_type)


def get_overall_risk(clause_risks: list[Optional[str]]) -> str:
    """Compute overall document risk from clause-level risks.
    
    Returns the highest risk level found, or 'Low' if no risky clauses.
    """
    priority = {"High": 3, "Medium": 2, "Low": 1}
    max_risk = 0
    for risk in clause_risks:
        if risk and risk in priority:
            max_risk = max(max_risk, priority[risk])
    reverse = {3: "High", 2: "Medium", 1: "Low", 0: "Low"}
    return reverse[max_risk]


if __name__ == "__main__":
    for ct in ALL_CLAUSE_TYPES:
        print(f"{ct:35s} -> {get_risk_level(ct)}")
