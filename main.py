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

    run(config=network_config, programs=programs, num_times=1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Gestione degli errori
        print(f"Si è verificato un errore: {e}")
        traceback.print_exc()
