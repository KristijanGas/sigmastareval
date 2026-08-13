from pathlib import Path
import random
import subprocess
import sys
import time
import utils.utils as utils

bot_path = sys.argv[1]
dataset_paths = sys.argv[2:]

processes = []
files = []
for dataset in dataset_paths:
    for data_file in Path(dataset).glob("*.gz"):
        print(f"Found data file: {data_file}")
        file = data_file.resolve()
        newer_than_time = "august-3-2026-12pm-et"
        #newer_than_time = None
        #file_creation_date = data_file.stat().st_ctime
        #if newer_than_time is not None and file_creation_date < time.time() - newer_than_time:
        if not utils.is_newer_than(file, newer_than_time):
            #print(f"  Skipping {gz_file} (too old)")
            continue
        files.append(file)

process_count = 6
partition_size = len(files) // process_count
partition_remainder_size = len(files) - partition_size * process_count
file_partitions = []
added_extra = 0
random.shuffle(files)  # Shuffle the files to ensure a more even distribution of workload across processes
for i in range(0,process_count):
    add_list = []
    for j in range(partition_size):
        offset = i * partition_size + j + added_extra
        add_list.append(files[offset])
    if added_extra < partition_remainder_size:
        add_list.append(files[(i+1) * partition_size + added_extra])
        added_extra+=1
    file_partitions.append(add_list)

try:
    for file_sublist in file_partitions:
        print(f"Starting evaluation...")
        process = subprocess.Popen([sys.executable, "evaluator/replay_engine.py", bot_path, *file_sublist])
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
