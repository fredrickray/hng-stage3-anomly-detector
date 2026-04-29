import subprocess


class IPTablesBlocker:
    def block_ip(self, ip: str):
        existing = subprocess.run(["iptables", "-C", "INPUT", "-s", ip, "-j", "DROP"], check=False)
        if existing.returncode != 0:
            subprocess.run(["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"], check=False)

    def unblock_ip(self, ip: str):
        subprocess.run(["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"], check=False)
