import traceback
import random

from netsquid_magic.models.perfect import PerfectLinkConfig
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.util.network_generation import create_complete_graph_network

from squidasm.run.stack.run import run

from router import *
from squidasm.run.stack.run import run


def main():

    N = 8

    while True:
        number_comunication = int(input(f"Enter a number between 1 and {N/2}: "))
        if 1 <= number_comunication <= N / 2:
            break
        else:
            print("number not valid.")

    params = TeleportParams.generate_random_params()
    # Define the nodes and links of the network
    node_names = []
    for letter in range(ord('A'), ord('D') + 1):
        for i in range(2):
            node_names.append(f"{chr(letter)}{i+1}")
    links = [
        ["A1", "A2"],
        ["A1", "B1"],
        ["A2", "C1"],
        ["B1", "B2"],
        ["B2", "D1"],
        ["C1", "C2"],
        ["C2", "D2"],
        ["D1", "D2"]
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
        print('\n')


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Error handling
        print(f"An error occurred: {e}")
        traceback.print_exc()
