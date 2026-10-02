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
The public package includes the matching Step-15 RTL, MAC dependency with its
own MIT notice, constraints, UDP host loader, key routed summaries, upload
transcript excerpts, the original eight-step capture, and curated P0 captures
from two independently programmed sessions. The P0 campaign/fault logs have
local machine paths redacted; diagnostic packet captures are not included.
Untouched full development transcripts remain local. The repository manifest
identifies each curated source.
The separate expanded-event image is
`hardware/bitstreams/cns2fpga_runtime_eth_long_events_200mhz.bit` (SHA-256
`d4c9378d461147062fa5dc590cb3647d241c789b01cc6255f38da16cb21990df`).
Its 131,072-entry event buffer was physically tested in one successful
courtship campaign after a failed first-program Ethernet attempt and
reprogramming of the same bitstream. The archived audit and complete raw
board/CPU event data are under
`code/15_Ethernet_Runtime_Deployment/reports/long_event_board_20260930/`.

Read `code/15_Ethernet_Runtime_Deployment/README.md` for the board protocol.
Its historical one-click PowerShell wrappers default to machine-specific Vivado
and NIC settings; review and override their parameters before use. In
particular, public release packaging does not make them safe to execute on an
arbitrary computer or network. This UDP control port has no authentication:
use an isolated lab link. The initial 100-Mbps and P0 host-observed 1-Gbps
negotiated links are separate observations, neither a line-rate benchmark.

For a hardware-free comparison of the two captured `smoke8` runs, execute
`python "code/15_Ethernet_Runtime_Deployment/scripts/build_old_new_board_comparison.py"`
from the repository root. The script asserts identical ordered events and
non-latency summary words and reports the per-step cycle differences. The
updated paper is available as Markdown, DOCX and PDF under `code/Paper/`;
Table 5 pairs the eight-step trial, while Table 6 reports three 4,308-step
courtship conditions on the Ethernet bitstream. The visual image was also
executed for 250 steps in both P0 sessions, matching 560 ordered events each.
The complete offline P0 audit can be rerun from the repository root:

```powershell
python "code/15_Ethernet_Runtime_Deployment/scripts/audit_p0_campaign.py" --campaign-root "code/15_Ethernet_Runtime_Deployment/reports/p0_board_20260930" --campaign-log "code/15_Ethernet_Runtime_Deployment/reports/p0_board_20260930/campaign.log" --jtag-root "code/14_Runtime Reconfigurable Deployment/reports/p0_board_20260930" --jtag-fault-root "code/14_Runtime Reconfigurable Deployment/reports/p0_board_20260930" --output "code/15_Ethernet_Runtime_Deployment/reports/p0_board_audit_recheck.json"
```

Use a new output name so the archived audit is not replaced.

## Comparison levels

1. Floating CPU versus fixed CPU tests the numerical format.
2. Fixed CPU versus RTL tests virtual-neuron state in short simulations.
3. Fixed CPU versus programmed FPGA tests exported events and counters.

The original P0 long courtship trials exported per-timestep counts but not
every neuron event. The later expanded-event runtime trial exported all
40,868/74,765/99,349 ordered individual events and matched independent
fixed-CPU references in the three selected conditions. The biological interpretation remains
conditional because experimental ROI-to-MaleCNS cell mapping and stimulus
transduction are not independently validated.

### Additional measured 100-Mbps capture (V0.3)

Recheck the archived capture without a board or a network connection:

```powershell
python "code/15_Ethernet_Runtime_Deployment/scripts/audit_100m_board_test.py" --output "$env:TEMP/cns2fpga_100m_recheck.json"
```

The audit verifies the bitstream hash, all eight counts, 2,475 ordered events,
epoch/checksum, deadline/fault flags and the selected upload/link/FCS logs.
Its canonical output is `reports/expanded_bit_100m_audit_v1.json`. The raw
capture and selected log excerpts are in `reports/expanded_bit_100m_20261001/`.
This is a separate short trial, not another long-event campaign. Actual
100-Mbps operation passed; further 1-Gbps testing is deferred, with neither
cable capability nor a specific RGMII fault confirmed.

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
选定布线摘要、上传日志摘录，以及 P0 双会话的视觉、求偶板卡采集。
P0 试验与异常日志会去除本机路径后发布；诊断抓包不发布，未经修改的完整日志
仍保留在开发工作区。
另有扩展事件容量的 `hardware/bitstreams/cns2fpga_runtime_eth_long_events_200mhz.bit`
（SHA-256 `d4c9378d461147062fa5dc590cb3647d241c789b01cc6255f38da16cb21990df`），
将事件容量增加到 131,072。首次烧录后网口未应答，重新烧录同一文件后的一次
成功试验，完整采集三组求偶长试验的 40,868/74,765/99,349 个有序事件，
全部与独立定点 CPU 参考一致。原始数据和审计见第 15 步 `reports/long_event_board_20260930/`。

历史一键式 PowerShell 脚本默认采用本机 Vivado 和网卡设定，运行前须按
目标环境检查和修改，不应在任意电脑或网络上直接执行。UDP 控制口没有认证，
只能用于隔离的实验链路。初始试验的 100 Mbps 与 P0 期间主机观察到的
1 Gbps 是两次不同的链路记录，都不代表达到线速吞吐率。

无需板卡即可运行
`python "code/15_Ethernet_Runtime_Deployment/scripts/build_old_new_board_comparison.py"`
核查新旧 `smoke8` 的事件、摘要和周期差异。更新的论文以 Markdown、DOCX 和 PDF
放在 `code/Paper/`；表 5 比较相同的 8 步输入，表 6 则记录网口新版的三组
4,308 步求偶条件。视觉图也在 P0 双会话中各执行 250 步、匹配 560 个有序事件。
完整 P0 离线复核命令见上文英文段落；请使用新输出文件名，避免覆盖归档结果。

### 比较层级

1. 浮点 CPU 对定点 CPU：检查数值格式的影响。
2. 定点 CPU 对 RTL：在短仿真中检查虚拟神经元状态。
3. 定点 CPU 对已编程 FPGA：检查导出的事件与计数器。

原版 P0 长求偶试验仅导出逐步群体计数；扩展事件版已完整导出三组长试验的
40,868/74,765/99,349 个有序事件，并逐条匹配独立定点 CPU。短时求偶鸣唱 raster
和视觉左侧输入试验也导出了有序事件记录。由于实验成像 ROI
与 MaleCNS 细胞之间的映射以及刺激转导尚未得到独立验证，生物学解释仍有条件限制。

### V0.3 新增的实际 100 Mbps 采集

无需连接板卡即可运行上述 `audit_100m_board_test.py` 命令，离线核对 bit 哈希、
八步计数、2,475 个有序事件、epoch/checksum、截止时间／异常标志及上传、链路、
FCS 日志摘录。使用临时输出文件可保留归档审计原样。原始采集位于
`reports/expanded_bit_100m_20261001/`。此测试是新增短试验，不算另一轮长事件
测试；实际 100 Mbps 已通过，后续 1G 测试暂缓，网线能力和具体 RGMII 故障均未证实。
