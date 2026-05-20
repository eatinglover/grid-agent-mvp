from src.utils import read_json, write_json
from src.agent import VoltageGovernanceAgent
from src.decision_reporter import build_decision_report


def main():

    cases = read_json("data/sample_cases_from_real_library.json")

    case_library = read_json("data/real_case_library.json")

    capability_library = read_json("data/device_capability_library.json")

    agent = VoltageGovernanceAgent(case_library, capability_library)

    results = []

    for case in cases:

        print("=" * 80)
        print(f"正在处理案例：{case['case_id']} - {case['area_name']}")

        result = agent.run(case)

        report = build_decision_report(result)

        result["case_id"] = case["case_id"]
        result["area_id"] = case["area_id"]
        result["area_name"] = case["area_name"]
        result["decision_report"] = report

        results.append(result)

        print(report)

    write_json("output/agent_results.json", results)

    print("=" * 80)

    print("Agent运行完成，结果已保存到 output/agent_results.json")


if __name__ == "__main__":
    main()