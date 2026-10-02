# P0 host Ethernet observation (30 September 2026)

During the detached two-session P0 board campaign, a read-only Windows
`Get-NetAdapter -InterfaceIndex 23` query reported the Realtek "以太网"
adapter as `Up` with `LinkSpeed: 1 Gbps`. A separate read-only
`Get-NetIPAddress -InterfaceIndex 23 -AddressFamily IPv4` query showed both
`192.168.1.10/24` (temporary board-test address) and the original
`192.168.0.3/24`; neither was marked `SkipAsSource`.

This is a host-reported negotiated link speed observed during the test, not a
measured application throughput or proof that every packet in both sessions
was sent while the link remained at that speed. The earlier 28 September
upload run was separately observed at 100 Mbps and must not be silently
merged with this observation. The campaign's host-inclusive image upload
durations, if both sessions pass, are recorded separately in
`campaign_summary.json`.
