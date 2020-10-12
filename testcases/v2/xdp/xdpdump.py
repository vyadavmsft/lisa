from pathlib import Path

from lisa import TestCaseMetadata, TestSuite, TestSuiteMetadata
from lisa.executable import CustomScript, CustomScriptBuilder
from lisa.testsuite import simple_requirement


@TestSuiteMetadata(
    area="xdp",
    category="functional",
    description="""
    This test suite run XDP Testcases.
    """,
    tags=["sriov", "networking", "xdp"],
    requirement=simple_requirement(min_count=1),
)
class xdpdump(TestSuite):
    @property
    def skiprun(self) -> bool:
        node = self.environment.default_node
        return not node.is_linux

    def before_suite(self) -> None:

        # Upload scripts required by testsuite
        self._xdp_script = CustomScriptBuilder(
            Path(__file__).parent.parent.joinpath("scripts"),
            [
                "xdpdumpsetup.sh",
                "xdputils.sh",
                "utils.sh",
                "enable_passwordless_root.sh",
                "enable_root.sh",
            ],
            command="sudo",
        )

    @TestCaseMetadata(
        description="""
        this test case run tests if xdp program load and unloads correctly.
        """,
        priority=1,
        requirement=simple_requirement(min_count=1, min_nic_count=2),
    )
    def verify_xdp_compliance(self) -> None:
        node = self.environment.default_node
        script: CustomScript = node.tools[self._xdp_script]
        # Get Extra NIC name
        synth_interface = script.run(
            "bash -c 'source ./xdputils.sh;get_extra_synth_nic'"
        )
        # Start setup script with parameters
        result = script.run(
            f"./xdpdumpsetup.sh {node.internal_address} {synth_interface}"
        )
        # TODO: Download remote log files
        state = script.run("cat state.txt")
        self.log.info(f"Final state after test execution:{state}")

        self.log.info("Check result")
        # TODO: Handle Skip test result
        self.assertEqual(state.stdout, "TestCompleted")
        self.assertEqual(
            0, result.exit_code, "xdpdumpsetup.sh script exit code should be 0"
        )

    def before_case(self) -> None:
        self.log.info("Setting up environment before test case")
        script: CustomScript = self.environment.default_node.tools[self._xdp_script]
        self.log.info("Enable root without password")
        script.run("./enable_root.sh")
        script.run("./enable_passwordless_root.sh")

    def after_case(self) -> None:
        self.log.info("after test case")
