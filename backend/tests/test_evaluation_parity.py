"""Parity test: Assert backend classifier flags and labels exactly match evaluation script on validation contracts."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from app.services.classifier import classifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VAL_NATURAL_PATH = PROJECT_ROOT / "ml" / "data" / "processed" / "val_natural.csv"
VAL_PROBS_PATH = PROJECT_ROOT / "ml" / "artifacts" / "legal_bert_val_natural_probs.npy"
OP_POINTS_PATH = PROJECT_ROOT / "ml" / "artifacts" / "operating_points.json"
LABEL_MAP_PATH = PROJECT_ROOT / "ml" / "artifacts" / "label_map.json"
MODEL_PATH = PROJECT_ROOT / "ml" / "artifacts" / "legal_bert_final"


@pytest.fixture(scope="module")
def loaded_classifier():
    if not MODEL_PATH.exists() or not VAL_PROBS_PATH.exists():
        pytest.skip("Required model or evaluation artifacts not found.")
    classifier.load(
        model_path=str(MODEL_PATH),
        label_map_path=str(LABEL_MAP_PATH),
        operating_points_path=str(OP_POINTS_PATH),
    )
    return classifier


def test_validation_contract_evaluation_parity(loaded_classifier):
    """Test that backend inference matches frozen evaluation outputs 100% on a validation contract."""
    if not VAL_NATURAL_PATH.exists() or not VAL_PROBS_PATH.exists():
        pytest.skip("val_natural.csv or legal_bert_val_natural_probs.npy not found.")

    val_nat = pd.read_csv(VAL_NATURAL_PATH)
    probs_saved = np.load(VAL_PROBS_PATH)

    with open(OP_POINTS_PATH) as f:
        op_data = json.load(f)
    with open(LABEL_MAP_PATH) as f:
        lm_data = json.load(f)

    id2label = {int(k): v for k, v in lm_data["id2label"].items()}
    no_clause_idx = lm_data["label2id"]["No Clause"]
    sub_indices = [i for i in range(len(id2label)) if i != no_clause_idx]
    sub_names = [id2label[i] for i in sub_indices]

    # Select the first validation contract
    first_contract = val_nat["contract"].iloc[0]
    mask = (val_nat["contract"] == first_contract).to_numpy()
    contract_units = val_nat[mask]
    contract_probs = probs_saved[mask]
    texts = contract_units["text"].tolist()

    for preset_name in ["strict", "balanced", "thorough"]:
        tau = op_data["presets"][preset_name]["tau"]

        # 1. Evaluation script ground truth
        eval_flagged = (contract_probs[:, no_clause_idx] < tau)
        eval_labels = []
        for fl, row in zip(eval_flagged, contract_probs):
            if fl:
                sub_p = row[sub_indices]
                eval_labels.append(sub_names[int(sub_p.argmax())])
            else:
                eval_labels.append("No Clause")

        # 2. Backend classifier prediction
        backend_preds = loaded_classifier.predict(texts, sensitivity=preset_name)
        backend_flagged = np.array([p["flagged"] for p in backend_preds])
        backend_labels = [p["label"] for p in backend_preds]

        # 3. Assert 100% parity
        assert (eval_flagged == backend_flagged).all(), (
            f"Flag mismatch in contract {first_contract} at preset {preset_name}: "
            f"eval={eval_flagged.sum()} vs backend={backend_flagged.sum()}"
        )
        assert eval_labels == backend_labels, (
            f"Label mismatch in contract {first_contract} at preset {preset_name}."
        )
