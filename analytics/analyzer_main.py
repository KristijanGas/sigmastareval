import sys
from pathlib import Path
from analytics.aggregate_analyzer import AggregateAnalyzer
from analytics.performance_analyzer import PerformanceAnalyzer

aggregate_analyzer = AggregateAnalyzer()

analytics_directory_path = sys.argv[1]

# run example: python -m analytics.main tmp/bitcoin-up-or-down/
for data_file in Path(analytics_directory_path).glob("*.json"):
    #print(f"Found data file: {data_file}")
    performance_analyzer = PerformanceAnalyzer(100)
    performance_analyzer.analytics_path = data_file
    result = performance_analyzer.analyze()
    aggregate_analyzer.add_result(result)

aggregate_analyzer.analyze()
