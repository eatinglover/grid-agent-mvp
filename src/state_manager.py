from typing import Dict, Any, List


def update_device_state(
    case: Dict[str, Any],
    checked_actions: List[Dict[str, Any]]
) -> Dict[str, Any]:

    """
    根据本次治理动作更新设备状态。
    """

    device_map = {
        d["device_id"]: d
        for d in case.get("devices", [])
    }

    for action in checked_actions:

        device_id = action.get("device_id")

        if device_id not in device_map:
            continue

        dev = device_map[device_id]

        # =====================================================
        # AVR / OLTC 档位更新
        # =====================================================

        if action.get("device_type") in ["AVR", "OLTC"]:

            if "after_tap" in action:

                dev["current_tap"] = action["after_tap"]

        # =====================================================
        # ESS SOC更新（简单模拟）
        # =====================================================

        if action.get("device_type") == "ESS":

            soc = dev.get("soc", 0.5)

            if action.get("action") == "charge":
                soc += 0.05

            elif action.get("action") == "discharge":
                soc -= 0.05

            soc = max(0.0, min(1.0, soc))

            dev["soc"] = round(soc, 3)

    return case


def inherit_previous_device_state(
    current_case: Dict[str, Any],
    previous_case: Dict[str, Any] | None
) -> Dict[str, Any]:

    """
    继承上一时刻设备状态。
    """

    if previous_case is None:
        return current_case

    previous_device_map = {
        d["device_id"]: d
        for d in previous_case.get("devices", [])
    }

    for dev in current_case.get("devices", []):

        device_id = dev.get("device_id")

        if device_id not in previous_device_map:
            continue

        prev_dev = previous_device_map[device_id]

        # =====================================================
        # 继承档位
        # =====================================================

        if "current_tap" in prev_dev:
            dev["current_tap"] = prev_dev["current_tap"]

        # =====================================================
        # 继承SOC
        # =====================================================

        if "soc" in prev_dev:
            dev["soc"] = prev_dev["soc"]

    return current_case