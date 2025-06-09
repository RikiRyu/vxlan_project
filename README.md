This repository contains a Python script (`vxlan_lab.py`) that demonstrates the functionality of VXLAN (Virtual Extensible LAN) using Containernet. It sets up a network topology with two Virtual Tunnel Endpoints (VTEPs) and two separate LAN segments, showing how Layer 2 frames are encapsulated into IP/UDP packets to extend a virtual network across an IP transport network.

## Project Goal

The main goal of this project is to illustrate VXLAN encapsulation and transparent Layer 2 connectivity between different hosts over an IP transport network. The setup uses Linux bridges as VTEPs within Containernet.

## Topology

The deployed topology consists of:
* **Two hosts (h1, h2)** connected to **VTEP 1 (br1)**.
* **Two hosts (h3, h4)** connected to **VTEP 2 (br2)**.
* **VTEP 1 (br1)** and **VTEP 2 (br2)** are connected via a Layer 3 (IP) transport network.
* A single VXLAN tunnel (VNI 100) is established between br1 and br2, allowing h1/h2 and h3/h4 to communicate as if they were on the same Layer 2 segment.

```
  h1 ----+                  +---- h3
         |                  |
  h2 ----+---- [br1] ----- [br2] ----+---- h4
               (VTEP 1)     (VTEP 2)  |
                     \      /         |
                      \    /          |
                   IP Transport       +---- (Other LAN segments)
                      Network
```

## Requirements

To run this lab, you need a virtual machine (VM) or a Linux environment with the following software installed:

* **Containernet**: An extension of Mininet for container-based networking.
* **Wireshark**: For detailed packet analysis.
* **Tshark**: The command-line version of Wireshark, used for preliminary packet analysis within the script.
* **iperf**: For performance testing (throughput measurement).
* **Python 3**: The script is written in Python 3.

## How to Run the Lab

1.  **Clone the repository (or copy the script):**
    ```bash
    git clone [https://github.com/RikiRyu/vxlan_project.git](https://github.com/RikiRyu/vxlan_project.git)
    cd vxlan_project
    ```

2.  **Execute the script:**
    Run the Python script with `sudo` privileges:
    ```bash
    sudo python3 vxlan_lab.py
    ```

3.  **Observe the output:**
    The script will perform the following actions, with informative messages displayed in your terminal:
    * Clean up any previous Mininet instances.
    * Set up the Containernet topology.
    * Configure VTEPs (br1, br2) as Linux bridges.
    * Configure IP addresses for the transport network interfaces on VTEPs.
    * Establish the VXLAN tunnel between br1 and br2 with VNI 100.
    * Configure IP addresses for all hosts (h1, h2, h3, h4).
    * **Execute automatic tests:**
        * `ping` tests between h1 and h3, and h2 and h4, demonstrating Layer 2 connectivity over VXLAN.
        * An `iperf` TCP test between h1 and h3 to show data throughput.
    * **Capture network traffic:** `tcpdump` will capture VXLAN traffic on the `br1-eth2` (transport) interface, saving it to `/tmp/vxlan_outer.pcap`.
    * **Perform preliminary analysis:** `tshark` will analyze the captured PCAP file and print a summary of detected VXLAN VNIs and an example packet dissection directly in the terminal.
    * Enter the **Mininet CLI**, allowing you to perform further manual tests (e.g., `h1 ping h4`, `br1 ip a`, `br2 brctl show`).

4.  **Exit the Mininet CLI:**
    Type `exit` and press Enter to terminate the Mininet simulation. The script will then perform a final cleanup.

## Analyzing the Captured Traffic with Wireshark

After the script finishes, a packet capture file named `vxlan_outer.pcap` will be available at `/tmp/vxlan_outer.pcap`.

To analyze the VXLAN encapsulation:

1.  **Open Wireshark:**
    ```bash
    wireshark /tmp/vxlan_outer.pcap
    ```
2.  **Apply a display filter:**
    In the Wireshark filter bar, type `vxlan` or `udp.port == 4789` and press Enter. This will show only the VXLAN encapsulated packets.

3.  **Inspect packet details:**
    Select any VXLAN packet and expand its details in the "Packet Details" pane. You will observe:
    * **Outer IP Header**: The IP addresses of the VTEPs (e.g., 192.168.1.1 and 192.168.1.2).
    * **Outer UDP Header**: The source and destination UDP ports, with the destination typically being 4789 (the standard VXLAN port).
    * **VXLAN Header**: This header contains the VNI (Virtual Network Identifier, which should be `100` in our case) and other flags.
    * **Inner Ethernet Frame**: This is the original Layer 2 frame (e.g., ARP requests, ICMP echo requests/replies, or TCP segments from iperf) that was encapsulated. Its source and destination MAC addresses will be those of the hosts (e.g., h1's MAC and h3's MAC).
    * **Inner IP Header**: The IP addresses of the communicating hosts (e.g., 10.0.0.1 and 10.0.0.3).

This detailed dissection in Wireshark visually confirms how VXLAN effectively tunnels Layer 2 traffic over a Layer 3 network.