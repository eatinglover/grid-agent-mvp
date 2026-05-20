from typing import Dict, Any, List
import copy


def calculate_voltage_delta(actions: List[Dict[str, Any]]) -> float:
    """
    根据治理动作计算电压修正量。
    正数表示电压升高，负数表示电压降低。
    """

    total_delta = 0.0

    for action in actions:
        device_type = action.get("device_type")
        action_type = action.get("action")

        if device_type in ["AVR", "OLTC"]:
            total_delta += action.get("expected_voltage_change_pu", 0.0)

        elif device_type == "SVG":
            value = action.get("value", 0)
            total_delta += -0.00005 * abs(value) if value < 0 else 0.00005 * abs(value)

        elif device_type == "ESS":
            value = action.get("value", 0)
            total_delta += -0.00003 * value if action_type == "charge" else 0.00003 * value

        elif device_type == "PV_INVERTER_CLUSTER":
            value = action.get("value", 0)
            if action_type == "inverter_absorb_reactive_power":
                total_delta += -0.00004 * abs(value)
            elif action_type == "active_power_curtailment":
                total_delta += -0.00008 * abs(value)

    return round(total_delta, 4)


def apply_voltage_feedback(
    next_case: Dict[str, Any],
    previous_actions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    将上一时刻治理动作反馈到下一时刻电压。
    """

    updated_case = copy.deepcopy(next_case)

    if not previous_actions:
        return updated_case

    delta = calculate_voltage_delta(previous_actions)

    voltage = updated_case.get("voltage", {})

    if "max_pu" in voltage:
        voltage["max_pu"] = round(voltage["max_pu"] + delta, 4)

    if "min_pu" in voltage:
        voltage["min_pu"] = round(voltage["min_pu"] + delta, 4)

    updated_case["voltage_feedback"] = {
        "applied": True,
        "delta_pu": delta,
        "reason": "上一时刻治理动作对当前电压产生反馈修正"
    }

    return updated_case