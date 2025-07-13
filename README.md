# VXLAN Demo Example with Containernet

This repository contains a Python script (`vxlan_lab.py`) that demonstrates the functionality of VXLAN (Virtual Extensible LAN). It sets up a network topology with two Virtual Tunnel Endpoints (VTEPs) and two separate LAN segments, showing how Layer 2 frames are encapsulated into IP/UDP packets to extend a virtual network across an IP transport network.

## Project Goal

The main goal of this project is to illustrate VXLAN encapsulation and transparent Layer 2 connectivity between different hosts over an IP transport network. The setup uses Linux bridges as VTEPs within Containernet and includes an advanced configuration using `ebtables` to demonstrate traffic isolation.

## Topology

The deployed topology consists of:
* **Two hosts (h1, h2)** connected to **VTEP 1 (br1)**.
* **Two hosts (h3, h4)** connected to **VTEP 2 (br2)**.
* **VTEP 1 (br1)** and **VTEP 2 (br2)** are connected via a Layer 3 (IP) transport network.
* A single VXLAN tunnel (**VNI 100**) is established between `br1` and `br2`, allowing `h1`/`h2` and `h3`/`h4` to communicate as if they were on the same Layer 2 segment.

```bash
      Host Overlay (10.0.0.0/24)          |       Transport Network (192.168.1.0/24)
                                          |
  h1 (10.0.0.1) ---+                      |                      +--- h4 (10.0.0.4)
                   |                      |                      |
                   +-- br1 (VTEP 1) ------+------ br2 (VTEP 2) --+
                   |  (192.168.1.1)       |      (192.168.1.2)   |
  h2 (10.0.0.2) ---+                      |                      +--- h3 (10.0.0.3)
                                          |                      
                 <-------------------- VXLAN Tunnel (VNI 100) ------------------->
                                                                                                          
```

## Requirements and VM Setup

To run this project, you need a virtual machine (VM) or a Linux environment with the following software pre-installed and configured:

* **Containernet**: An extension of Mininet for container-based networking.
* **Wireshark**: For detailed packet analysis.
* **Tshark**: The command-line version of Wireshark, used for preliminary packet analysis within the script.
* **Python 3**: The script is written in Python 3.

**VM Installation and Access:**
For VirtualBox, download the virtual machine image from the course-provided link. After downloading, import the appliance into VirtualBox.
* Be sure to set a proper number of CPUs and RAM for the virtual machine.
* Delete any shared folders in the shared folder settings of the virtual machine.

For better manageability, it is recommended to use your own terminal and SSH into the VM instead of running commands directly in the VM's console. To do so:
1.  Start the VM in VirtualBox.
2.  From your host machine's terminal, run:
    ```bash
    ssh -X -p 2222 vagrant@localhost
    ```
3.  The password is "vagrant".

## How to Run the Demo

1.  **Clone the repository (or copy the script) onto your VM:**
    Once logged into your VM via SSH, you can clone this repository:
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
    * Configure VTEPs (`br1`, `br2`) as Linux bridges.
    * Configure IP addresses for the transport network interfaces on VTEPs.
    * Establish the VXLAN tunnel between `br1` and `br2` with VNI 100.
    * Configure IP addresses for all hosts (`h1`, `h2`, `h3`, `h4`).
    * **Configure `ebtables` for local host isolation:** This will prevent direct Layer 2 communication between hosts connected to the *same* VTEP (e.g., `h1` and `h2`).
    * **Execute automatic tests:**
        * `ping` tests between `h1` and `h3`, and `h2` and `h4`, demonstrating Layer 2 connectivity over VXLAN. These should **succeed**.
        * `ping` tests between `h1` and `h2`, and `h3` and `h4`, demonstrating local Layer 2 isolation. These should **fail**.
    * **Capture network traffic:** `tcpdump` will capture VXLAN traffic, saving it to `/tmp/vxlan_capture.pcap`.
    * **Perform preliminary analysis:** `tshark` will analyze the captured PCAP file and print a summary of detected VXLAN VNIs.
    * Enter the **Mininet CLI**, allowing you to perform further manual tests (e.g., `h1 ping h4`, `br1 ip a`).

4.  **Exit the Mininet CLI:**
    Type `exit` and press Enter to terminate the Mininet simulation. The script will then perform a final cleanup, explicitly noting that the PCAP file has been preserved for analysis.

## Analyzing the Captured Traffic with Wireshark

After the script finishes, a packet capture file named `vxlan_capture.pcap` will be available at `/tmp/`.

To analyze the VXLAN encapsulation:

1.  **Open Wireshark on your VM or transfer the file to your host machine:**
    If your VM has a graphical desktop environment, you can open Wireshark directly from the terminal:
    ```bash
    wireshark /tmp/vxlan_capture.pcap
    ```

2.  **Inspect packet details:**
    Select any VXLAN packet and expand its details in the "Packet Details" pane. You will observe:
    * **Outer IP Header**: The IP addresses of the VTEPs (e.g., `192.168.1.1` and `192.168.1.2`).
    * **Outer UDP Header**: The source and destination UDP ports, with the destination being `4789`.
    * **VXLAN Header**: This header contains the **VNI (Virtual Network Identifier)**, which should be `100` in this case.
    * **Inner Ethernet Frame**: This is the original Layer 2 frame that was encapsulated. Its source and destination MAC addresses will be those of the hosts (e.g., `h1`'s MAC and `h3`'s MAC).
    * **Inner IP Header**: The IP addresses of the communicating hosts (e.g., `10.0.0.1` and `10.0.0.3`).
