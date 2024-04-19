import logging
from dataclasses import dataclass

import numpy
from netqasm.sdk import Qubit
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.toolbox.state_prep import set_qubit_state
from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.base_configs import StackNetworkConfig, StackConfig, LinkConfig, CLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.modules.qdevices.generic import GenericQDeviceConfig
from netsquid_netbuilder.util.network_generation import create_simple_network

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import get_qubit_state, get_reference_state


def create_network(node_names: list[str], links: list[tuple[str, str]]) -> StackNetworkConfig:
    """

    Args:
        node_names: a list of node names
        links: a list fo tuples of node names, each tuple is a link between the two nodes

    Returns:
        the network configuration with perfect links and devices
    """
    network_config = StackNetworkConfig(stacks=[], links=[], clinks=[])

    qdevice_cfg = GenericQDeviceConfig.perfect_config()

    stacks = dict()

    for node in node_names:

        stack = StackConfig(
            name=node, qdevice_typ='generic', qdevice_cfg=qdevice_cfg
        )
        network_config.stacks.append(stack)
        stacks[node] = stack

    for node0, node1 in links:

        link = LinkConfig(stack1=node0, stack2=node1, typ='perfect', cfg=PerfectLinkConfig(state_delay=0.0))
        network_config.links.append(link)

        clink = CLinkConfig(stack1=node0, stack2=node1, typ='default', cfg=DefaultCLinkConfig(delay=0.0))
        network_config.clinks.append(clink)

    return network_config
