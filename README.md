# 电网光伏电压治理智能体 MVP

这是一个本地小样本验证实验，用于模拟：

台区数据输入 → 本地 Ollama/Qwen3:4B 分析 → 规则约束校验 → 输出电压治理策略

## 1. 创建虚拟环境

Windows PowerShell：

```powershell
cd G:\grid_agent_mvp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. 确认 Ollama 模型可用

```powershell
ollama list
ollama run qwen3:4b
```

能正常对话后，退出模型对话。

## 3. 运行实验

```powershell
python main.py
```

## 4. 输出结果

程序会读取：

```text
data/sample_cases.json
```

然后生成：

```text
output/decision_results.json
```

## 5. 项目结构

```text
grid_agent_mvp/
├── main.py
├── requirements.txt
├── data/
│   └── sample_cases.json
├── src/
│   ├── ollama_client.py
│   ├── rule_engine.py
│   ├── decision_agent.py
│   └── utils.py
└── output/
```
