import time
from datetime import datetime
from time import perf_counter

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.utils import read_json
from src.agent import VoltageGovernanceAgent
from src.decision_reporter import build_decision_report
from src.state_manager import update_device_state
from src.voltage_feedback import apply_voltage_feedback


st.set_page_config(
    page_title="配网电压治理智能体演示系统",
    layout="wide"
)


CUSTOM_CSS = """
<style>
.block-container {
    padding-top: 1.2rem;
    max-width: 1500px;
}
.card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
}
.metric-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 22px;
    text-align: center;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
}
.metric-title {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 8px;
}
.metric-value {
    font-size: 34px;
    font-weight: 800;
    color: #1f2937;
}
.metric-blue { color: #2563eb; }
.metric-green { color: #059669; }
.metric-red { color: #dc2626; }
.step-box {
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 15px;
    text-align: center;
    background: #ffffff;
    font-weight: 700;
}
.terminal {
    background: #0f172a;
    color: #dbeafe;
    border-radius: 16px;
    padding: 20px;
    min-height: 300px;
    font-family: Consolas, monospace;
    font-size: 14px;
    white-space: pre-wrap;
}
.small {
    color: #64748b;
    font-size: 13px;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def init_state():
    defaults = {
        "running": False,
        "tick": 0,
        "current_tap": 0,
        "history": [],
        "previous_actions": [],
        "latest_result": None,
        "latest_case": None,
        "latest_report": "",
        "last_action_text": "无",
        "terminal_logs": [],
        "response_time": "--",
        "selected_case_name": None,
        "refresh_seconds": 5,
        "event_active": False,
        "event_mode": None,
        "event_step": 0,
        "event_start_time": None,
        "event_cross_time": None,
        "event_response_done": False,
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_system(keep_selected_case=True):
    selected_case_name = st.session_state.get("selected_case_name") if keep_selected_case else None
    refresh_seconds = st.session_state.get("refresh_seconds", 5)

    st.session_state.running = False
    st.session_state.tick = 0
    st.session_state.current_tap = 0
    st.session_state.history = []
    st.session_state.previous_actions = []
    st.session_state.latest_result = None
    st.session_state.latest_case = None
    st.session_state.latest_report = ""
    st.session_state.last_action_text = "无"
    st.session_state.terminal_logs = []
    st.session_state.response_time = "--"
    st.session_state.selected_case_name = selected_case_name
    st.session_state.refresh_seconds = refresh_seconds
    st.session_state.event_active = False
    st.session_state.event_mode = None
    st.session_state.event_step = 0
    st.session_state.event_start_time = None
    st.session_state.event_cross_time = None
    st.session_state.event_response_done = False


def get_status_label(problem_type):
    return {
        "normal": "正常",
        "over_voltage": "过电压",
        "under_voltage": "欠电压",
        "two_way_voltage_violation": "双向越限"
    }.get(problem_type, problem_type)


def event_voltage(mode, step):
    """
    5秒动态过程，按1秒一帧：
    step 0: 正常
    step 1: 接近边界
    step 2: 刚越限
    step 3: 治理中，开始回落
    step 4: 恢复正常
    step >=5: 正常
    """
    if mode == "过电压":
        points = [
            (1.000, 0.995),
            (1.055, 0.980),
            (1.082, 0.970),
            (1.045, 0.975),
            (1.005, 0.995),
            (1.000, 0.995),
        ]
    elif mode == "欠电压":
        points = [
            (1.000, 0.995),
            (1.000, 0.945),
            (1.010, 0.910),
            (1.005, 0.945),
            (1.000, 0.995),
            (1.000, 0.995),
        ]
    elif mode == "双向越限":
        points = [
            (1.000, 0.995),
            (1.055, 0.945),
            (1.090, 0.905),
            (1.045, 0.945),
            (1.000, 0.995),
            (1.000, 0.995),
        ]
    else:
        points = [
            (1.000, 0.995),
            (1.001, 0.995),
            (1.000, 0.996),
            (1.001, 0.995),
            (1.000, 0.995),
        ]

    if step >= len(points):
        return points[-1]

    return points[step]


def normal_voltage(tick):
    return 1.000 + (tick % 3) * 0.001, 0.995


def build_demo_case(selected_case, mode, current_tap, tick):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if st.session_state.event_active:
        max_pu, min_pu = event_voltage(mode, st.session_state.event_step)
    else:
        max_pu, min_pu = normal_voltage(tick)

    if mode == "过电压":
        time_period = "day"
        pv_power = 210
        load_power = 70
    elif mode == "欠电压":
        time_period = "night"
        pv_power = 0
        load_power = 190
    elif mode == "双向越限":
        time_period = "night"
        pv_power = 160
        load_power = 190
    else:
        time_period = "day"
        pv_power = 30
        load_power = 120

    return {
        "case_id": f"DEMO_STREAM_{tick:04d}",
        "source_case_id": selected_case.get("case_id", "DEMO_CASE"),
        "area_id": selected_case.get("area_id", "DEMO_AREA"),
        "area_name": selected_case.get("case_name", selected_case.get("area_name", "示范台区")),
        "timestamp": now,
        "time_period": time_period,
        "voltage": {
            "max_pu": round(max_pu, 4),
            "min_pu": round(min_pu, 4),
            "upper_limit_pu": 1.07,
            "lower_limit_pu": 0.93
        },
        "pv_power_kw": pv_power,
        "load_power_kw": load_power,
        "devices": [
            {
                "device_id": "AVR_DEMO_001",
                "device_type": "AVR",
                "device_name": "低压线路自动调压器",
                "status": "online",
                "current_tap": current_tap,
                "tap_min": -8,
                "tap_max": 16,
                "tap_step_percent": 1.25
            }
        ]
    }


def is_voltage_normal(case):
    v = case["voltage"]
    return v["max_pu"] <= v["upper_limit_pu"] and v["min_pu"] >= v["lower_limit_pu"]


def is_voltage_crossed(case):
    return not is_voltage_normal(case)


def build_terminal_logs(result, case, actions):
    logs = []
    problem_type = result["problem_analysis"]["problem_type"]

    logs.append(f"检测状态：{get_status_label(problem_type)}")
    logs.append(f"最大电压：{case['voltage']['max_pu']} pu")
    logs.append(f"最小电压：{case['voltage']['min_pu']} pu")

    if st.session_state.event_active:
        logs.append(f"异常演化阶段：第 {st.session_state.event_step}/4 秒")
    else:
        logs.append("异常演化阶段：稳定监测")

    if case.get("voltage_feedback", {}).get("applied"):
        fb = case["voltage_feedback"]
        logs.append(f"闭环反馈：上一轮治理使电压修正 {fb.get('delta_pu')} pu")

    if actions:
        for action in actions:
            eva = action.get("evaluation", {})
            logs.append(
                f"执行策略：设备 {action.get('device_id')}，"
                f"动作 {action.get('action')}，"
                f"调节 {action.get('value')} {action.get('unit')}，"
                f"综合评分 {eva.get('total_score', '--')}"
            )

            if "before_tap" in action and "after_tap" in action:
                logs.append(f"档位调整：{action.get('before_tap')} → {action.get('after_tap')}")

            if "expected_effect" in action:
                effect = action.get("expected_effect", {})
                logs.append(f"预期效果：{effect.get('reason', '无')}")
    else:
        logs.append("当前无需治理动作，系统持续监测。")

    return logs


def run_one_step(agent, selected_case):
    st.session_state.tick += 1

    mode = st.session_state.event_mode or "正常"

    case = build_demo_case(
        selected_case=selected_case,
        mode=mode,
        current_tap=st.session_state.current_tap,
        tick=st.session_state.tick
    )

    # 动态异常演示时，不额外叠加反馈修正，避免曲线跳变太大
    if not st.session_state.event_active:
        case = apply_voltage_feedback(case, st.session_state.previous_actions)

    crossed = is_voltage_crossed(case)

    if crossed and st.session_state.event_cross_time is None:
        st.session_state.event_cross_time = perf_counter()

    start_time = perf_counter()
    result = agent.run(case)
    agent_elapsed = perf_counter() - start_time

    actions = result.get("checked_actions", [])

    # 响应时长：从越限开始到恢复正常
    if st.session_state.event_cross_time is not None and is_voltage_normal(case):
        total_elapsed = perf_counter() - st.session_state.event_cross_time
        st.session_state.response_time = f"{total_elapsed:.2f} s"
        st.session_state.event_response_done = True
    elif actions:
        st.session_state.response_time = f"{agent_elapsed:.3f} s"

    report = build_decision_report(result)

    updated_case = update_device_state(case, actions)

    for dev in updated_case.get("devices", []):
        if dev.get("device_id") == "AVR_DEMO_001":
            st.session_state.current_tap = dev.get("current_tap", st.session_state.current_tap)

    best_action = actions[0] if actions else {}

    if actions:
        st.session_state.last_action_text = f"{best_action.get('action')} {best_action.get('value')} {best_action.get('unit')}"
    else:
        st.session_state.last_action_text = "无"

    result["case_id"] = case["case_id"]
    result["area_name"] = case["area_name"]
    result["timestamp"] = case["timestamp"]
    result["decision_report"] = report
    result["voltage_feedback"] = case.get("voltage_feedback", {})

    max_voltage_v = round(case["voltage"]["max_pu"] * 380, 1)
    min_voltage_v = round(case["voltage"]["min_pu"] * 380, 1)

    problem_type = result["problem_analysis"]["problem_type"]

    if problem_type in ["under_voltage", "two_way_voltage_violation"]:
        display_voltage_v = min_voltage_v
    else:
        display_voltage_v = max_voltage_v

    st.session_state.history.append({
        "时间": case["timestamp"],
        "实时电压V": display_voltage_v,
        "最大电压pu": case["voltage"]["max_pu"],
        "最小电压pu": case["voltage"]["min_pu"],
        "光伏出力kW": case.get("pv_power_kw", 0),
        "负荷功率kW": case.get("load_power_kw", 0),
        "状态": get_status_label(problem_type),
        "治理动作": best_action.get("action", "无"),
        "调节值": f"{best_action.get('value', '')} {best_action.get('unit', '')}".strip(),
        "当前档位": st.session_state.current_tap,
        "综合评分": best_action.get("evaluation", {}).get("total_score", ""),
        "响应时长": st.session_state.response_time
    })

    st.session_state.history = st.session_state.history[-50:]

    st.session_state.previous_actions = actions
    st.session_state.latest_result = result
    st.session_state.latest_case = case
    st.session_state.latest_report = report
    st.session_state.terminal_logs = build_terminal_logs(result, case, actions)

    if st.session_state.event_active:
        st.session_state.event_step += 1

        if st.session_state.event_step >= 5:
            st.session_state.event_active = False
            st.session_state.event_mode = None
            st.session_state.event_step = 0
            st.session_state.event_cross_time = None


def build_voltage_chart(history_df):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=history_df["时间"],
        y=history_df["实时电压V"],
        mode="lines+markers",
        name="实时电压",
        line=dict(width=2)
    ))

    fig.add_hline(y=406.6, line_dash="dash", annotation_text="上限约406.6V")
    fig.add_hline(y=353.4, line_dash="dash", annotation_text="下限约353.4V")

    fig.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="时间",
        yaxis_title="电压(V)",
        hovermode="x unified",
        uirevision="keep_zoom",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )

    return fig


init_state()

case_library = read_json("data/real_case_library.json")
capability_library = read_json("data/device_capability_library.json")
agent = VoltageGovernanceAgent(case_library, capability_library)

case_names = [
    c.get("case_name", c.get("area_name", c.get("case_id", "未知案例")))
    for c in case_library
]

st.markdown("## 配网电压治理智能体演示系统")

top1, top2, top3 = st.columns([3, 1, 1])

with top1:
    selected_name = st.selectbox("台区案例选择", case_names, index=0)

if st.session_state.selected_case_name is None:
    st.session_state.selected_case_name = selected_name

if selected_name != st.session_state.selected_case_name:
    st.session_state.selected_case_name = selected_name
    reset_system(keep_selected_case=True)
    st.rerun()

selected_case = case_library[case_names.index(selected_name)]

with top2:
    if st.button("启动决策流", use_container_width=True):
        st.session_state.running = True

with top3:
    if st.button("重置系统", use_container_width=True):
        reset_system(keep_selected_case=True)
        st.rerun()

ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])

with ctrl1:
    anomaly_mode = st.selectbox(
        "异常类型选择",
        ["过电压", "欠电压", "双向越限"],
        index=0
    )

with ctrl2:
    if st.button("触发一次异常", use_container_width=True):
        st.session_state.event_active = True
        st.session_state.event_mode = anomaly_mode
        st.session_state.event_step = 0
        st.session_state.event_start_time = perf_counter()
        st.session_state.event_cross_time = None
        st.session_state.event_response_done = False
        st.session_state.response_time = "--"
        st.session_state.running = True
        run_one_step(agent, selected_case)
        st.rerun()

with ctrl3:
    refresh_options = [1, 5, 10, 30]
    current_index = refresh_options.index(st.session_state.refresh_seconds)

    selected_refresh = st.selectbox(
        "刷新间隔",
        refresh_options,
        index=current_index,
        key="refresh_select"
    )

    st.session_state.refresh_seconds = selected_refresh

if st.button("暂停", use_container_width=True):
    st.session_state.running = False

if st.session_state.latest_result is None:
    run_one_step(agent, selected_case)

elif st.session_state.running:
    run_one_step(agent, selected_case)

latest_result = st.session_state.latest_result
latest_case = st.session_state.latest_case
latest_problem = latest_result.get("problem_analysis", {})
latest_actions = latest_result.get("checked_actions", [])

status = get_status_label(latest_problem.get("problem_type", "normal"))
problem_type = latest_problem.get("problem_type", "normal")

if problem_type in ["under_voltage", "two_way_voltage_violation"]:
    current_voltage_v = round(latest_case["voltage"]["min_pu"] * 380, 1)
else:
    current_voltage_v = round(latest_case["voltage"]["max_pu"] * 380, 1)

if problem_type == "normal":
    qualified_rate = "99.9%"
    status_color = "metric-green"
else:
    qualified_rate = "异常"
    status_color = "metric-red"

response_time = st.session_state.response_time

st.markdown("---")

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">当前实测电压</div>
            <div class="metric-value">{current_voltage_v} V</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with m2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">运行健康状态</div>
            <div class="metric-value {status_color}">{status}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with m3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">电压合格率</div>
            <div class="metric-value {status_color}">{qualified_rate}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with m4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">策略响应时长</div>
            <div class="metric-value metric-blue">{response_time}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")

left, right = st.columns([3, 1])

history_df = pd.DataFrame(st.session_state.history)

with left:
    shown_refresh = 1 if st.session_state.event_active else st.session_state.refresh_seconds
    st.markdown(f"### 实时电压趋势（当前刷新：{shown_refresh}秒）")
    if not history_df.empty:
        fig = build_voltage_chart(history_df)
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
    else:
        st.info("暂无实时数据。")

with right:
    st.markdown("### 实时监测信息")
    st.markdown(
        f"""
        <div class="card">
            <div class="small">台区名称</div>
            <b>{latest_case.get("area_name", "")}</b><br><br>
            <div class="small">当前时间</div>
            <b>{latest_case.get("timestamp", "")}</b><br><br>
            <div class="small">最大电压</div>
            <b>{latest_case["voltage"]["max_pu"]} pu</b><br><br>
            <div class="small">最小电压</div>
            <b>{latest_case["voltage"]["min_pu"]} pu</b><br><br>
            <div class="small">光伏出力</div>
            <b>{latest_case.get("pv_power_kw", 0)} kW</b><br><br>
            <div class="small">负荷功率</div>
            <b>{latest_case.get("load_power_kw", 0)} kW</b><br><br>
            <div class="small">当前档位</div>
            <b>{st.session_state.current_tap}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")

flow_left, terminal_right = st.columns([2, 1])

with flow_left:
    st.markdown("### 智能体决策流程")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown('<div class="step-box">STEP 01<br>数据感知</div>', unsafe_allow_html=True)
    with s2:
        st.markdown('<div class="step-box">STEP 02<br>策略生成</div>', unsafe_allow_html=True)
    with s3:
        st.markdown('<div class="step-box">STEP 03<br>策略优选</div>', unsafe_allow_html=True)
    with s4:
        st.markdown('<div class="step-box">STEP 04<br>执行建议</div>', unsafe_allow_html=True)

    st.markdown("### 实时采样与治理结果")
    st.dataframe(history_df, use_container_width=True)

with terminal_right:
    score = latest_actions[0].get("evaluation", {}).get("total_score", "--") if latest_actions else "--"
    process_logs = "\n".join([f"> {log}" for log in st.session_state.get("terminal_logs", [])])

    terminal_text = f"""
TERMINAL MONITOR

> 系统运行状态：{"运行中" if st.session_state.running else "待机"}
> 数据采集频率：{st.session_state.refresh_seconds} 秒
> 当前演示刷新：{1 if st.session_state.event_active else st.session_state.refresh_seconds} 秒
> 当前异常状态：{status}
> 当前推荐动作：{st.session_state.last_action_text}
> 综合评分：{score}
> 当前档位：{st.session_state.current_tap}
> 策略响应时长：{response_time}
> 异常触发模式：缓慢越限，治理后恢复

{process_logs}
"""
    st.markdown(f'<div class="terminal"><pre>{terminal_text}</pre></div>', unsafe_allow_html=True)

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["历史案例匹配", "治理动作评分", "决策报告"])

with tab1:
    matched_cases = latest_result.get("matched_real_cases", [])
    if matched_cases:
        matched_df = pd.DataFrame([
            {
                "案例名称": c.get("case_name"),
                "匹配分数": c.get("score"),
                "参考意义": c.get("summary")
            }
            for c in matched_cases
        ])
        st.dataframe(matched_df, use_container_width=True)
    else:
        st.info("当前未触发案例检索。")

with tab2:
    if latest_actions:
        action_df = pd.DataFrame([
            {
                "设备ID": a.get("device_id"),
                "设备类型": a.get("device_type"),
                "动作": a.get("action"),
                "调节值": f"{a.get('value')} {a.get('unit')}",
                "当前档位": a.get("before_tap", ""),
                "目标档位": a.get("after_tap", ""),
                "有效性": a.get("evaluation", {}).get("effective_score", ""),
                "经济性": a.get("evaluation", {}).get("economy_score", ""),
                "可落地性": a.get("evaluation", {}).get("feasibility_score", ""),
                "风险控制": a.get("evaluation", {}).get("risk_score", ""),
                "综合评分": a.get("evaluation", {}).get("total_score", "")
            }
            for a in latest_actions
        ])
        st.dataframe(action_df, use_container_width=True)
    else:
        st.info("当前无需治理动作。")

with tab3:
    st.text_area("最新决策报告", st.session_state.latest_report, height=420)

if st.session_state.running:
    sleep_seconds = 1 if st.session_state.event_active else st.session_state.refresh_seconds
    time.sleep(sleep_seconds)
    st.rerun()