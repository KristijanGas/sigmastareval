from pathlib import Path
import subprocess
import sys
import time


bot_path = sys.argv[1]
dataset_paths = sys.argv[2:]

processes = []
files = []
for dataset in dataset_paths:
    for data_file in Path(dataset).glob("*.gz"):
        print(f"Found data file: {data_file}")
        file = data_file.resolve()
        files.append(file)



try:
    for data_file in files:
        print(f"Starting evaluation for {data_file}...")
        process = subprocess.Popen([sys.executable, "evaluator/replay_engine.py", bot_path, str(data_file)])
        processes.append(process)
    for process in processes:
        process.wait()
except KeyboardInterrupt:
    print("Terminating all evaluator processes...")
    for process in processes:
        process.terminate()
    for process in processes:
        process.wait()
    print("All evaluator processes terminated.")

    