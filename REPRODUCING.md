# Reproducing the recorded results

## 1 Prepare the environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\download_malecns.py
.\.venv\Scripts\python.exe scripts\validate_repository.py
```

The download is about 1.1 GB. The three `.feather` files are written to
`support/` only after each SHA-256 check succeeds. Existing mismatched files
are never overwritten by the helper.

## 2 Run a small CPU and data smoke test

```powershell
.\.venv\Scripts\python.exe -m pytest -q "code\2_Subcircuit Automatic Extraction Tool\tests" "code\12_Visual-to-Steering Circuit\tests"
```

This checks deterministic sparse-row construction, the visual graph and
compiler image, CPU response, baseline, and the archived physical capture.
Some historical step scripts show absolute paths to the development runtime;
replace those with your own Python executable when invoking them.

For the complete offline regression suite, run
`.\.venv\Scripts\python.exe -m pytest -q code`.

## 3 Rebuild without changing archived outputs

The numbered `README.md` files give the commands and contracts for each step.
When rerunning an extractor or compiler, use a new output directory instead
of replacing the recorded `outputs/*_v0`/`*_v1` snapshots. The original
MaleCNS release and source hashes are listed in `support/data_sources.json`;
the paper CSV/figure sources are listed in
`code/14_Paper/paper_data/manifest.json`.

The hardware flow requires licensed/installed Vivado, a compatible simulator,
and (for board trials) the ALINX AXKU115 V1.0 and JTAG cable. The verified
bitstreams are under `hardware/bitstreams/`. To use historical host scripts
that expect the original `code/<step>/build/...` path, copy the corresponding
bitstream there locally; those build directories are ignored by Git. Never
program a different FPGA part with these images.

The three committed Step-7/Step-8 `.log` files are deliberately reduced
excerpts of the original ModelSim output, not full simulator transcripts.
They preserve the project testbench PASS lines and final error summaries;
their headers record SHA-256 values of the full local logs. Rerun ModelSim
with the supplied scripts for independent confirmation.

## Comparison levels

1. Floating CPU versus fixed CPU tests the numerical format.
2. Fixed CPU versus RTL tests virtual-neuron state in short simulations.
3. Fixed CPU versus programmed FPGA tests exported events and counters.

Long courtship board trials did not export every neuron event; they exported
per-timestep population counts. The short courtship raster and visual-left
trial did export ordered event records. The biological interpretation remains
conditional because experimental ROI-to-MaleCNS cell mapping and stimulus
transduction are not independently validated.

## 中文说明：复现已记录的结果

### 1 准备环境

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\download_malecns.py
.\.venv\Scripts\python.exe scripts\validate_repository.py
```

下载量约 1.1 GB。三个 `.feather` 文件只有通过 SHA-256 校验才会写入
`support/`。下载工具不会覆盖校验不通过的已有文件。

### 2 运行 CPU 与数据快速测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q "code\2_Subcircuit Automatic Extraction Tool\tests" "code\12_Visual-to-Steering Circuit\tests"
```

这些测试检查确定性的稀疏行构建、视觉图和编译镜像、CPU 响应、基线及归档的
板卡采集。一些早期步骤脚本写有开发机 Python 的绝对路径；运行时应换成你自己
的 Python 路径。完整离线回归测试可运行
`.\.venv\Scripts\python.exe -m pytest -q code`。

### 3 不覆盖归档结果的重建方式

各编号目录中的 `README.md` 给出了相应命令和接口约定。重跑抽取器或编译器时，
请使用新的输出目录，不要覆盖已记录的 `outputs/*_v0`/`*_v1` 快照。
MaleCNS 发行版本及原始文件哈希在 `support/data_sources.json`；论文 CSV 与图像
素材来源在 `code/14_Paper/paper_data/manifest.json`。

硬件流程需要已安装且具备许可的 Vivado、兼容的仿真器；板卡试验还需要
ALINX AXKU115 V1.0 和 JTAG 线。已验证的 bit 文件在 `hardware/bitstreams/`。
若早期主机脚本要求原来的 `code/<step>/build/...` 路径，可在本机把对应 bit
文件复制到该目录；构建目录被 Git 忽略。绝不能把这些镜像烧录到其他 FPGA 型号。

仓库中的三份第 7、8 步 `.log` 文件是原始 ModelSim 输出的精简摘录，**并非完整
仿真日志**。它们保留了项目 testbench 的 PASS 行和最终错误摘要，文件头记录
完整本地日志的 SHA-256。独立确认时应使用提供的脚本重新运行 ModelSim。

### 比较层级

1. 浮点 CPU 对定点 CPU：检查数值格式的影响。
2. 定点 CPU 对 RTL：在短仿真中检查虚拟神经元状态。
3. 定点 CPU 对已编程 FPGA：检查导出的事件与计数器。

长时间求偶鸣唱板卡试验没有导出每个神经元的事件，仅导出了各时间步的群体计数。
短时求偶鸣唱 raster 和视觉左侧输入试验导出了有序事件记录。由于实验成像 ROI
与 MaleCNS 细胞之间的映射以及刺激转导尚未得到独立验证，生物学解释仍有条件限制。
