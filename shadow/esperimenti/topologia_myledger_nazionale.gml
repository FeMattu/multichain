graph [
  directed 0
  node [
    id 0
    label "HUB_NORD_Milano"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 1
    label "HUB_CENTRO_Roma"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 2
    label "HUB_SUD_Napoli"
    host_bandwidth_down "1 Gbit"
    host_bandwidth_up "1 Gbit"
  ]
  node [
    id 3
    label "Torino"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 4
    label "Venezia"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 5
    label "Firenze"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 6
    label "Perugia"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 7
    label "Bologna"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 8
    label "Bari"
    host_bandwidth_down "200 Mbit"
    host_bandwidth_up "50 Mbit"
  ]
  node [
    id 9
    label "Palermo"
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
    label "loop_Roma"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 2
    target 2
    label "loop_Napoli"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 3
    target 3
    label "loop_Torino"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 4
    target 4
    label "loop_Venezia"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 5
    target 5
    label "loop_Firenze"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 6
    target 6
    label "loop_Perugia"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 7
    target 7
    label "loop_Bologna"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 8
    target 8
    label "loop_Bari"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 9
    target 9
    label "loop_Palermo"
    latency "200 us"
    jitter "0 us"
    packet_loss 0.0
  ]
  edge [
    source 0
    target 1
    label "Milano-Roma"
    latency "3838 us"
    jitter "0 us"
    packet_loss 0.0002954
  ]
  edge [
    source 0
    target 2
    label "Milano-Napoli"
    latency "5103 us"
    jitter "0 us"
    packet_loss 0.0003315
  ]
  edge [
    source 1
    target 2
    label "Roma-Napoli"
    latency "1819 us"
    jitter "0 us"
    packet_loss 0.0002377
  ]
  edge [
    source 3
    target 0
    label "Torino-Milano"
    latency "1879 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 4
    target 0
    label "Venezia-Milano"
    latency "2707 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 5
    target 1
    label "Firenze-Roma"
    latency "2616 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 6
    target 1
    label "Perugia-Roma"
    latency "1942 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 7
    target 0
    label "Bologna-Milano"
    latency "2405 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 8
    target 2
    label "Bari-Napoli"
    latency "2544 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
  edge [
    source 9
    target 2
    label "Palermo-Napoli"
    latency "3198 us"
    jitter "0 us"
    packet_loss 0.0004000
  ]
]
