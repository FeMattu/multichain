graph [
  directed 0
  node [
    id 0
    label "HUB_TOSCANA_Firenze"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 1
    label "HUB_LIGURIA_Genova"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 2
    label "HUB_EMILIAROMAGNA_Bologna"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 3
    label "Pisa"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 4
    label "Siena"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 5
    label "La_Spezia"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 6
    label "Savona"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 7
    label "Modena"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 8
    label "Parma"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 9
    label "Ravenna"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  edge [
    source 0
    target 0
    label "loop_Firenze"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 1
    target 1
    label "loop_Genova"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 2
    target 2
    label "loop_Bologna"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 3
    target 3
    label "loop_Pisa"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 4
    target 4
    label "loop_Siena"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 5
    target 5
    label "loop_La_Spezia"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 6
    target 6
    label "loop_Savona"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 7
    target 7
    label "loop_Modena"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 8
    target 8
    label "loop_Parma"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 9
    target 9
    label "loop_Ravenna"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 0
    target 1
    label "Firenze-Genova"
    latency "1883 us"
    jitter "0 us"
    packet_loss 0.0002395
  ]
  edge [
    source 0
    target 2
    label "Firenze-Bologna"
    latency "1067 us"
    jitter "0 us"
    packet_loss 0.0002162
  ]
  edge [
    source 1
    target 2
    label "Genova-Bologna"
    latency "1833 us"
    jitter "0 us"
    packet_loss 0.0002381
  ]
  edge [
    source 3
    target 0
    label "Pisa-Firenze"
    latency "1482 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 4
    target 0
    label "Siena-Firenze"
    latency "1353 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 5
    target 1
    label "La_Spezia-Genova"
    latency "1543 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 6
    target 1
    label "Savona-Genova"
    latency "1272 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 7
    target 2
    label "Modena-Bologna"
    latency "1260 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 8
    target 2
    label "Parma-Bologna"
    latency "1610 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 9
    target 2
    label "Ravenna-Bologna"
    latency "1482 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
]
