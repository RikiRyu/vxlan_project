# Import required libraries
# Containernet: Extended Mininet for container networking
from comnetsemu.net import Containernet
# Controller: Basic SDN controller
from mininet.node import Controller
# TCLink: Links with bandwidth/delay/loss parameters
from mininet.link import TCLink
# CLI: Command line interface for Mininet
from mininet.cli import CLI
# Logging utilities
from mininet.log import info, setLogLevel
# For running system commands
import subprocess
import time
import os # Import for path manipulation and file existence checks

# --- CONFIGURATION PARAMETERS ---
# Subnet for hosts in virtual LAN segments
HOST_SUBNET = '10.0.0.0/24'
# IP addresses for hosts
H1_IP = '10.0.0.1/24'
H2_IP = '10.0.0.2/24'
H3_IP = '10.0.0.3/24'
H4_IP = '10.0.0.4/24'
# IP addresses for VTEPs (br1 and br2) for the transport network
BR1_TRANSPORT_IP = '192.168.1.1/24'
BR2_TRANSPORT_IP = '192.168.1.2/24'
# Virtual Network Identifier (VNI) for VXLAN
VXLAN_VNI = 100
# Standard UDP port for VXLAN
VXLAN_DST_PORT = 4789
# Names of transport interfaces on VTEPs
BR1_TRANSPORT_IF = 'br1-eth2'
BR2_TRANSPORT_IF = 'br2-eth2'
# Path for the tcpdump capture file
PCAP_FILE = '/tmp/vxlan_outer.pcap'
# Duration of tcpdump capture for automatic tests (can be short for pings)
CAPTURE_DURATION_SECONDS = 5

# Cleanup function to remove old Mininet instances and pcap files
def cleanup():
   info("*** Cleaning up old Mininet instances and temporary files...\n")
   try:
       subprocess.run(['mn', '-c'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
       info("  Mininet cleaned.\n")
   except subprocess.CalledProcessError as e:
       info(f"  Error during Mininet cleanup (may not be an active instance): {e.stderr.decode().strip()}\n")
   except FileNotFoundError:
       info("  'mn' command not found. Ensure Mininet is installed and in PATH.\n")

   if os.path.exists(PCAP_FILE):
       try:
           os.remove(PCAP_FILE)
           info(f"  PCAP file {PCAP_FILE} removed.\n")
       except OSError as e:
           info(f"  Error removing PCAP file {PCAP_FILE}: {e}\n")

   # Ensure tcpdump is terminated if still running
   subprocess.run(['pkill', '-f', 'tcpdump -i br1-eth2'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   info("  Tcpdump processes terminated (if active).\n")

   # Clean up ebtables rules
   info("  Cleaning up ebtables rules...\n")
   for br in ['br1', 'br2']:
       for table in ['filter', 'nat', 'broute']:
           try:
               subprocess.run([f'./{br}/sbin/ebtables', '-t', table, '-F'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
               subprocess.run([f'./{br}/sbin/ebtables', '-t', table, '-X'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
           except FileNotFoundError:
               # ebtables not found in container, ignore
               pass
           except Exception as e:
               info(f"    Warning: Could not flush ebtables on {br} (table {table}): {e}\n")


# Main topology creation function
def create_vxlan_topo():
   # Clean any existing Mininet setup
   cleanup()
   info("*** Creating Containernet network...\n")
   net = Containernet(controller=Controller, link=TCLink)
   net.addController('c0')

   # Create hosts (h1-h4) and bridges (br1-br2)
   # These will form two network segments connected by VXLAN
   info("*** Adding hosts and VTEPs (Linux bridges)...\n")
   h1 = net.addHost('h1')
   h2 = net.addHost('h2')
   h3 = net.addHost('h3')
   h4 = net.addHost('h4')
   br1 = net.addHost('br1')  # VTEP 1
   br2 = net.addHost('br2')  # VTEP 2

   # Create network links:
   # h1,h2 -> br1 (first segment)
   # h3,h4 -> br2 (second segment)
   # br1 <-> br2 (transport network)
   info("*** Adding network links...\n")
   net.addLink(h1, br1) # h1-eth0 -> br1-eth0
   net.addLink(h2, br1) # h2-eth0 -> br1-eth1
   net.addLink(h3, br2) # h3-eth0 -> br2-eth0
   net.addLink(h4, br2) # h4-eth0 -> br2-eth1
   net.addLink(br1, br2) # br1-eth2 -> br2-eth2 (Transport interface between VTEPs)

   # Start network
   info("*** Starting network...\n")
   net.start()

   info("*** Configuring Linux bridges on VTEP nodes...\n")
   for br in [br1, br2]:
       # Crea un bridge Linux (br0) che fungerà da punto di aggregazione per le interfacce LAN e VXLAN
       br.cmd('ip link add br0 type bridge')
       br.cmd('ip link set br0 up')
       # Assegna un IP al bridge, anche se gli host useranno i propri IP, utile per debugging sui VTEP
       br.cmd(f'ip addr add {HOST_SUBNET.split("/")[0]}254/24 dev br0') # Es: 10.0.0.254/24

   info("*** Configuring IP addresses for the transport network (VXLAN tunnel)...\n")
   # Assegna gli IP alle interfacce fisiche che formano la rete di trasporto tra i VTEP
   br1.cmd(f'ip addr add {BR1_TRANSPORT_IP} dev {BR1_TRANSPORT_IF}')
   br2.cmd(f'ip addr add {BR2_TRANSPORT_IP} dev {BR2_TRANSPORT_IF}')

   info(f"*** Configuring VXLAN interfaces (VNI={VXLAN_VNI}, Dest Port={VXLAN_DST_PORT})...\n")
   # Crea l'interfaccia VXLAN su br1, puntando a br2
   br1.cmd(f'ip link add vxlan0 type vxlan id {VXLAN_VNI} remote {BR2_TRANSPORT_IP.split("/")[0]} local {BR1_TRANSPORT_IP.split("/")[0]} dstport {VXLAN_DST_PORT} dev {BR1_TRANSPORT_IF}')
   # Crea l'interfaccia VXLAN su br2, puntando a br1
   br2.cmd(f'ip link add vxlan0 type vxlan id {VXLAN_VNI} remote {BR1_TRANSPORT_IP.split("/")[0]} local {BR2_TRANSPORT_IP.split("/")[0]} dstport {VXLAN_DST_PORT} dev {BR2_TRANSPORT_IF}')
   br1.cmd('ip link set vxlan0 up')
   br2.cmd('ip link set vxlan0 up')

   info("*** Adding host and VXLAN interfaces to Linux bridges...\n")
   # Add physical interfaces (to hosts) and the VXLAN interface to the logical bridge br0
   # br1
   br1.cmd('ip link set br1-eth0 master br0') # Interface to h1
   br1.cmd('ip link set br1-eth1 master br0') # Interface to h2
   br1.cmd('ip link set vxlan0 master br0')
   # br2
   br2.cmd('ip link set br2-eth0 master br0') # Interface to h3
   br2.cmd('ip link set br2-eth1 master br0') # Interface to h4
   br2.cmd('ip link set vxlan0 master br0')

   info("*** Configuring host IP addresses...\n")
   h1.cmd(f'ip addr add {H1_IP} dev h1-eth0')
   h2.cmd(f'ip addr add {H2_IP} dev h2-eth0')
   h3.cmd(f'ip addr add {H3_IP} dev h3-eth0')
   h4.cmd(f'ip addr add {H4_IP} dev h4-eth0')

   # --- CONFIGURE EBTABLES FOR LOCAL ISOLATION (BONUS FEATURE) ---
   info("\n*** Configuring ebtables on VTEPs for local host isolation (bonus feature)...\n")
   info("    This will prevent h1-h2 and h3-h4 local communication but allow h1-h3 (via VXLAN).\n")

   # On br1: Prevent br1-eth0 and br1-eth1 from talking directly
   # -A FORWARD: Appends rule to FORWARD chain
   # -i br1-eth0 -o br1-eth1: Traffic from eth0 to eth1
   # -j DROP: Drop the traffic
   # We need rules in both directions
   br1.cmd('ebtables -A FORWARD -i br1-eth0 -o br1-eth1 -j DROP')
   br1.cmd('ebtables -A FORWARD -i br1-eth1 -o br1-eth0 -j DROP')

   # On br2: Prevent br2-eth0 and br2-eth1 from talking directly
   br2.cmd('ebtables -A FORWARD -i br2-eth0 -o br2-eth1 -j DROP')
   br2.cmd('ebtables -A FORWARD -i br2-eth1 -o br2-eth0 -j DROP')
   
   # Ebtables by default allows traffic not explicitly dropped.
   # We rely on the implicit allow for traffic to/from vxlan0, as it's a different interface
   # from br1-eth0/eth1. The DROP rules are specific to local-to-local port forwarding.

   # --- Automatic Tests and Packet Capture ---
   info("\n*** Executing automatic tests and capturing VXLAN traffic (using pings)...\n")

   # Start packet capture on br1's transport interface in the background
   # Filter only UDP packets on the standard VXLAN port to reduce noise
   tcpdump_cmd = f'tcpdump -i {BR1_TRANSPORT_IF} -w {PCAP_FILE} "udp port {VXLAN_DST_PORT}" &'
   info(f"  Starting tcpdump on {BR1_TRANSPORT_IF}: {tcpdump_cmd}\n")
   br1.cmd(tcpdump_cmd)
   time.sleep(1) # Give tcpdump a moment to start

   info(f"  Executing ping from {h1.name} to {h3.name} ({H3_IP.split('/')[0]})...\n")
   h1_ping_h3_output = h1.cmd(f'ping -c 4 {H3_IP.split("/")[0]}')
   info(f"  Ping result h1 -> h3:\n{h1_ping_h3_output}\n")

   info(f"  Executing ping from {h2.name} to {h4.name} ({H4_IP.split('/')[0]})...\n")
   h2_ping_h4_output = h2.cmd(f'ping -c 4 {H4_IP.split("/")[0]}')
   info(f"  Ping result h2 -> h4:\n{h2_ping_h4_output}\n")

   # --- Verify Local Isolation ---
   info("\n*** Verifying local host isolation (these pings should FAIL)...\n")
   info(f"  Executing ping from {h1.name} to {h2.name} ({H2_IP.split('/')[0]})...\n")
   h1_ping_h2_output = h1.cmd(f'ping -c 2 {H2_IP.split("/")[0]}') # Reduced count for quicker fail
   info(f"  Ping result h1 -> h2:\n{h1_ping_h2_output}\n")

   info(f"  Executing ping from {h3.name} to {h4.name} ({H4_IP.split('/')[0]})...\n")
   h3_ping_h4_output = h3.cmd(f'ping -c 2 {H4_IP.split("/")[0]}') # Reduced count for quicker fail
   info(f"  Ping result h3 -> h4:\n{h3_ping_h4_output}\n")


   # Allow a few extra seconds for any delayed packets to be captured
   time.sleep(2)
   info(f"*** Terminating tcpdump capture on {BR1_TRANSPORT_IF}...\n")
   br1.cmd('pkill tcpdump') # Terminate the tcpdump process

   info(f"\n*** Packet capture saved to {PCAP_FILE}. You can open it with Wireshark.\n")
   info("    Look for UDP packets on port 4789 to see VXLAN encapsulation.\n")

   # Example of preliminary analysis with tshark (requires tshark installed on the VM)
   info("\n*** Preliminary analysis of PCAP file with tshark (if available)...\n")
   try:
       # Count captured VXLAN VNIs and show a summary
       tshark_output = subprocess.check_output(f'tshark -r {PCAP_FILE} -Y "vxlan" -T fields -e vxlan.vni | sort | uniq -c', shell=True).decode()
       info(f"  Count of captured VXLAN VNIs:\n{tshark_output}")

       tshark_summary = subprocess.check_output(f'tshark -r {PCAP_FILE} -Y "vxlan" -V | head -n 50', shell=True).decode()
       info(f"  Example of captured VXLAN packets (first 50 lines):\n{tshark_summary}...\n")

   except FileNotFoundError:
       info("  Tshark not found. Cannot perform preliminary PCAP analysis.\n")
   except subprocess.CalledProcessError as e:
       info(f"  Error during tshark analysis: {e.stderr.decode().strip()}\n")


   # Start CLI
   info("*** Starting Mininet CLI (type 'exit' to end simulation)...\n")
   CLI(net)

   # Cleanup: stop network
   info("*** Terminating Mininet network...\n")
   net.stop()
   cleanup() # COMMENTED OUT to preserve PCAP file in /tmp/
   info(f"*** Note: The PCAP file '{PCAP_FILE}' was NOT removed for your analysis.\n")
   info("         You can manually clean up Mininet instances with 'sudo mn -c' when finished.\n")


# Main entry point
if __name__ == '__main__':
   setLogLevel('info') # Set log level to 'info' for detailed messages
   create_vxlan_topo()