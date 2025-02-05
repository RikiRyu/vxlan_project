#!/usr/bin/python3

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

# Cleanup function to remove old Mininet instances
def cleanup():
   subprocess.run(['mn', '-c'], check=True)

# Main topology creation function
def createVxlanTopo():
   # Clean any existing Mininet setup
   cleanup()
   # Create network with controller and configurable links
   net = Containernet(controller=Controller, link=TCLink)
   net.addController('c0')

   # Create hosts (h1-h4) and bridges (br1-br2)
   # These will form two network segments connected by VXLAN
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
   net.addLink(h1, br1)
   net.addLink(h2, br1)
   net.addLink(h3, br2)
   net.addLink(h4, br2)
   net.addLink(br1, br2)

   # Start network
   net.start()

   # Configure Linux bridges on VTEP nodes
   for br in [br1, br2]:
       br.cmd('ip link add br0 type bridge')  # Create bridge
       br.cmd('ip link set br0 up')           # Enable bridge
       br.cmd('ip addr add 10.0.0.254/24 dev br0')  # Add IP to bridge

   # Configure transport network IPs (for VXLAN tunnel)
   br1.cmd('ip addr add 192.168.1.1/24 dev br1-eth2')
   br2.cmd('ip addr add 192.168.1.2/24 dev br2-eth2')

   # Configure VXLAN interfaces
   # VNI=100, UDP port=4789 (standard VXLAN port)
   br1.cmd('ip link add vxlan0 type vxlan id 100 remote 192.168.1.2 local 192.168.1.1 dstport 4789 dev br1-eth2')
   br2.cmd('ip link add vxlan0 type vxlan id 100 remote 192.168.1.1 local 192.168.1.2 dstport 4789 dev br2-eth2')
   br1.cmd('ip link set vxlan0 up')
   br2.cmd('ip link set vxlan0 up')

   # Add host interfaces and VXLAN interfaces to bridges
   for i in range(2):
       br1.cmd(f'ip link set br1-eth{i} master br0')
       br2.cmd(f'ip link set br2-eth{i} master br0')
   
   br1.cmd('ip link set vxlan0 master br0')
   br2.cmd('ip link set vxlan0 master br0')

   # Configure host IP addresses in the 10.0.0.0/24 subnet
   h1.cmd('ip addr add 10.0.0.1/24 dev h1-eth0')
   h2.cmd('ip addr add 10.0.0.2/24 dev h2-eth0')
   h3.cmd('ip addr add 10.0.0.3/24 dev h3-eth0')
   h4.cmd('ip addr add 10.0.0.4/24 dev h4-eth0')

   # Start packet capture on the transport interface
   br1.cmd('tcpdump -i br1-eth2 -w /tmp/vxlan_outer.pcap &')
   time.sleep(1)  # Wait for tcpdump to initialize

   # Start CLI
   CLI(net)

   # Cleanup: stop packet capture and network
   br1.cmd('pkill tcpdump')
   net.stop()

# Main entry point
if __name__ == '__main__':
   setLogLevel('info')
   createVxlanTopo()
