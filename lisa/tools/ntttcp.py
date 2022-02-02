# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import re
from decimal import Decimal
from typing import Any, Dict, List, Type

from lisa.executable import Tool
from lisa.messages import (
    NetworkNtttcpTCPPerformanceMessage,
    NetworkNtttcpUDPPerformanceMessage,
    TransportProtocol,
    create_message,
)
from lisa.tools import Gcc, Git, Make
from lisa.util.process import ExecutableResult, Process

NTTTCP_TCP_CONCURRENCY = [
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    128,
    256,
    512,
    1024,
    2048,
    4096,
    6144,
    8192,
    10240,
    20480,
]
NTTTCP_UDP_CONCURRENCY = [
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    128,
    256,
    512,
    1024,
]


class NtttcpResult:
    role: str = "server"
    connections_created_time: Decimal = Decimal(0)
    throughput_in_gbps: Decimal = Decimal(0)
    retrans_segs: Decimal = Decimal(0)
    tx_packets: Decimal = Decimal(0)
    rx_packets: Decimal = Decimal(0)
    pkts_interrupt: Decimal = Decimal(0)
    cycles_per_byte: Decimal = Decimal(0)


class Ntttcp(Tool):
    repo = "https://github.com/microsoft/ntttcp-for-linux"
    throughput_pattern = re.compile(r" 	 throughput	:(.+)")
    # NTTTCP output sample
    # NTTTCP for Linux 1.4.0
    # ---------------------------------------------------------
    # Test cycle time negotiated is: 122 seconds
    # 1 threads created
    # 1 connections created in 1156 microseconds
    # Network activity progressing...
    # Test warmup completed.
    # Test run completed.
    # Test cooldown is in progress...
    # Test cycle finished.
    # receiver exited from current test
    # 1 connections tested
    # #####  Totals:  #####
    # test duration	:120.36 seconds
    # total bytes	:135945781248
    #     throughput	:9.04Gbps
    #     retrans segs	:679
    # total packets:
    #     tx_packets	:2895248
    #     rx_packets	:3240673
    # interrupts:
    #     total		:2769054
    #     pkts/interrupt	:2.22
    # cpu cores	:72
    #     cpu speed	:2593.905MHz
    #     user		:0.03%
    #     system		:0.41%
    #     idle		:99.56%
    #     iowait		:0.00%
    #     softirq	:0.00%
    #     cycles/byte	:0.73
    # cpu busy (all)	:26.81%
    output_pattern = re.compile(
        r"(([\w\W]*?)connections created in "
        r"(?P<connections_created_time>.+) microseconds)?([\w\W]*?)Totals:([\w\W]*?)"
        r"throughput.*:(?P<throughput>.+)(?P<unit>Mbps|Gbps)(([\w\W]*?)"
        r"retrans segs.*:(?P<retrans_segs>.+))?"
        r"([\w\W]*?)tx_packets.*:(?P<tx_packets>.+)"
        r"([\w\W]*?)rx_packets.*:(?P<rx_packets>.+)"
        r"(([\w\W]*?)pkts/interrupt.*:(?P<pkts_interrupt>.+))?"
        r"([\w\W]*?)cycles/byte.*:(?P<cycles_per_byte>.+)",
        re.MULTILINE,
    )

    @property
    def dependencies(self) -> List[Type[Tool]]:
        return [Git, Make, Gcc]

    @property
    def command(self) -> str:
        return "ntttcp"

    @property
    def can_install(self) -> bool:
        return True

    def _install(self) -> bool:
        tool_path = self.get_tool_path()
        git = self.node.tools[Git]
        git.clone(self.repo, tool_path)
        make = self.node.tools[Make]
        code_path = tool_path.joinpath("ntttcp-for-linux/src")
        make.make_install(cwd=code_path)
        self.node.execute(
            "ln -s /usr/local/bin/ntttcp /usr/bin/ntttcp", sudo=True, cwd=code_path
        ).assert_exit_code()
        return self._check_exists()

    def help(self) -> ExecutableResult:
        return self.run("-h")

    def get_throughput(self, stdout: str) -> str:
        throughput = self.throughput_pattern.findall(stdout)
        if throughput:
            result: str = throughput[0]
        else:
            result = "cannot find throughput"
        return result

    def run_as_server_async(
        self,
        nic_name: str,
        run_time_seconds: int = 10,
        ports_count: int = 64,
        buffer_size: int = 64,
        cool_down_time_seconds: int = 1,
        warm_up_time_seconds: int = 1,
        use_epoll: bool = True,
        server_ip: str = "",
        dev_differentiator: str = "Hypervisor callback interrupts",
        run_as_daemon: bool = False,
        udp_mode: bool = False,
    ) -> Process:
        cmd = ""
        if server_ip:
            cmd += f" -r{server_ip} "
        cmd += (
            f" -P {ports_count} -t {run_time_seconds} -W {warm_up_time_seconds} "
            f"-C {cool_down_time_seconds} -b {buffer_size}k "
            f"--show-nic-packets {nic_name} "
        )
        if udp_mode:
            cmd += " -u "
        if use_epoll:
            cmd += " -e "
        if dev_differentiator:
            cmd += f" --show-dev-interrupts {dev_differentiator} "
        if run_as_daemon:
            cmd += " -D "
        process = self.node.execute_async(
            f"ulimit -n 204800 && {self.command} {cmd}", shell=True, sudo=True
        )
        return process

    def run_as_server(
        self,
        nic_name: str,
        run_time_seconds: int = 10,
        ports_count: int = 64,
        buffer_size: int = 64,
        cool_down_time_seconds: int = 1,
        warm_up_time_seconds: int = 1,
        use_epoll: bool = True,
        server_ip: str = "",
        dev_differentiator: str = "Hypervisor callback interrupts",
        run_as_daemon: bool = False,
        udp_mode: bool = False,
    ) -> None:
        # -rserver_ip: run as a receiver with specified server ip address
        # -P: Number of ports listening on receiver side [default: 16] [max: 512]
        # -t: Time of test duration in seconds [default: 60]
        # -e: [receiver only] use epoll() instead of select()
        # -u: UDP mode     [default: TCP]
        # -W: Warm-up time in seconds          [default: 0]
        # -C: Cool-down time in seconds        [default: 0]
        # -b: <buffer size in n[KMG] Bytes>    [default: 65536 (receiver); 131072
        # (sender)]
        # --show-nic-packets <network interface name>: Show number of packets
        # transferred (tx and rx) through this network interface
        # --show-dev-interrupts <device differentiator>: Show number of interrupts for
        # the devices specified by the differentiator
        # Examples for differentiator: Hyper-V PCIe MSI, mlx4, Hypervisor callback
        # interrupts
        process = self.run_as_server_async(
            nic_name,
            run_time_seconds,
            ports_count,
            buffer_size,
            cool_down_time_seconds,
            warm_up_time_seconds,
            use_epoll,
            server_ip,
            dev_differentiator,
            run_as_daemon,
            udp_mode,
        )
        process.wait_result(
            expected_exit_code=0,
            expected_exit_code_failure_message="fail to lanuch ntttcp server",
        )

    def run_as_client(
        self,
        nic_name: str,
        server_ip: str,
        threads_count: int,
        run_time_seconds: int = 10,
        ports_count: int = 64,
        buffer_size: int = 64,
        cool_down_time_seconds: int = 1,
        warm_up_time_seconds: int = 1,
        dev_differentiator: str = "Hypervisor callback interrupts",
        run_as_daemon: bool = False,
        udp_mode: bool = False,
    ) -> ExecutableResult:
        # -sserver_ip: run as a sender with server ip address
        # -P: Number of ports listening on receiver side [default: 16] [max: 512]
        # -n: [sender only] number of threads per each receiver port     [default: 4]
        # [max: 25600]
        # -t: Time of test duration in seconds [default: 60]
        # -e: [receiver only] use epoll() instead of select()
        # -u: UDP mode     [default: TCP]
        # -W: Warm-up time in seconds          [default: 0]
        # -C: Cool-down time in seconds        [default: 0]
        # -b: <buffer size in n[KMG] Bytes>    [default: 65536 (receiver); 131072
        # (sender)]
        # --show-nic-packets <network interface name>: Show number of packets
        # transferred (tx and rx) through this network interface
        # --show-dev-interrupts <device differentiator>: Show number of interrupts for
        # the devices specified by the differentiator
        # Examples for differentiator: Hyper-V PCIe MSI, mlx4, Hypervisor callback
        # interrupts
        cmd = (
            f" -s{server_ip} -P {ports_count} -n {threads_count} -t {run_time_seconds} "
            f"-W {warm_up_time_seconds} -C {cool_down_time_seconds} -b {buffer_size}k "
            f"--show-nic-packets {nic_name} "
        )
        if udp_mode:
            cmd += " -u "
        if dev_differentiator:
            cmd += f" --show-dev-interrupts {dev_differentiator} "
        if run_as_daemon:
            cmd += " -D "
        result = self.node.execute(
            f"ulimit -n 204800 && {self.command} {cmd}",
            shell=True,
            sudo=True,
            expected_exit_code=0,
            expected_exit_code_failure_message=f"fail to run {self.command} {cmd}",
        )
        return result

    def create_ntttcp_result(
        self, result: ExecutableResult, role: str = "server"
    ) -> NtttcpResult:
        matched_results = self.output_pattern.match(result.stdout)
        assert matched_results, "not found matched ntttcp results."
        ntttcp_result = NtttcpResult()
        ntttcp_result.role = role
        if "Mbps" == matched_results.group("unit"):
            ntttcp_result.throughput_in_gbps = Decimal(
                Decimal(matched_results.group("throughput")) / 1000
            )
        else:
            ntttcp_result.throughput_in_gbps = Decimal(
                matched_results.group("throughput")
            )
        if matched_results.group("connections_created_time"):
            ntttcp_result.connections_created_time = Decimal(
                matched_results.group("connections_created_time")
            )
        if matched_results.group("pkts_interrupt"):
            ntttcp_result.pkts_interrupt = Decimal(
                matched_results.group("pkts_interrupt")
            )
        if matched_results.group("retrans_segs"):
            ntttcp_result.retrans_segs = Decimal(matched_results.group("retrans_segs"))
        ntttcp_result.rx_packets = Decimal(matched_results.group("rx_packets"))
        ntttcp_result.tx_packets = Decimal(matched_results.group("tx_packets"))
        ntttcp_result.cycles_per_byte = Decimal(
            matched_results.group("cycles_per_byte")
        )
        return ntttcp_result

    def create_ntttcp_tcp_performance_message(
        self,
        server_result: NtttcpResult,
        client_result: NtttcpResult,
        latency: Decimal,
        connections_num: str,
        buffer_size: int,
        information: Dict[str, str],
        test_case_name: str,
    ) -> NetworkNtttcpTCPPerformanceMessage:
        other_fields: Dict[str, Any] = {}
        other_fields["buffer_size"] = Decimal(buffer_size)
        other_fields["connections_created_time"] = int(
            client_result.connections_created_time
        )
        other_fields["connections_num"] = int(connections_num)
        other_fields["latency_us"] = latency
        other_fields["retrans_segments"] = int(client_result.retrans_segs)
        other_fields["throughput_in_gbps"] = client_result.throughput_in_gbps
        other_fields["rx_packets"] = server_result.rx_packets
        other_fields["tx_packets"] = client_result.tx_packets
        other_fields["pkts_interrupts"] = client_result.pkts_interrupt
        other_fields["sender_cycles_per_byte"] = client_result.cycles_per_byte
        other_fields["receiver_cycles_rer_byte"] = server_result.cycles_per_byte
        return create_message(
            NetworkNtttcpTCPPerformanceMessage,
            self.node,
            information,
            test_case_name,
            other_fields,
        )

    def create_ntttcp_udp_performance_message(
        self,
        server_result: NtttcpResult,
        client_result: NtttcpResult,
        connections_num: str,
        buffer_size: int,
        information: Dict[str, str],
        test_case_name: str,
    ) -> NetworkNtttcpUDPPerformanceMessage:
        other_fields: Dict[str, Any] = {}
        other_fields["protocol_type"] = TransportProtocol.Udp
        other_fields["send_buffer_size"] = Decimal(buffer_size)
        other_fields["connections_created_time"] = int(
            client_result.connections_created_time
        )
        other_fields["connections_num"] = int(connections_num)
        other_fields["tx_throughput_in_gbps"] = client_result.throughput_in_gbps
        other_fields["rx_throughput_in_gbps"] = server_result.throughput_in_gbps
        other_fields["receiver_cycles_rer_byte"] = server_result.cycles_per_byte
        other_fields["data_loss"] = (
            100
            * (client_result.throughput_in_gbps - server_result.throughput_in_gbps)
            / client_result.throughput_in_gbps
        )
        return create_message(
            NetworkNtttcpUDPPerformanceMessage,
            self.node,
            information,
            test_case_name,
            other_fields,
        )
