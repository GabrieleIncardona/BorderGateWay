from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.util.network_generation import create_complete_graph_network

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

    # import network configuration from file
    cfg = create_complete_graph_network(
        node_names,
        "perfect",
        PerfectLinkConfig(state_delay=100),
        clink_typ="default",
        clink_cfg=DefaultCLinkConfig(delay=100),
    )

    # Creare un dizionario di programmi per ciascun nodo
    programs = {}
    for node_name in node_names:
        link = []
        for link_name in links:
            if node_name in link_name:
                for num in link_name:
                    if num != node_name:
                        link.append(num)

        router = Router(node_name, link, TeleportParams.generate_random_params())
        programs[node_name] = router

    run(config=cfg, programs=programs, num_times=1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Gestione degli errori
        print(f"Si è verificato un errore: {e}")
        traceback.print_exc()
