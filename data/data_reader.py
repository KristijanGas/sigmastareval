import argparse
import gzip
import json
from pathlib import Path


def load_gzipped_json(input_path: Path) -> object:
	with gzip.open(input_path, "rt", encoding="utf-8") as handle:
		return json.load(handle)


def main() -> None:
	parser = argparse.ArgumentParser(
		description="Load a gzipped JSON file and write it to temp.json in the repo root."
	)
	parser.add_argument("input_path", help="Path to the .gz file to load")
	parser.add_argument(
		"--output",
		default=None,
		help="Optional output path. Defaults to <repo-root>/temp.json",
	)
	args = parser.parse_args()

	repo_root = Path(__file__).resolve().parents[1]
	output_path = Path(args.output) if args.output else repo_root / "temp.json"
	data = load_gzipped_json(Path(args.input_path))

	output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
	print(f"Wrote {output_path}")


if __name__ == "__main__":
	main()
