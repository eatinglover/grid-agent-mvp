import time

from src.utils import read_json, write_json
from src.agent import VoltageGovernanceAgent
from src.decision_reporter import build_decision_report
from src.state_manager import update_device_state, inherit_previous_device_state
from src.voltage_feedback import apply_voltage_feedback


def main():
    cases = read_json("data/realtime_stream/mfc_voltage_stream.json")

    case_library = read_json("data/real_case_library.json")

    capability_library = read_json("data/device_capability_library.json")

    agent = VoltageGovernanceAgent(case_library, capability_library)

    results = []

    previous_case = None
    previous_actions = []

    print("=" * 80)
    print("实时电压治理闭环模拟开始")
    print("=" * 80)

    for case in cases:
        # 继承上一时刻设备状态
        case = inherit_previous_device_state(case, previous_case)

        # 将上一时刻治理动作反馈到当前电压
        case = apply_voltage_feedback(case, previous_actions)

        print("\n" + "=" * 80)
        print(f"实时采样时间：{case['timestamp']}")
        print(f"台区：{case['area_name']}")

        if case.get("voltage_feedback", {}).get("applied"):
            fb = case["voltage_feedback"]
            print(f"上一时刻治理反馈：{fb['delta_pu']} pu，说明：{fb['reason']}")

        print(f"最大电压：{case['voltage']['max_pu']} pu")
        print(f"最小电压：{case['voltage']['min_pu']} pu")
        print(f"光伏出力：{case.get('pv_power_kw', 0)} kW")
        print(f"负荷功率：{case.get('load_power_kw', 0)} kW")

        for dev in case.get("devices", []):
            if "current_tap" in dev:
                print(f"设备 {dev['device_id']} 当前档位：{dev['current_tap']}")
            if "soc" in dev:
                print(f"设备 {dev['device_id']} 当前SOC：{dev['soc']}")

        print("-" * 80)

        result = agent.run(case)

        report = build_decision_report(result)

        result["case_id"] = case["case_id"]
        result["area_id"] = case["area_id"]
        result["area_name"] = case["area_name"]
        result["timestamp"] = case["timestamp"]
        result["voltage_feedback"] = case.get("voltage_feedback", {})
        result["decision_report"] = report

        results.append(result)

        print(report)

        # 根据本次治理动作更新设备状态
        case = update_device_state(
            case,
            result.get("checked_actions", [])
        )

        previous_case = case
        previous_actions = result.get("checked_actions", [])

        time.sleep(1)

    write_json("output/realtime_agent_results.json", results)

    print("=" * 80)
    print("实时电压治理闭环模拟完成，结果已保存到 output/realtime_agent_results.json")


if __name__ == "__main__":
    main()