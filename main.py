import traceback
import random

from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.util.network_generation import create_complete_graph_network

from squidasm.run.stack.run import run

from quantum_repeater import *
from squidasm.run.stack.run import run


def main():

    N = 36

    while True:
        number_comunication = int(input(f"Enter a number between 1 and {N/2}: "))
        if 1 <= number_comunication <= N / 2:
            break
        else:
            print("number not valid.")

    params = TeleportParams.generate_random_params()
    # Define the nodes and links of the network
    node_names = []
    for letter in range(ord('A'), ord('I') + 1):
        for i in range(4):
            node_names.append(f"{chr(letter)}{i+1}")
    links = [
        ["A1", "A2"],
        ["A1", "A3"],
        ["A1", "A4"],
        ["A2", "A3"],
        ["A2", "A4"],
        ["A3", "A4"],
        ["A4", "B1"],

        ["B1", "B2"],
        ["B1", "B3"],
        ["B1", "B4"],
        ["B2", "B3"],
        ["B2", "B4"],
        ["B3", "B4"],
        ["B4", "C1"],
        ["B2", "D3"],
        ["B3", "E2"],

        ["C1", "C2"],
        ["C1", "C3"],
        ["C1", "C4"],
        ["C2", "C3"],
        ["C2", "C4"],
        ["C3", "C4"],

        ["D1", "D2"],
        ["D1", "D3"],
        ["D1", "D4"],
        ["D2", "D3"],
        ["D2", "D4"],
        ["D3", "D4"],

        ["E1", "E2"],
        ["E1", "E3"],
        ["E1", "E4"],
        ["E2", "E3"],
        ["E2", "E4"],
        ["E3", "E4"],

        ["F1", "F2"],
        ["F1", "F3"],
        ["F1", "F4"],
        ["F2", "F3"],
        ["F2", "F4"],
        ["F3", "F4"],

        ["F2", "A3"],
        ["F4", "E1"],

        ["G1", "G2"],
        ["G1", "G3"],
        ["G1", "G4"],
        ["G2", "G3"],
        ["G2", "G4"],
        ["G3", "G4"],

        ["G3", "A2"],
        ["G4", "D1"],

        ["H1", "H2"],
        ["H1", "H3"],
        ["H1", "H4"],
        ["H2", "H3"],
        ["H2", "H4"],
        ["H3", "H4"],

        ["H1", "E4"],
        ["H2", "C3"],

        ["I1", "I2"],
        ["I1", "I3"],
        ["I1", "I4"],
        ["I2", "I3"],
        ["I2", "I4"],
        ["I3", "I4"],

        ["I1", "D4"],
        ["I3", "C2"]
    ]

    # import network configuration from file
    cfg = create_complete_graph_network(
        node_names,
        "perfect",
        PerfectLinkConfig(state_delay=0),
        clink_typ="default",
        clink_cfg=DefaultCLinkConfig(delay=0),
    )

    #print(programs)
    for i in range(10):

        senders = random.sample(node_names, number_comunication)
        received = random.sample(node_names, number_comunication)
        print(senders)
        print(received)
        # Create a program dictionary for each node
        programs = {}
        for node_name in node_names:
            link = []
            for link_name in links:
                if node_name in link_name:
                    for num in link_name:
                        if num != node_name:
                            link.append(num)

            router = Router(node_name, link, TeleportParams.generate_random_params(), senders, received)
            programs[node_name] = router
        run(config=cfg, programs=programs, num_times=1)
        with open('time.txt', 'a') as f:
            f.write(f"\n")
        with open('test.txt', 'a') as f:
            f.write(f"\n")
        print('\n')


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Error handling
        print(f"An error occurred: {e}")
        traceback.print_exc()
