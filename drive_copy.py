# -*- coding: utf-8 -*-
"""Copy prepared datasets and output artifacts to the destination backup directory."""

import os
import shutil
from config import DATA_PATH, OUTPUT_DIR, SHARED_DRIVE_DIR

def copy_artifacts_to_shared_drive():
    print(f"Target destination folder: {SHARED_DRIVE_DIR}")
    print("Local CSV exists:", os.path.exists(DATA_PATH))
    print("Local outputs exist:", os.path.exists(OUTPUT_DIR))

    if os.path.exists(DATA_PATH):
        shutil.copy2(DATA_PATH, SHARED_DRIVE_DIR)
        print("Copied m100_node1_digital_twin.csv to target drive!")

    if os.path.exists(OUTPUT_DIR):
        dest_outputs = SHARED_DRIVE_DIR / "member1_outputs"
        if os.path.exists(dest_outputs):
            shutil.rmtree(dest_outputs)
        shutil.copytree(OUTPUT_DIR, dest_outputs)
        print("Copied member1_outputs directory to target drive!")

    print("\nFiles now inside target drive folder:")
    for item in os.listdir(SHARED_DRIVE_DIR):
        print(" -", item)

if __name__ == "__main__":
    copy_artifacts_to_shared_drive()