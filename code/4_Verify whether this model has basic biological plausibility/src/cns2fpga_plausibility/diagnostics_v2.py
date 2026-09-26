"""Exploratory diagnostics. Does not alter v1's frozen model or acceptance rules."""
from __future__ import annotations

from collections import deque
from copy import copy

import numpy as np
import pandas as pd
from scipy.signal import lfilter
from scipy.sparse import csr_matrix


def cut_edges(network, mask):
    """Independent execution weights; keep CSR edge order and every uncut weight."""
    mask = np.asarray(mask)
    if mask.dtype != bool or mask.shape != network.weights.shape:
        raise ValueError("Edge mask must be boolean with one entry per IR edge")
    result = copy(network)
    result.weights = network.weights.copy()
    result.weights[mask] = 0.
    result.weight_matrix = csr_matrix((result.weights, (network.pre, network.post)),
                                     shape=(network.n, network.n))
    if not np.array_equal(result.weights[~mask], network.weights[~mask]):
        raise AssertionError("Uncut weights changed")
    return result


def edge_partitions(synapses, vpn_indices, pc_indices):
    source = synapses.pre_index.isin(vpn_indices).to_numpy()
    direct = source & synapses.post_index.isin(pc_indices).to_numpy()
    return {"cut_vPN1_to_pC1": direct, "cut_vPN1_to_other": source & ~direct,
            "cut_vPN1_all_output": source}


def anatomical_groups(neurons, synapses, groups):
    result = {key: np.asarray(value, dtype=np.int32) for key, value in groups.items()}
    direct = synapses[synapses.pre_index.isin(groups["vPN1"]) &
                      synapses.post_index.isin(groups["pC1"]) & synapses.nt_model_sign.ne(0)]
    recipient = np.unique(direct.post_index.to_numpy(np.int32))
    result["pC1_direct_vPN1_recipient"] = recipient
    result["pC1_no_direct_vPN1"] = np.setdiff1d(groups["pC1"], recipient)
    pc = neurons.iloc[groups["pC1"]]
    for label, rows in pc.groupby("type", sort=True, dropna=False):
        result[f"pC1_type:{label}"] = rows.neuron_index.to_numpy(np.int32)
    # Annotation-defined subsets, not functional selection of favorable responders.
    for label, rows in pc.groupby("fruDsx", sort=True, dropna=False):
        result[f"pC1_fruDsx:{label}"] = rows.neuron_index.to_numpy(np.int32)
    return result


def shortest_paths(synapses, n, sources, blocked=(), positive_only=False):
    """Directed reachability only: negative edges are NOT excitatory transmission."""
    forbidden = set(map(int, blocked))
    adjacency = [[] for _ in range(n)]
    active = synapses.nt_model_sign.gt(0) if positive_only else synapses.nt_model_sign.ne(0)
    for pre, post in synapses.loc[active, ["pre_index", "post_index"]].itertuples(index=False, name=None):
        if pre not in forbidden and post not in forbidden:
            adjacency[pre].append(post)
    distance = np.full(n, -1, dtype=int)
    parent = np.full(n, -1, dtype=int)
    queue = deque()
    for source in sorted(sources):
        if source not in forbidden:
            distance[source] = 0
            queue.append(int(source))
    while queue:
        pre = queue.popleft()
        for post in adjacency[pre]:
            if distance[post] < 0:
                distance[post] = distance[pre] + 1
                parent[post] = pre
                queue.append(post)
    return distance, parent


def reconstruct_path(target, distance, parent):
    if distance[target] < 0:
        return []
    path = [int(target)]
    while parent[path[-1]] >= 0:
        path.append(int(parent[path[-1]]))
    return path[::-1]


def population_counts(times, indices, members, duration):
    selected = np.isin(indices, members)
    return np.bincount(times[selected], minlength=duration).astype(np.int64)


def filtered_proxy(counts, dt_ms, rise_ms, decay_ms):
    """Causal double exponential with unit single-spike peak, arbitrary units.

    This is linear spike filtering, NOT a calcium/fluorescence forward model.
    No saturation, compartment kinetics or expression calibration is available.
    """
    if not (0 < dt_ms and 0 < rise_ms < decay_ms):
        raise ValueError("Require dt > 0 and 0 < rise < decay")
    if not np.isfinite([dt_ms, rise_ms, decay_ms]).all():
        raise ValueError("Kernel parameters must be finite")
    t_peak = rise_ms * decay_ms / (decay_ms - rise_ms) * np.log(decay_ms / rise_ms)
    scale = np.exp(-t_peak / decay_ms) - np.exp(-t_peak / rise_ms)
    slow = lfilter([1.], [1., -np.exp(-dt_ms / decay_ms)], counts)
    fast = lfilter([1.], [1., -np.exp(-dt_ms / rise_ms)], counts)
    return (slow - fast) / scale


def observation_metrics(counts, size, condition, windows_ms, kernels):
    if size <= 0:
        raise ValueError("Do not score an empty anatomical group")
    rows = []
    evoked = np.asarray(counts[condition.start:condition.response_end], dtype=float) / size
    for width in windows_ms:
        steps = int(round(width / condition.dt_ms))
        if not np.isclose(steps * condition.dt_ms, width) or not 0 < steps <= len(evoked):
            raise ValueError("Rolling window must be an integer number of steps within response")
        total = np.r_[0., np.cumsum(evoked)]
        peak = float((total[steps:] - total[:-steps]).max() / (steps * condition.dt_ms / 1000.))
        rows.append(dict(metric=f"rolling_{width:g}ms_hz", value=peak, unit="Hz/neuron",
                         peak_after_response_window=False))
    rows.append(dict(metric="spikes_per_neuron_per_pulse", value=float(evoked.sum()/len(condition.onsets)),
                     unit="spikes/neuron/pulse", peak_after_response_window=False))
    for kernel in kernels:
        # Pad beyond the response window to detect a delayed observation peak.
        # Input to the proxy is explicitly the response-window spike train only.
        pad = int(np.ceil(5 * kernel["decay_ms"] / condition.dt_ms))
        values = filtered_proxy(np.pad(evoked, (0, pad)), condition.dt_ms, **kernel)
        peak_index = int(np.argmax(values))
        rows.append(dict(metric=f"proxy_r{kernel['rise_ms']:g}_d{kernel['decay_ms']:g}",
                         value=float(values.max()), unit="uncalibrated AU/neuron",
                         peak_after_response_window=peak_index >= len(evoked)))
    return rows


def readout_directions(table, tolerance):
    """Every declared readout/subgroup is reported; no best-kernel selection."""
    rows = []
    for (group, metric), data in table.groupby(["group", "metric"], sort=True):
        values = data.set_index("ipi_ms").value
        for rule, comparators in [("short_15_25", [15., 25.]), ("long_85_95", [85., 95.])]:
            differences = [float(values.loc[35.] - values.loc[ipi]) for ipi in comparators]
            rows.append(dict(group=group, metric=metric, comparison=rule,
                             supported=all(value > tolerance for value in differences),
                             minimum_margin=min(differences), reference_value=float(values.loc[35.]),
                             reference_above_zero=bool(values.loc[35.] > tolerance)))
    return pd.DataFrame(rows)
