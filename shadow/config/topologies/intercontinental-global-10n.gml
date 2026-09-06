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
    label "HUB_ES_Madrid"
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
    label "HUB_SG_Singapore"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 4
    label "HUB_BR_Sao_Paulo"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 5
    label "Frankfurt"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 6
    label "Amsterdam"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 7
    label "Tokyo"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 8
    label "Toronto"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 9
    label "Johannesburg"
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
    label "loop_Madrid"
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
    label "loop_Singapore"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 4
    target 4
    label "loop_Sao_Paulo"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 5
    target 5
    label "loop_Frankfurt"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 6
    target 6
    label "loop_Amsterdam"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 7
    target 7
    label "loop_Tokyo"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 8
    target 8
    label "loop_Toronto"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 9
    target 9
    label "loop_Johannesburg"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 0
    target 1
    label "Milano-Madrid"
    latency "8818 us"
    jitter "0 us"
    packet_loss 0.0004376
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
    source 0
    target 3
    label "Milano-Singapore"
    latency "72327 us"
    jitter "0 us"
    packet_loss 0.0022522
  ]
  edge [
    source 0
    target 4
    label "Milano-Sao_Paulo"
    latency "67144 us"
    jitter "0 us"
    packet_loss 0.0021041
  ]
  edge [
    source 1
    target 2
    label "Madrid-New_York"
    latency "40876 us"
    jitter "0 us"
    packet_loss 0.0013536
  ]
  edge [
    source 1
    target 3
    label "Madrid-Singapore"
    latency "80165 us"
    jitter "0 us"
    packet_loss 0.0024762
  ]
  edge [
    source 1
    target 4
    label "Madrid-Sao_Paulo"
    latency "59193 us"
    jitter "0 us"
    packet_loss 0.0018769
  ]
  edge [
    source 2
    target 3
    label "New_York-Singapore"
    latency "107827 us"
    jitter "0 us"
    packet_loss 0.0032665
  ]
  edge [
    source 2
    target 4
    label "New_York-Sao_Paulo"
    latency "54299 us"
    jitter "0 us"
    packet_loss 0.0017371
  ]
  edge [
    source 3
    target 4
    label "Singapore-Sao_Paulo"
    latency "112409 us"
    jitter "0 us"
    packet_loss 0.0033974
  ]
  edge [
    source 5
    target 0
    label "Frankfurt-Milano"
    latency "4627 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 6
    target 0
    label "Amsterdam-Milano"
    latency "6801 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 7
    target 3
    label "Tokyo-Singapore"
    latency "38179 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 8
    target 2
    label "Toronto-New_York"
    latency "4853 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 9
    target 4
    label "Johannesburg-Sao_Paulo"
    latency "53005 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
]
