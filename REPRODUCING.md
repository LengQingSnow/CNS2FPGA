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
`code/Paper/paper_data/manifest.json`.

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

## 4 Inspect the Ethernet runtime deployment

The board-tested runtime image is
`hardware/bitstreams/cns2fpga_runtime_eth_200mhz.bit` (SHA-256
`581354a62c8c7aeb134f300e7ea1928d8b681b996807710c61e307b33530d8f8`).
The public package includes the matching Step-16 RTL, MAC dependency with its
own MIT notice, constraints, UDP host loader, key routed summaries, upload
transcript **excerpts**, and complete eight-step courtship capture words.
PowerShell host identity/session metadata and diagnostic packet captures are
not published. The untouched full transcripts remain in the development
workspace. The repository manifest identifies the source of each curated file.

Read `code/15_Ethernet_Runtime_Deployment/README.md` for the board protocol.
Its historical one-click PowerShell wrappers default to machine-specific Vivado
and NIC settings; review and override their parameters before use. In
particular, public release packaging does not make them safe to execute on an
arbitrary computer or network. This UDP control port has no authentication:
use an isolated lab link. The 100-Mbps negotiated upload is not a measured
end-to-end throughput benchmark.

For a hardware-free comparison of the two captured `smoke8` runs, execute
`python "code/15_Ethernet_Runtime_Deployment/scripts/build_old_new_board_comparison.py"`
from the repository root. The script asserts identical ordered events and
non-latency summary words and reports the per-step cycle differences. The
updated paper is available as Markdown, DOCX and PDF under `code/Paper/`;
its Table 5 is paired only over this eight-step input. The visual graph was
committed and status-checked on the new bitstream but was **not** executed in
a new-bitstream trial.

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
素材来源在 `code/Paper/paper_data/manifest.json`。

硬件流程需要已安装且具备许可的 Vivado、兼容的仿真器；板卡试验还需要
ALINX AXKU115 V1.0 和 JTAG 线。已验证的 bit 文件在 `hardware/bitstreams/`。
若早期主机脚本要求原来的 `code/<step>/build/...` 路径，可在本机把对应 bit
文件复制到该目录；构建目录被 Git 忽略。绝不能把这些镜像烧录到其他 FPGA 型号。

仓库中的三份第 7、8 步 `.log` 文件是原始 ModelSim 输出的精简摘录，**并非完整
仿真日志**。它们保留了项目 testbench 的 PASS 行和最终错误摘要，文件头记录
完整本地日志的 SHA-256。独立确认时应使用提供的脚本重新运行 ModelSim。

### 4 检查网口运行时部署

已上板测试的网口 bit 文件为 `hardware/bitstreams/cns2fpga_runtime_eth_200mhz.bit`
（SHA-256 `581354a62c8c7aeb134f300e7ea1928d8b681b996807710c61e307b33530d8f8`）。
公开包包含对应第 15 步 RTL、带独立 MIT 声明的 MAC 依赖、约束、UDP 装载器、
选定布线摘要、上传日志**摘录**和完整的求偶 8 步采集字。不会发布 PowerShell
主机身份与会话元数据或诊断抓包；未经修改的完整日志仍保留在开发工作区。

历史一键式 PowerShell 脚本默认采用本机 Vivado 和网卡设定，运行前须按
目标环境检查和修改，不应在任意电脑或网络上直接执行。UDP 控制口没有认证，
只能用于隔离的实验链路；100 Mbps 是本次协商速率，不是端到端吞吐率。

无需板卡即可运行
`python "code/15_Ethernet_Runtime_Deployment/scripts/build_old_new_board_comparison.py"`
核查新旧 `smoke8` 的事件、摘要和周期差异。更新的论文以 Markdown、DOCX 和 PDF
放在 `code/Paper/`；表 5 只比较相同的 8 步输入。视觉图在新 bit 文件上完成
COMMIT 与 STATUS 校验，**尚未在该 bit 文件上执行新试验**。

### 比较层级

1. 浮点 CPU 对定点 CPU：检查数值格式的影响。
2. 定点 CPU 对 RTL：在短仿真中检查虚拟神经元状态。
3. 定点 CPU 对已编程 FPGA：检查导出的事件与计数器。

长时间求偶鸣唱板卡试验没有导出每个神经元的事件，仅导出了各时间步的群体计数。
短时求偶鸣唱 raster 和视觉左侧输入试验导出了有序事件记录。由于实验成像 ROI
与 MaleCNS 细胞之间的映射以及刺激转导尚未得到独立验证，生物学解释仍有条件限制。
