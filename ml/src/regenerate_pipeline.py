"""Master pipeline script to regenerate datasets and out-of-fold harmless units ranking
using the slice-based segmentation with >=20 char annotation threshold and dot-leader dropping.
"""
import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from transformers import AutoTokenizer

from ml.src.resegment_and_audit import (
    RAW_PATH,
    PROCESSED_DIR,
    ARTIFACTS_DIR,
    BASELINE_PATH,
    SEED,
    process_all_contracts,
    create_dataset_splits,
)
from ml.src.oof_hard_negatives import run_oof_scoring

def main():
    print("=" * 80)
    print("REGENERATING DATASETS WITH SLICE-BASED FIX (>=20 CHAR ANNOTATIONS)")
    print("=" * 80)
    
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        cuad_data = json.load(f)["data"]
        
    tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
    
    # 1. Process all 510 contracts
    all_records = process_all_contracts(cuad_data, tokenizer)
    
    # 2. Create dataset splits
    df_train, df_val, df_test, df_val_nat, df_test_nat = create_dataset_splits(
        all_records,
        baseline_model_path=BASELINE_PATH,
        downsample_ratio=3.0,
    )
    
    print("\nDataset generation complete!")
    print(f"train.csv:        {len(df_train)} rows")
    print(f"val.csv:          {len(df_val)} rows")
    print(f"test.csv:         {len(df_test)} rows")
    print(f"train_natural.csv:{len(pd.read_csv(PROCESSED_DIR / 'train_natural.csv'))} rows")
    print(f"val_natural.csv:  {len(df_val_nat)} rows")
    print(f"test_natural.csv: {len(df_test_nat)} rows")
    
    # 3. Regenerate oof_ranked_harmless_units.csv
    print("\n" + "=" * 80)
    print("REGENERATING OOF RANKED HARMLESS UNITS (5-FOLD CV)")
    print("=" * 80)
    df_ranked = run_oof_scoring()
    print(f"OOF ranked harmless units complete: {len(df_ranked)} rows saved to ml/artifacts/oof_ranked_harmless_units.csv")

if __name__ == "__main__":
    main()
