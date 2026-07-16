# Master's project framework - static metrics

## 1. Toolchain

- **Custom Python Scripts (Orchestrator):** Aggregates data, executes analysis, and exports results to Pandas DataFrames/CSV.
- **Tree-sitter:** Language-agnostic AST parser (we are starting with python, in the future potential to expand to different languages) used to build custom structural and scope-based metrics.
- **Radon:** Python library for extracting information volume and raw textual metrics.
- **SonarQube (Community Build):** Local Docker container used via its Web API to extract baseline cognitive metrics.

---

## 2. Metrics Matrix

### Structural & Control Flow

- **Nesting Depth Penalty (Tree-sitter):** Exponential penalty tracker based on nested conditional blocks (`if`, `for`, `while`).
- **Cognitive Complexity (SonarQube API):** Industry-standard metric accounting for breaks in linear code reading.

### Working Memory & Volume

- **Parameter Count (Tree-sitter):** Total arguments per function to evaluate constraints against Miller's Law ($7 \pm 2$).
- **Halstead Mental Effort (Radon):** Mathematical difficulty score calculated from the ratio of unique operators to operands.
- **Variable Scope Distance (Tree-sitter):** Line count delta between a variable's declaration and its final usage.

### Visual & Semantic Friction

- **Indentation Variance (Python Script):** Standard deviation of leading whitespaces per line to detect erratic visual layout.
- **Line Width Bounds (Python Script):** Max and mean character lengths per line to identify text exceeding peripheral vision bounds.
- **Average Identifier Length (Tree-sitter):** Mean character length of variables/functions to capture naming fatigue or cryptic abstractions.
- **Comment-to-Code Ratio (Radon):** Proportions of documentation vs. execution logic.

---

## 3. Implementation Roadmap

### Milestone 1: Core Orchestration & Text Metrics

- Build the main Python execution wrapper.
- Implement native text-parsing scripts for line width and indentation variance.
- Integrate Radon's API for Halstead and comment metrics.

### Milestone 2: Tree-sitter Custom Parsing

- Set up `tree-sitter-languages` for Python.
- Write AST queries for parameter counting, identifier lengths, variable lifetimes, and the nesting depth penalty.

### Milestone 3: SonarQube Integration & Export

- Deploy a local SonarQube Docker container.
- Configure the orchestrator to launch a project scan and query the Web API for Cognitive Complexity values.
- Format final metrics into a unified, research-ready tabular dataset (CSV/JSON).
