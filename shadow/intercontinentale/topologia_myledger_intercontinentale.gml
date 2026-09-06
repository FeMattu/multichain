graph [
  directed 0
  node [
    id 0
    label "HUB_IT_Milano"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 1
    label "HUB_DE_Frankfurt"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 2
    label "HUB_US_New_York"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 3
    label "Zurich"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 4
    label "Marseille"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 5
    label "Amsterdam"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 6
    label "Warszawa"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 7
    label "Paris"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 8
    label "London"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 9
    label "Toronto"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  edge [
    source 0
    target 0
    label "loop_Milano"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 1
    target 1
    label "loop_Frankfurt"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 2
    target 2
    label "loop_New_York"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 3
    target 3
    label "loop_Zurich"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 4
    target 4
    label "loop_Marseille"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 5
    target 5
    label "loop_Amsterdam"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 6
    target 6
    label "loop_Warszawa"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 7
    target 7
    label "loop_Paris"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 8
    target 8
    label "loop_London"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 9
    target 9
    label "loop_Toronto"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 0
    target 1
    label "Milano-Frankfurt"
    latency "4127 us"
    jitter "0 us"
    packet_loss 0.0003036
  ]
  edge [
    source 0
    target 2
    label "Milano-New_York"
    latency "45750 us"
    jitter "0 us"
    packet_loss 0.0014929
  ]
  edge [
    source 1
    target 2
    label "Frankfurt-New_York"
    latency "43919 us"
    jitter "0 us"
    packet_loss 0.0014405
  ]
  edge [
    source 3
    target 0
    label "Zurich-Milano"
    latency "2529 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 4
    target 0
    label "Marseille-Milano"
    latency "3713 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 5
    target 1
    label "Amsterdam-Frankfurt"
    latency "3544 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 6
    target 1
    label "Warszawa-Frankfurt"
    latency "7231 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 7
    target 1
    label "Paris-Frankfurt"
    latency "4345 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 8
    target 1
    label "London-Frankfurt"
    latency "5464 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 9
    target 2
    label "Toronto-New_York"
    latency "4853 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
]
