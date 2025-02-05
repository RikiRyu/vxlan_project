
# VXLAN Lab Implementation

This project demonstrates VXLAN (Virtual Extensible LAN) functionality using ComNetEmu. It creates a network topology with two segments connected via VXLAN tunneling and shows the encapsulation process through packet analysis.

## Network Topology Details

1. Network Segments Configuration:
   - Subnet: 10.0.0.0/24
   - First Segment:
     - h1 (10.0.0.1)
     - h2 (10.0.0.2)
     - Connected to br1 (VTEP1)
   - Second Segment:
     - h3 (10.0.0.3)
     - h4 (10.0.0.4)
     - Connected to br2 (VTEP2)

2. VXLAN Tunnel Configuration:
   - Transport Network: 192.168.1.0/24
   - VTEP1 (br1): 192.168.1.1
   - VTEP2 (br2): 192.168.1.2
   - VNI (VXLAN Network Identifier): 100
   - UDP Port: 4789 (Standard VXLAN port)
   - MTU: 1500 bytes (effective payload ~1400 bytes due to VXLAN overhead)
   
## Requirements

- ComNetEmu installed in a virtual machine (https://drive.google.com/drive/folders/1FP5Bx2DHp7oV57Ja38_x01ABiw3wK11M?usp=string)
- Oracle VM VirtualBox
- Wireshark for packet analysis
- Python 3
- SSH access to VM (default: ssh -X -p 2222 vagrant@localhost)

## Installation and Setup

1. Connect to your VM:
```bash
ssh -X -p 2222 vagrant@localhost
```

2. Create and save the Python script (vxlan_lab.py)
```bash
nano vxlan_lab.py
# Copy and paste the script content
# Save with Ctrl+O, exit with Ctrl+X
```

## Running the Demo

1. Execute the script:
```bash
sudo python3 vxlan_lab.py
```

2. Test basic connectivity:
```bash
mininet> h1 ping h3
```

3. Test MTU limitations:
```bash
mininet> h1 ping -s 1400 h3  # Should work
mininet> h1 ping -s 1500 h3  # Should fail due to VXLAN overhead
```

## Packet Analysis

The script automatically captures packets in `/tmp/vxlan_outer.pcap`. To analyze:
1. Exit the Mininet CLI (`exit` command)
2. Open the capture file in Wireshark
3. Look for:
   - VXLAN encapsulation (UDP port 4789)
   - Outer Headers:
     - Source IP: 192.168.1.1 (br1)
     - Destination IP: 192.168.1.2 (br2)
     - UDP destination port: 4789
   - Inner Headers:
     - Original source IP (10.0.0.x)
     - Original destination IP (10.0.0.x)
     - Original payload

## Key Findings

1. VXLAN Encapsulation:
   - Successfully encapsulates Layer 2 frames in UDP/IP
   - Adds 50 bytes overhead

2. MTU Behavior:
   - Packets up to ~1400 bytes work correctly
   - Larger packets fail due to VXLAN overhead
   - Demonstrates importance of MTU considerations in VXLAN deployments

3. Network Segmentation:
   - Different subnets successfully communicate
   - VXLAN provides Layer 2 connectivity over Layer 3

## Troubleshooting

If you encounter connectivity issues:
1. Clean up Mininet: `sudo mn -c`
2. Verify interface states with `ip link show`
3. Check VXLAN interface: `ip -d link show vxlan0`
4. Ensure tcpdump is not already running