from typing import Dict, Any, List


def diagnose_voltage(case: Dict[str, Any]) -> Dict[str, Any]:
    voltage = case["voltage"]

    max_pu = voltage["max_pu"]
    min_pu = voltage["min_pu"]

    upper = voltage["upper_limit_pu"]
    lower = voltage["lower_limit_pu"]

    over_exist = max_pu > upper
    under_exist = min_pu < lower

    # 双向越限
    if over_exist and under_exist:

        over = max_pu - upper
        under = lower - min_pu

        severity = "light"

        if max(over, under) >= 0.03:
            severity = "serious"
        elif max(over, under) >= 0.015:
            severity = "medium"

        return {
            "status": "two_way_voltage_violation",
            "severity": severity,
            "over_exceed_pu": round(over, 4),
            "under_exceed_pu": round(under, 4),
            "description": (
                f"存在双向电压越限："
                f"最高电压 {max_pu} pu 超过上限 {upper} pu，"
                f"最低电压 {min_pu} pu 低于下限 {lower} pu"
            )
        }

    # 过电压
    if over_exist:

        over = max_pu - upper

        severity = "light"

        if over >= 0.03:
            severity = "serious"
        elif over >= 0.015:
            severity = "medium"

        return {
            "status": "over_voltage",
            "severity": severity,
            "exceed_value_pu": round(over, 4),
            "description": (
                f"最高电压 {max_pu} pu 超过上限 {upper} pu"
            )
        }

    # 欠电压
    if under_exist:

        under = lower - min_pu

        severity = "light"

        if under >= 0.03:
            severity = "serious"
        elif under >= 0.015:
            severity = "medium"

        return {
            "status": "under_voltage",
            "severity": severity,
            "exceed_value_pu": round(under, 4),
            "description": (
                f"最低电压 {min_pu} pu 低于下限 {lower} pu"
            )
        }

    return {
        "status": "normal",
        "severity": "none",
        "exceed_value_pu": 0,
        "description": "电压处于正常范围"
    }


def available_devices(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        d for d in case.get("devices", [])
        if d.get("status") == "online"
    ]


def generate_rule_based_strategy(case: Dict[str, Any]) -> Dict[str, Any]:

    diagnosis = diagnose_voltage(case)

    devices = available_devices(case)

    device_types = [d["device_type"] for d in devices]

    result = {
        "case_id": case["case_id"],
        "area_id": case["area_id"],
        "diagnosis": diagnosis,
        "candidate_actions": [],
        "rule_reason": ""
    }

    # 正常不治理
    if diagnosis["status"] == "normal":

        result["rule_reason"] = "电压正常，无需治理。"

        return result

    is_over = diagnosis["status"] == "over_voltage"

    is_under = diagnosis["status"] == "under_voltage"

    is_two_way = diagnosis["status"] == "two_way_voltage_violation"

    time_period = case.get("time_period", "day")

    # =========================================================
    # 过电压治理
    # =========================================================

    if is_over or (is_two_way and time_period == "day"):

        # SVG 无功吸收
        if "SVG" in device_types:

            svg = next(
                d for d in devices
                if d["device_type"] == "SVG"
            )

            exceed = diagnosis.get("exceed_value_pu", 0.02)

            q = min(
                svg["capacity_kvar"],
                max(50, int(exceed * 10000))
            )

            result["candidate_actions"].append({

                "priority": 1,

                "device_id": svg["device_id"],

                "device_type": "SVG",

                "action": "absorb_reactive_power",

                "value": -q,

                "unit": "kVar",

                "current_q_kvar": svg.get("current_q_kvar", 0),

                "target_q_kvar": -q,

                "expected_effect": {
                    "voltage_direction": "decrease",
                    "reason": (
                        f"SVG吸收无功 {q} kVar，"
                        f"预计可降低并网点电压。"
                    )
                },

                "reason": (
                    "过电压优先采用SVG吸收无功，"
                    "响应速度快。"
                )
            })

        # 光伏逆变器集群
        if "PV_INVERTER_CLUSTER" in device_types:

            inv = next(
                d for d in devices
                if d["device_type"] == "PV_INVERTER_CLUSTER"
            )

            q_capacity = inv.get("reactive_capacity_kvar", 0)

            curtail_max = inv.get(
                "active_curtailment_max_kw",
                0
            )

            exceed = diagnosis.get("exceed_value_pu", 0.02)

            # 无功控制
            if q_capacity > 0:

                q = min(
                    q_capacity,
                    max(20, int(exceed * 3000))
                )

                result["candidate_actions"].append({

                    "priority": 1,

                    "device_id": inv["device_id"],

                    "device_type": "PV_INVERTER_CLUSTER",

                    "action": "inverter_absorb_reactive_power",

                    "value": -q,

                    "unit": "kVar",

                    "target_q_kvar": -q,

                    "expected_effect": {
                        "voltage_direction": "decrease",
                        "reason": (
                            f"逆变器吸收无功 {q} kVar，"
                            f"降低光伏并网电压。"
                        )
                    },

                    "reason": (
                        "优先采用Q/V无功控制降低电压。"
                    )
                })

            # 有功削减
            if (
                curtail_max > 0
                and diagnosis["severity"] == "serious"
            ):

                p = min(
                    curtail_max,
                    max(
                        5,
                        int(case.get("pv_power_kw", 0) * 0.05)
                    )
                )

                result["candidate_actions"].append({

                    "priority": 4,

                    "device_id": inv["device_id"],

                    "device_type": "PV_INVERTER_CLUSTER",

                    "action": "active_power_curtailment",

                    "value": -p,

                    "unit": "kW",

                    "target_curtailment_kw": p,

                    "expected_effect": {
                        "voltage_direction": "decrease",
                        "reason": (
                            f"削减有功 {p} kW，"
                            f"进一步降低过电压。"
                        )
                    },

                    "reason": (
                        "无功能力不足时，"
                        "采用少量有功削减。"
                    )
                })

        # 储能充电
        if (
            "ESS" in device_types
            and case.get("pv_power_kw", 0)
            > case.get("load_power_kw", 0)
        ):

            ess = next(
                d for d in devices
                if d["device_type"] == "ESS"
            )

            if ess["soc"] < ess["soc_max"]:

                p = min(
                    ess["max_charge_kw"],
                    max(
                        20,
                        int(
                            (
                                case["pv_power_kw"]
                                - case["load_power_kw"]
                            ) * 0.3
                        )
                    )
                )

                result["candidate_actions"].append({

                    "priority": 2,

                    "device_id": ess["device_id"],

                    "device_type": "ESS",

                    "action": "charge",

                    "value": p,

                    "unit": "kW",

                    "current_soc": ess["soc"],

                    "target_charge_kw": p,

                    "expected_effect": {
                        "voltage_direction": "decrease",
                        "reason": (
                            f"储能充电 {p} kW，"
                            f"吸收光伏有功。"
                        )
                    },

                    "reason": (
                        "储能充电可吸收光伏有功，"
                        "降低过电压。"
                    )
                })

        # OLTC / AVR 降档
        for dtype in ["OLTC", "AVR"]:

            if dtype in device_types:

                dev = next(
                    d for d in devices
                    if d["device_type"] == dtype
                )

                current_tap = dev["current_tap"]

                tap_min = dev["tap_min"]

                tap_step_percent = dev.get(
                    "tap_step_percent",
                    1.25
                )

                if current_tap > tap_min:

                    exceed = diagnosis.get(
                        "exceed_value_pu",
                        0.02
                    )

                    if diagnosis["severity"] == "serious":

                        step = min(
                            2,
                            current_tap - tap_min
                        )

                    else:

                        step = 1

                    target_tap = current_tap - step

                    expected_voltage_change_pu = round(
                        -step * tap_step_percent / 100,
                        4
                    )

                    result["candidate_actions"].append({

                        "priority": 3,

                        "device_id": dev["device_id"],

                        "device_type": dtype,

                        "action": "tap_down",

                        "value": -step,

                        "unit": "tap",

                        "before_tap": current_tap,

                        "after_tap": target_tap,

                        "adjust_step": -step,

                        "expected_voltage_change_pu":
                            expected_voltage_change_pu,

                        "expected_effect": {
                            "voltage_direction": "decrease",
                            "reason": (
                                f"建议由 {current_tap} 档"
                                f"降至 {target_tap} 档，"
                                f"预计电压变化约 "
                                f"{expected_voltage_change_pu} pu"
                            )
                        },

                        "reason": (
                            "过电压可通过调压设备降档降低电压。"
                        )
                    })

    # =========================================================
    # 欠电压治理
    # =========================================================

    if is_under or (is_two_way and time_period == "night"):

        # SVG 注入无功
        if "SVG" in device_types:

            svg = next(
                d for d in devices
                if d["device_type"] == "SVG"
            )

            exceed = diagnosis.get("exceed_value_pu", 0.02)

            q = min(
                svg["capacity_kvar"],
                max(50, int(exceed * 10000))
            )

            result["candidate_actions"].append({

                "priority": 1,

                "device_id": svg["device_id"],

                "device_type": "SVG",

                "action": "inject_reactive_power",

                "value": q,

                "unit": "kVar",

                "current_q_kvar": svg.get("current_q_kvar", 0),

                "target_q_kvar": q,

                "expected_effect": {
                    "voltage_direction": "increase",
                    "reason": (
                        f"SVG注入无功 {q} kVar，"
                        f"提高电压。"
                    )
                },

                "reason": (
                    "欠电压优先采用SVG注入无功。"
                )
            })

        # 储能放电
        if "ESS" in device_types:

            ess = next(
                d for d in devices
                if d["device_type"] == "ESS"
            )

            if ess["soc"] > ess["soc_min"]:

                p = min(
                    ess["max_discharge_kw"],
                    50
                )

                result["candidate_actions"].append({

                    "priority": 2,

                    "device_id": ess["device_id"],

                    "device_type": "ESS",

                    "action": "discharge",

                    "value": p,

                    "unit": "kW",

                    "current_soc": ess["soc"],

                    "target_discharge_kw": p,

                    "expected_effect": {
                        "voltage_direction": "increase",
                        "reason": (
                            f"储能放电 {p} kW，"
                            f"提高低电压。"
                        )
                    },

                    "reason": (
                        "储能放电提供有功支撑。"
                    )
                })

        # OLTC / AVR 升档
        for dtype in ["OLTC", "AVR"]:

            if dtype in device_types:

                dev = next(
                    d for d in devices
                    if d["device_type"] == dtype
                )

                current_tap = dev["current_tap"]

                tap_max = dev["tap_max"]

                tap_step_percent = dev.get(
                    "tap_step_percent",
                    1.25
                )

                if current_tap < tap_max:

                    exceed = diagnosis.get(
                        "exceed_value_pu",
                        0.02
                    )

                    if diagnosis["severity"] == "serious":

                        step = min(
                            2,
                            tap_max - current_tap
                        )

                    else:

                        step = 1

                    target_tap = current_tap + step

                    expected_voltage_change_pu = round(
                        step * tap_step_percent / 100,
                        4
                    )

                    result["candidate_actions"].append({

                        "priority": 3,

                        "device_id": dev["device_id"],

                        "device_type": dtype,

                        "action": "tap_up",

                        "value": step,

                        "unit": "tap",

                        "before_tap": current_tap,

                        "after_tap": target_tap,

                        "adjust_step": step,

                        "expected_voltage_change_pu":
                            expected_voltage_change_pu,

                        "expected_effect": {
                            "voltage_direction": "increase",
                            "reason": (
                                f"建议由 {current_tap} 档"
                                f"升至 {target_tap} 档，"
                                f"预计电压变化约 "
                                f"+{expected_voltage_change_pu} pu"
                            )
                        },

                        "reason": (
                            "欠电压可通过调压设备升档提高电压。"
                        )
                    })

    if not result["candidate_actions"]:

        result["rule_reason"] = (
            "当前无可用调节设备或设备状态不满足动作条件。"
        )

    else:

        result["rule_reason"] = (
            "已根据电压状态、设备类型和设备约束生成候选治理策略。"
        )

    return result


def safety_check(
    strategy: Dict[str, Any],
    case: Dict[str, Any]
) -> Dict[str, Any]:

    checked_actions = []

    warnings = []

    device_map = {
        d["device_id"]: d
        for d in case.get("devices", [])
    }

    for action in strategy["candidate_actions"]:

        dev = device_map.get(action["device_id"])

        if not dev:

            warnings.append(
                f"{action['device_id']} 不存在，已删除动作。"
            )

            continue

        if dev.get("status") != "online":

            warnings.append(
                f"{action['device_id']} 不在线，已删除动作。"
            )

            continue

        # SVG
        if action["device_type"] == "SVG":

            if abs(action["value"]) > dev["capacity_kvar"]:

                warnings.append(
                    "SVG动作超过容量，已截断到容量范围。"
                )

                action["value"] = (
                    dev["capacity_kvar"]
                    if action["value"] > 0
                    else -dev["capacity_kvar"]
                )

        # OLTC / AVR
        if action["device_type"] in ["OLTC", "AVR"]:

            new_tap = (
                dev["current_tap"]
                + action["value"]
            )

            if (
                new_tap < dev["tap_min"]
                or new_tap > dev["tap_max"]
            ):

                warnings.append(
                    f"{action['device_id']} 档位越界，"
                    f"已删除动作。"
                )

                continue

            if (
                dev.get("today_action_count", 0)
                >= dev.get("max_daily_action_count", 999)
            ):

                warnings.append(
                    f"{action['device_id']} 今日动作次数已达上限，"
                    f"已删除动作。"
                )

                continue

        # 储能
        if action["device_type"] == "ESS":

            if (
                action["action"] == "charge"
                and dev["soc"] >= dev["soc_max"]
            ):

                warnings.append(
                    "储能SOC接近上限，禁止继续充电。"
                )

                continue

            if (
                action["action"] == "discharge"
                and dev["soc"] <= dev["soc_min"]
            ):

                warnings.append(
                    "储能SOC接近下限，禁止继续放电。"
                )

                continue

        # 光伏逆变器
        elif action["device_type"] == "PV_INVERTER_CLUSTER":

            if (
                action["action"]
                == "inverter_absorb_reactive_power"
            ):

                cap = dev.get(
                    "reactive_capacity_kvar",
                    0
                )

                if abs(action["value"]) > cap:

                    warnings.append(
                        "逆变器无功动作超过容量，已截断。"
                    )

                    action["value"] = -cap

            if (
                action["action"]
                == "active_power_curtailment"
            ):

                max_p = dev.get(
                    "active_curtailment_max_kw",
                    0
                )

                if abs(action["value"]) > max_p:

                    warnings.append(
                        "逆变器有功削减超过上限，已截断。"
                    )

                    action["value"] = -max_p

        checked_actions.append(action)

    return {
        **strategy,
        "checked_actions": checked_actions,
        "warnings": warnings
    }