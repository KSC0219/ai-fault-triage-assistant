"""Generate a synthetic history of resolved network faults.

Each category has several symptom phrasings, root causes and fixes, so the
knowledge base looks like a real NOC ticket history. The output is
data/fault_history.json. Real ticket exports with the same fields can replace it.
"""
import json
import random
from pathlib import Path

random.seed(42)

DEVICES = {
    "router": ["router-blr-01", "router-blr-02", "router-hyd-01", "router-chn-01", "router-mum-01"],
    "switch": ["switch-blr-core-01", "switch-blr-acc-12", "switch-hyd-acc-03", "switch-chn-core-02"],
    "firewall": ["fw-blr-edge-01", "fw-hyd-edge-01"],
    "server": ["dns-blr-01", "dhcp-hyd-01", "app-chn-07"],
    "wireless": ["wlc-blr-01", "ap-blr-3f-14", "ap-hyd-2f-05"],
}

CATEGORIES = {
    "fiber_link_down": {
        "device": "router", "severity": "HIGH",
        "symptoms": [
            "Uplink interface {port} went down, no carrier detected",
            "Link on {port} flapping and then fully down, site lost WAN",
            "Interface {port} shows down/down, remote side unreachable",
            "Loss of signal alarm on {port}, branch office offline",
        ],
        "root_causes": [
            "Fiber cable cut during civil work near the site",
            "Faulty SFP transceiver on {port}",
            "Dirty fiber connector causing total light loss",
        ],
        "resolutions": [
            "Replaced the SFP module on {port}; link came up and traffic restored",
            "ISP team spliced the damaged fiber; link restored after 3 hours",
            "Cleaned the fiber connectors and re-seated the patch cord; link stable",
        ],
    },
    "low_optical_power": {
        "device": "router", "severity": "MEDIUM",
        "symptoms": [
            "Rx optical power on {port} below threshold at -24 dBm",
            "Low light warning on {port}, intermittent CRC errors",
            "DOM shows degraded receive power on {port}",
        ],
        "root_causes": [
            "Bent fiber patch cord in the rack",
            "Aging SFP with degraded laser",
            "Dirty connector at the ODF panel",
        ],
        "resolutions": [
            "Replaced the patch cord; Rx power back to -6 dBm",
            "Swapped the SFP with a spare; optical levels normal",
            "Cleaned the ODF connectors with a fiber cleaning kit",
        ],
    },
    "high_cpu": {
        "device": "router", "severity": "HIGH",
        "symptoms": [
            "CPU utilisation at 98% for the last 20 minutes, SSH very slow",
            "Control plane CPU spiking, routing protocol timers expiring",
            "High CPU alarm, device slow to respond to SNMP polls",
        ],
        "root_causes": [
            "Excessive SNMP polling from a misconfigured monitoring server",
            "Broadcast storm punted to the CPU",
            "Routing process stuck after a large route update",
        ],
        "resolutions": [
            "Reduced the SNMP polling interval and applied a control-plane policing policy",
            "Identified the storm source port, shut it and enabled storm control",
            "Cleared the routing process and applied the vendor-recommended patch",
        ],
    },
    "bgp_flap": {
        "device": "router", "severity": "CRITICAL",
        "symptoms": [
            "BGP session with ISP neighbor flapping every few minutes",
            "BGP neighbor down, hold timer expired, prefixes withdrawn",
            "eBGP peer repeatedly going Idle/Active, internet reachability unstable",
        ],
        "root_causes": [
            "MTU mismatch causing large BGP update packets to drop",
            "Packet loss on the ISP link causing keepalives to be lost",
            "ISP changed the neighbor password without notice",
        ],
        "resolutions": [
            "Aligned the interface MTU on both ends; session stable",
            "Raised a ticket with the ISP who fixed the loss on their side",
            "Updated the MD5 password to match the ISP; session established",
        ],
    },
    "packet_loss_crc": {
        "device": "switch", "severity": "MEDIUM",
        "symptoms": [
            "Users report slow network, CRC errors incrementing on {port}",
            "Input errors and CRC counters rising on {port}, 5% packet loss",
            "Intermittent packet loss to servers behind {port}",
        ],
        "root_causes": [
            "Damaged copper cable between switch and patch panel",
            "Duplex mismatch: one side half duplex, other full duplex",
            "Electromagnetic interference from a nearby power line",
        ],
        "resolutions": [
            "Replaced the Cat6 cable; CRC counters stopped increasing",
            "Set both ends to auto-negotiate; duplex now full on both sides",
            "Re-routed the cable away from the power line and used shielded cable",
        ],
    },
    "stp_loop": {
        "device": "switch", "severity": "CRITICAL",
        "symptoms": [
            "Whole floor lost network, MAC address table flapping",
            "Switch CPU at 100%, broadcast traffic flooding all ports",
            "Network outage, topology change notifications flooding the logs",
        ],
        "root_causes": [
            "User connected a cable between two wall ports, creating a layer 2 loop",
            "Unmanaged switch added under a desk with no spanning tree",
            "BPDU guard disabled on access ports after a template change",
        ],
        "resolutions": [
            "Located the looped port via MAC flap logs and shut it; enabled BPDU guard",
            "Removed the unmanaged switch and enabled BPDU guard on access ports",
            "Restored the access port template with BPDU guard and storm control",
        ],
    },
    "port_err_disabled": {
        "device": "switch", "severity": "LOW",
        "symptoms": [
            "Port {port} in err-disabled state, user desk has no network",
            "Interface {port} shut down by port security violation",
            "Access port {port} err-disabled after a device was plugged in",
        ],
        "root_causes": [
            "Port security violation: a new laptop MAC address was not allowed",
            "BPDU received on a portfast port from a small switch",
        ],
        "resolutions": [
            "Cleared the sticky MAC, bounced the port and updated the allowed MAC",
            "Removed the rogue switch and re-enabled the port",
        ],
    },
    "dns_failure": {
        "device": "server", "severity": "HIGH",
        "symptoms": [
            "Users cannot open websites but can ping IP addresses",
            "DNS resolution timing out for internal domains",
            "Applications failing with name resolution errors",
        ],
        "root_causes": [
            "DNS service stopped after the server ran out of disk space",
            "Firewall rule change blocked UDP 53 to the DNS server",
            "Forwarder to the upstream resolver unreachable",
        ],
        "resolutions": [
            "Cleared old logs to free disk space and restarted the DNS service",
            "Restored the firewall rule allowing DNS traffic",
            "Configured a secondary forwarder and verified resolution",
        ],
    },
    "dhcp_exhaustion": {
        "device": "server", "severity": "MEDIUM",
        "symptoms": [
            "New devices getting 169.254.x.x addresses, no IP assigned",
            "DHCP scope for the guest VLAN at 100% utilisation",
            "Users cannot connect after joining Wi-Fi, no IP lease",
        ],
        "root_causes": [
            "DHCP lease time too long for a high-churn guest network",
            "Rogue DHCP-starvation traffic from an infected laptop",
            "Scope too small after more users moved to the floor",
        ],
        "resolutions": [
            "Reduced the lease time to 4 hours and cleared stale leases",
            "Blocked the offending MAC and enabled DHCP snooping",
            "Expanded the scope from /24 to /23",
        ],
    },
    "firewall_session_limit": {
        "device": "firewall", "severity": "HIGH",
        "symptoms": [
            "Firewall session table full, new connections dropped",
            "Internet access intermittent, firewall logs show session limit reached",
            "Concurrent session count at maximum on the edge firewall",
        ],
        "root_causes": [
            "Malware-infected host opening thousands of connections",
            "Session timeout too long for UDP traffic",
        ],
        "resolutions": [
            "Isolated the infected host and cleared its sessions",
            "Reduced the UDP session timeout and applied per-host session limits",
        ],
    },
    "power_supply_failure": {
        "device": "switch", "severity": "HIGH",
        "symptoms": [
            "Power supply 2 failed alarm, device running on single PSU",
            "Device rebooted unexpectedly, PSU fault in logs",
            "Redundant power lost, PSU status shows failed",
        ],
        "root_causes": [
            "PSU hardware failure",
            "Rack PDU breaker tripped on one feed",
        ],
        "resolutions": [
            "Replaced the PSU under the vendor RMA",
            "Reset the PDU breaker and balanced load across both feeds",
        ],
    },
    "high_temperature": {
        "device": "router", "severity": "HIGH",
        "symptoms": [
            "Temperature alarm, chassis inlet at 52 C",
            "Fan tray failure alarm and rising temperature",
            "Device throttling due to overheating",
        ],
        "root_causes": [
            "Server room AC failure",
            "Fan tray failure",
            "Blocked airflow from cables in front of the vents",
        ],
        "resolutions": [
            "Facilities restored the AC; temperature back to normal",
            "Replaced the fan tray",
            "Re-dressed the cables to clear the airflow path",
        ],
    },
    "memory_leak": {
        "device": "firewall", "severity": "MEDIUM",
        "symptoms": [
            "Free memory steadily decreasing over weeks, now at 5%",
            "Memory utilisation alarm, process consuming more memory every day",
            "Device crashed with out-of-memory after a long uptime",
        ],
        "root_causes": [
            "Known memory leak bug in the current firmware version",
            "Logging process leaking memory when the syslog server is unreachable",
        ],
        "resolutions": [
            "Upgraded the firmware to the fixed release in a maintenance window",
            "Restored syslog server reachability and restarted the logging process",
        ],
    },
    "wifi_auth_failure": {
        "device": "wireless", "severity": "MEDIUM",
        "symptoms": [
            "Users cannot connect to corporate Wi-Fi, authentication failing",
            "802.1X authentication timeouts on the wireless network",
            "Wi-Fi connects for guests but employees get credential errors",
        ],
        "root_causes": [
            "RADIUS server certificate expired",
            "RADIUS server unreachable from the wireless controller",
            "Shared secret mismatch after the controller was replaced",
        ],
        "resolutions": [
            "Renewed the RADIUS server certificate",
            "Fixed the routing to the RADIUS server",
            "Re-entered the correct shared secret on the controller",
        ],
    },
    "vpn_tunnel_down": {
        "device": "firewall", "severity": "HIGH",
        "symptoms": [
            "Site-to-site IPsec VPN to the branch is down",
            "IPsec tunnel phase 1 negotiation failing",
            "Branch cannot reach the data centre over the VPN",
        ],
        "root_causes": [
            "Pre-shared key mismatch after a key rotation",
            "Branch public IP changed after an ISP change",
            "Phase 2 proposal mismatch after a firewall upgrade",
        ],
        "resolutions": [
            "Updated the pre-shared key on both peers",
            "Updated the peer IP to the branch's new public address",
            "Aligned the phase 2 encryption and hashing proposals",
        ],
    },
}

PORTS = ["Gi0/0/1", "Gi0/1", "Te1/0/1", "Gi1/0/24", "Te0/0/0", "Gi1/0/7"]
ENGINEERS = ["ravi.k", "anitha.s", "noc-team", "suresh.m", "priya.r"]


def fill(text: str, port: str) -> str:
    return text.format(port=port)


def generate(per_category: int = 10):
    records = []
    fid = 1000
    for category, spec in CATEGORIES.items():
        for _ in range(per_category):
            fid += 1
            port = random.choice(PORTS)
            i = random.randrange(len(spec["root_causes"]))
            symptom = fill(random.choice(spec["symptoms"]), port)
            records.append({
                "id": fid,
                "title": symptom.split(",")[0][:120],
                "description": symptom,
                "device_name": random.choice(DEVICES[spec["device"]]),
                "category": category,
                "severity": spec["severity"],
                "root_cause": fill(spec["root_causes"][i], port),
                "resolution": fill(spec["resolutions"][i], port),
                "resolved_by": random.choice(ENGINEERS),
            })
    random.shuffle(records)
    return records


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "fault_history.json"
    data = generate()
    out.write_text(json.dumps(data, indent=2))
    print(f"Wrote {len(data)} resolved faults across {len(CATEGORIES)} categories to {out}")
