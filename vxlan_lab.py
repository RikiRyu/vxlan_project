import os
import subprocess
import time

from comnetsemu.net import Containernet
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

# --- CONFIGURATION PARAMETERS ---
H1_IP = '10.0.0.1/24'
H2_IP = '10.0.0.2/24'
H3_IP = '10.0.0.3/24'
H4_IP = '10.0.0.4/24'
BR1_TRANSPORT_IP = '192.168.1.1'
BR2_TRANSPORT_IP = '192.168.1.2'
TRANSPORT_SUBNET = '24'
VXLAN_VNI = 100
VXLAN_DST_PORT = 4789
PCAP_FILE = '/tmp/vxlan_capture.pcap'

def cleanup():
    """Cleans up previous Mininet instances, temporary files, and processes."""
    info("*** Cleaning up old Mininet instances and temporary files...\n")
    subprocess.run(['mn', '-c'], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(PCAP_FILE):
        try:
            os.remove(PCAP_FILE)
            info(f"  Removed old PCAP file: {PCAP_FILE}\n")
        except OSError as e:
            info(f"  Error removing PCAP file: {e}\n")
    subprocess.run(['pkill', '-f', 'tcpdump'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def create_vxlan_topo():
    """Main function to create and test the VXLAN topology."""
    cleanup()
    net = Containernet(controller=Controller, link=TCLink)
    net.addController('c0')

    info("*** Adding hosts and VTEPs...\n")
    h1, h2 = net.addHost('h1'), net.addHost('h2')
    h3, h4 = net.addHost('h3'), net.addHost('h4')
    br1, br2 = net.addHost('br1'), net.addHost('br2')

    info("*** Adding network links...\n")
    net.addLink(h1, br1); net.addLink(h2, br1)
    net.addLink(h3, br2); net.addLink(h4, br2)
    net.addLink(br1, br2)

    info("*** Starting network...\n")
    net.start()

    info("*** Detecting transport interfaces dynamically...\n")
    connection = br1.connectionsTo(br2)[0]
    transport_if_br1 = connection[0].name
    transport_if_br2 = connection[1].name
    info(f"  Detected -> br1: {transport_if_br1}, br2: {transport_if_br2}\n")

    info("*** Configuring VTEPs and VXLAN tunnel...\n")
    for br_node, transport_if, transport_ip in [(br1, transport_if_br1, BR1_TRANSPORT_IP), (br2, transport_if_br2, BR2_TRANSPORT_IP)]:
        br_node.cmd('ip link add name br0 type bridge')
        br_node.cmd('ip link set br0 up')
        br_node.cmd(f'ip addr add {transport_ip}/{TRANSPORT_SUBNET} dev {transport_if}')
        br_node.cmd(f'ip link set {br_node.name}-eth0 master br0')
        br_node.cmd(f'ip link set {br_node.name}-eth1 master br0')

    br1.cmd(f'ip link add vxlan{VXLAN_VNI} type vxlan id {VXLAN_VNI} remote {BR2_TRANSPORT_IP} local {BR1_TRANSPORT_IP} dstport {VXLAN_DST_PORT} dev {transport_if_br1}')
    br2.cmd(f'ip link add vxlan{VXLAN_VNI} type vxlan id {VXLAN_VNI} remote {BR1_TRANSPORT_IP} local {BR2_TRANSPORT_IP} dstport {VXLAN_DST_PORT} dev {transport_if_br2}')

    for br_node in [br1, br2]:
        br_node.cmd(f'ip link set vxlan{VXLAN_VNI} master br0')
        br_node.cmd(f'ip link set vxlan{VXLAN_VNI} up')

    info("*** Configuring host IP addresses...\n")
    h1.cmd(f'ip addr add {H1_IP} dev h1-eth0')
    h2.cmd(f'ip addr add {H2_IP} dev h2-eth0')
    h3.cmd(f'ip addr add {H3_IP} dev h3-eth0')
    h4.cmd(f'ip addr add {H4_IP} dev h4-eth0')

    info("*** Configuring ebtables for local host isolation...\n")
    br1.cmd('ebtables -A FORWARD -i br1-eth0 -o br1-eth1 -j DROP')
    br1.cmd('ebtables -A FORWARD -i br1-eth1 -o br1-eth0 -j DROP')
    br2.cmd('ebtables -A FORWARD -i br2-eth0 -o br2-eth1 -j DROP')
    br2.cmd('ebtables -A FORWARD -i br2-eth1 -o br2-eth0 -j DROP')

    info("\n*** Starting automated tests and traffic capture...\n")
    br1.cmd(f'tcpdump -i {transport_if_br1} -w {PCAP_FILE} "udp port {VXLAN_DST_PORT}" &')
    time.sleep(1)

    info(">>> Test 1: Pinging across VXLAN tunnel (SHOULD work).\n")
    ping_cmd_h1_h3 = f'ping -c 2 {H3_IP.split("/")[0]}'
    result_h1_h3 = h1.cmd(ping_cmd_h1_h3)
    info(f"  Pinging h1 -> h3...\n{result_h1_h3}\n")

    ping_cmd_h2_h4 = f'ping -c 2 {H4_IP.split("/")[0]}'
    result_h2_h4 = h2.cmd(ping_cmd_h2_h4)
    info(f"  Pinging h2 -> h4...\n{result_h2_h4}\n")

    info(">>> Test 2: Pinging locally isolated hosts (SHOULD FAIL).\n")
    ping_cmd_h1_h2 = f'ping -c 2 {H2_IP.split("/")[0]}'
    result_h1_h2 = h1.cmd(ping_cmd_h1_h2)
    info(f"  Pinging h1 -> h2...\n{result_h1_h2}\n")
    
    ping_cmd_h3_h4 = f'ping -c 2 {H4_IP.split("/")[0]}'
    result_h3_h4 = h3.cmd(ping_cmd_h3_h4)
    info(f"  Pinging h3 -> h4...\n{result_h3_h4}\n")

    time.sleep(1); br1.cmd('pkill tcpdump')
    info(f"\n*** Packet capture complete. File saved to {PCAP_FILE}\n")

    info("*** Performing preliminary analysis with tshark...\n")
    try:
        # Quick analysis: Count captured VNIs
        vni_count_cmd = f'tshark -r {PCAP_FILE} -Y "vxlan" -T fields -e vxlan.vni | sort | uniq -c'
        vni_count_output = subprocess.check_output(vni_count_cmd, shell=True, stderr=subprocess.STDOUT).decode()
        info(f"  Count of captured VXLAN VNIs:\n{vni_count_output}")

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        info(f"  Could not run tshark analysis. Is it installed? Error: {e}\n")

    info("*** Starting Mininet CLI. Type 'exit' to quit.\n")
    CLI(net)
    net.stop()
    info(f"*** Simulation finished. The PCAP file '{PCAP_FILE}' was NOT removed for your analysis.\n")
    info("    You can manually clean up with 'sudo mn -c' when finished.\n")

if __name__ == '__main__':
    setLogLevel('info')
    create_vxlan_topo()