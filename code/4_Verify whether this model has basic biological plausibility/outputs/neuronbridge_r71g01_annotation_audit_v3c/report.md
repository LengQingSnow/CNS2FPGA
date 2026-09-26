# R71G01 NeuronBridge 全量注释与提取路径审计（v3c）

**结论：18 份搜索表在补全 MaleCNS v1.0 注释后检出 148 个 pC1；107 个已在冻结子图，41 个在子图外。`10217` 不是唯一 pC1 候选。**

全部 21,930 条 MaleCNS v0.9 结果、2,797 个唯一 bodyId 都能按相同 bodyId 对上固定的 v1.0 注释表；未匹配行数为 0。补全后得到 1,372 条 pC1 命中、148 个唯一 pC1。早先只检查 CSV 自带 `Neuron Type` 会漏掉大多数通道，因为部分导出没有该列。

## 排名靠前的 pC1

| bodyId | type | instance | appearances | best_rank | best_score | in_frozen_ir |
| --- | --- | --- | --- | --- | --- | --- |
| 19948 | pC1_3c | pC1_3c_R | 12 | 3 | 23797.436 | True |
| 12442 | pC1_4a | pC1_4a_L | 12 | 6 | 19291.691 | True |
| 522419 | pC1_4a | pC1_4a_L | 12 | 20 | 18494.846 | True |
| 18017 | pC1_3c | pC1_3c_L | 12 | 20 | 18007.438 | True |
| 20117 | pC1_4a | pC1_4a_R | 12 | 21 | 17648.94 | True |
| 514925 | pC1_3b | pC1_3b_R | 12 | 25 | 15767.622 | False |
| 12448 | pC1_18a | pC1_18a_L | 12 | 30 | 15485.283 | True |
| 19894 | pC1_3c | pC1_3c_R | 12 | 32 | 14177.881 | False |
| 19650 | pC1_3a | pC1_3a_L | 12 | 36 | 13624.339 | True |
| 20803 | pC1_4a | pC1_4a_R | 12 | 40 | 14422.22 | True |
| 58786 | pC1_16b | pC1_16b_R | 12 | 40 | 13231.04 | False |
| 29143 | pC1_5b | pC1_5b_R | 12 | 52 | 10972.244 | True |

`best_rank` 是每份导出内部名次，`best_score` 是 NeuronBridge 搜索分数。两者用于排序和复查，不是校准后的置信概率。R71G01 单独的 MCFO 结果也不能直接定义 R71G01∩dsx 交集或钙成像 ROI。

## 为什么 10217 不在当前子图

`10217 / pC1x_b` 符合第二步 `^pC1` relay 选择器。从 JO-A/JO-B 输入到它的最短距离为 3 跳，从它到 pIP10/pMP2 输出的最短距离为 2 跳，总计 5 跳。冻结规则要求总距离 ≤ 4，因此其排除原因是 `distance_sum_exceeds_limit`。

完整 v1.0 注释共有 156 个 `^pC1`：112 个进入冻结 IR，44 个因总距离超过限制被排除；没有 pC1 因单向不可达被排除。当前阈值为每条聚合边至少 5 个突触。

## 工程决定

现有模型已经覆盖多数搜索命中的 pC1，包括排名最靠前的一批。仅凭 `10217` 的第 1466 名最佳命中，没有依据单独把它加入网络。若以后要测试第五跳 pC1，应建立 max_hops=5 的独立子图版本并重新计算规模、BRAM 和全部 Golden Model 结果。

## 产物

- `all_malecns_hits_enriched.csv`：全部 MaleCNS 命中及 v1.0 注释、冻结 IR 成员关系。
- `pc1_search_candidate_summary.csv`：148 个 pC1 的跨文件汇总。
- `all_pc1_extraction_status.csv`：156 个 v1.0 pC1 的输入/输出距离和排除原因。
- `per_file_coverage.csv`：18 份导出的覆盖情况。
- lock: `365723e1154416bfb049a942095d87adb96578d0219928ee5d007f5a09b408bc`。