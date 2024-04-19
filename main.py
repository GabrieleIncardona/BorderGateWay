from netsquid_netbuilder.run import get_default_builder
from squidasm.sim.stack.context import NetSquidContext
from squidasm.sim.stack.stack import ProcessingNode, NodeStack
import itertools

from struttura import create_network
import traceback
from router import *


def main():
    params = TeleportParams.generate_random_params()
    # Definire i nodi e i collegamenti della rete
    node_names = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2"]
    links = [
        ("A1", "A2"),
        ("A1", "B1"),
        ("A2", "C1"),
        ("B1", "B2"),
        ("B2", "D1"),
        ("C1", "C2"),
        ("C2", "D2"),
        ("D1", "D2")
    ]

    # Creare la configurazione della rete
    network_config = create_network(node_names, links)

    # Creare un dizionario di programmi per ciascun nodo
    programs = {}
    for node_name in node_names:
        router = Router(node_name, links, TeleportParams.generate_random_params())
        programs[node_name] = router

    NetSquidContext.reset()
    builder = get_default_builder()
    network = builder.build(network_config)
    stacks = {}
    for node_name, node in network.nodes.items():
        assert isinstance(node, ProcessingNode)
        stack = NodeStack(name=node_name, node=node, qdevice_type=node.qmemory_typ)
        NetSquidContext.add_node(stack.node.ID, node_name)
        stacks[node_name] = stack

    for id_tuple, egp in network.egp.items():
        node_name, peer_name = id_tuple
        stacks[node_name].assign_egp(network.node_name_id_mapping[peer_name], egp)

    for s1, s2 in itertools.combinations(stacks.values(), 2):
        print(s1.name, s2.name)
        print(s1.qnos.netstack._comp.ports)
        s1.qnos.netstack.register_peer(s2.node.ID)
        s1.qnos_comp.register_peer(s2.node.ID)
        s2.qnos.netstack.register_peer(s1.node.ID)
        s2.qnos_comp.register_peer(s1.node.ID)

    run(config=network_config, programs=programs, num_times=1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Gestione degli errori
        print(f"Si è verificato un errore: {e}")
        traceback.print_exc()
