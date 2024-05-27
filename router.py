import random
import time

import numpy

from netsquid_protocols import QueueProtocol, CSocketListener

from netqasm.sdk import Qubit
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.toolbox.state_prep import set_qubit_state

from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import get_qubit_state, get_reference_state


class TeleportParams:
    phi: float = 0.0
    theta: float = 0.0

    @classmethod
    def generate_random_params(cls):
        """Create random parameters for a distributed CNOT program"""
        params = cls()
        params.theta = numpy.random.random() * numpy.pi
        params.phi = numpy.random.random() * numpy.pi
        return params


class Router(Program):
    msg = ""
    availability = 1
    sender = None
    sender2 = None
    initiator = 0
    last = 0
    link_already_created = 0

    receiver = ""
    first = ""

    def __init__(self, jointly, link, params: TeleportParams, senders, receivers):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.jointly = jointly
        self.link = link
        self.phi = params.phi
        self.theta = params.theta
        self.senders = senders
        self.receivers = receivers
        self.start_time = 0
        self.end_time = 0

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="controller_program",
            csockets=self.link,
            epr_sockets=self.link,
            max_qubits=2,
        )

    def run(self, context: ProgramContext):

        if self.jointly in self.senders:
            self.receiver = random.choice(self.receivers)
            if self.jointly != self.receiver:
                self.send_message(f"{self.jointly} want to communicate with {self.receiver}", context)
                print(f"{self.jointly} would like to communicate with {self.receiver}")

        yield from self.receive_message(context)

    def send_message(self, msg, context):
        self.start_time = time.time()
        if self.receiver in self.link:
            csocket1 = context.csockets[self.receiver]
            csocket1.send("direct connection")
            self.initiator = 1
            self.msg = msg
            self.availability = 0
        else:
            csocket = []
            for i in range(len(self.link)):
                csocket.append(context.csockets[self.link[i]])
            if "want to communicate with" in msg:
                self.initiator = 1
            self.msg = msg
            self.availability = 0
            # yield from connection.flush()
            for i in range(len(self.link)):
                csocket[i].send(msg)

    def receive_message(self, context):
        queue_protocol = QueueProtocol()
        queue_protocol.start()
        count = 0

        request = []

        for i in range(len(self.link)):
            listener = (
                CSocketListener(context, self.link[i], queue_protocol, self.logger))
            listener.start()
        while True and count < 1000:
            connection = []
            client_name, msg = yield from queue_protocol.pop()

            for i in range(len(self.link)):
                if self.link[i] != client_name:
                    connection.append(self.link[i])

            self.msg = msg
            # print(f"{self.jointly}: ho ricevuto {msg} da {client_name}")
            if "want to communicate with" in msg:
                submission = self.msg.split("want to communicate with ")
                if self.jointly == submission[1]:
                    if self.availability == 1:
                        self.availability = 0
                        self.last = 1
                        self.sender = client_name
                        self.send_answer(context, 0)
                        string = msg.split(" ")
                        self.first = string[0]
                        if self.link_already_created == 0:
                            self.link_already_created = 1

                    else:
                        # self.Restore_availability(context)
                        # with open('file.txt', 'a') as f:
                        #   f.write('')
                        request.append((msg, client_name))

                else:
                    if self.availability == 1:
                        self.availability = 0
                        self.sender = client_name
                        string = msg.split(" ")
                        self.first = string[0]
                        # print(msg)
                        self.ask_availability(context, connection)

                    else:
                        request.append((msg, client_name))

            elif "Available" in msg:
                if self.link_already_created == 0:
                    self.link_already_created = 1
                    self.sender2 = client_name
                    substring = msg.split(":")
                    # print(substring)
                    counter = int(substring[1].strip())
                    counter = counter + 1
                    # print(f"{self.jointly}: {client_name}")
                    # print(f"{self.jointly}: {self.initiator}")
                    if self.initiator == 0:
                        if self.sender is not None:
                            self.send_answer(context, counter)
                    else:
                        self.sender = client_name
                        self.sender2 = client_name
                        # print(f"{counter}")
                        with open('test.txt', 'a') as f:
                            f.write(f"{self.jointly} Link with {counter} hope with {self.receiver}\n")
                        yield from self.create_quantum_link_initial(queue_protocol, context, request)

            # elif self.msg == "No Available":
            #    if self.availability == 0 and self.initiator == 0:
            #        self.Restore_availability(context)

            elif msg.startswith("Sending epr"):
                self.sender = client_name
                # self.cycle = False
                if self.last == 0:
                    yield from self.create_quantum_link_intermediate(queue_protocol, context, request)
                else:
                    yield from self.create_quantum_link_last(queue_protocol, context, request)
            elif "Restore availability" in msg:
                if self.availability == 0 and self.initiator == 0 and self.first in msg:
                    self.send_message(f"Restore availability {self.first}", context)
                    self.availability = 1
                    # print("HELLO")
                    self.message_checker(context, request, queue_protocol)
                    # print(f"{self.jointly}")
                elif self.initiator == 1 and self.link_already_created == 0:
                    time.sleep(0.001)
                    # print(f"{self.jointly}  want to communicate with {self.receiver}")
                    self.send_message(f"{self.jointly} want to communicate with {self.receiver}", context)

            elif msg == "direct connection":
                if self.availability == 1:
                    self.sender = client_name
                    self.availability = 0
                    self.link_already_created = 1
                    yield from self.create_quantum_link_direct_received(queue_protocol, context, request)
                else:
                    request.append((msg, client_name))

            elif msg == "would like to communicate with":

                self.sender = client_name
                self.link_already_created = 1
                with open('test.txt', 'a') as f:
                    f.write(f"{self.jointly} Link with 1 hope with {self.receiver}\n")
                yield from self.create_quantum_link_direct_sender(context, request, queue_protocol)

            self.msg = ""
            count = count + 1
    def ask_availability(self, context, connection):
        for i in range(len(connection)):
            csocket = context.csockets[connection[i]]
            csocket.send(self.msg)

    def send_answer(self, context, counter):
        csocket = context.csockets[self.sender]
        csocket.send(f"Available, counter: {counter}")

    def Notsend_answer(self, context, client_name):
        csocket = context.csockets[client_name]
        csocket.send("No Available")

    def Restore_availability(self, context):
        csocket = context.csockets[self.sender]
        # self.availability = 1
        csocket.send(f"Restore availability {self.first}")

    def create_quantum_link_initial(self, queue_protocol, context, request):
        csocket = context.csockets[self.sender2]
        epr_socket = context.epr_sockets[self.sender2]
        connection = context.connection
        q = Qubit(connection)
        set_qubit_state(q, self.phi, self.theta)
        yield from connection.flush()
        # Create EPR pairs
        csocket.send("Sending epr")
        epr = epr_socket.create_keep()[0]
        yield from connection.flush()

        # sending buffer signal
        csocket.send("I'm the first")
        measurements_obtained = []
        while True:
            client_name, msg = yield from queue_protocol.pop()
            if "want to communicate with" not in msg and "Restore availability" not in msg and "Available" not in msg:
                break
            request.append((msg, client_name))
        elements = msg[1:-1].split(', ')
        for i in elements:
            measurements_obtained.append(i)
        for i in measurements_obtained:
            if i == '1':
                epr.Z()
        yield from connection.flush()
        mo = epr.measure()
        yield from connection.flush()
        mo = int(mo)
        print(self.jointly + " I measured: " + mo.__str__())
        self.end_time = time.time()
        elapsed_time = self.end_time - self.start_time
        with open('time.txt', 'a') as f:
            f.write(f"{self.jointly} connected with a delay of {elapsed_time} with {self.receiver}\n")
        self.receiver = " "
        self.send_message(f"Restore availability {self.jointly}", context)
        self.restore_values()
        self.message_checker(context, request, queue_protocol)

    def create_quantum_link_intermediate(self, queue_protocol, context, request):
        csocket1 = context.csockets[self.sender]
        csocket2 = context.csockets[self.sender2]
        epr_socket1 = context.epr_sockets[self.sender]
        epr_socket2 = context.epr_sockets[self.sender2]
        intermediate_measurements = []
        measurements = []

        connection = context.connection
        epr0 = epr_socket1.recv_keep()[0]
        yield from connection.flush()

        csocket2.send("Sending epr")
        epr1 = epr_socket2.create_keep()[0]
        yield from connection.flush()

        epr0.cnot(epr1)
        epr0.H()
        m0 = epr0.measure()
        m1 = epr1.measure()
        yield from connection.flush()

        # client_name, msg = yield from queue_protocol.pop()
        while True:
            client_name, msg = yield from queue_protocol.pop()
            # print(msg)
            if "want to communicate with" not in msg and "Restore availability" not in msg and "Available" not in msg:
                break
            request.append((msg, client_name))
        if msg == "I'm the first":
            intermediate_measurements.append(int(m1))
            csocket2.send(intermediate_measurements.__str__())
        elif msg == "I'm last":
            measurements.append(int(m0))
            csocket1.send(measurements.__str__())

        # print(f"{self.jointly}: {msg}")
        else:
            if client_name == self.sender:
                elements = msg[1:-1].split(', ')
                for i in elements:
                    intermediate_measurements.append(int(i))
                intermediate_measurements.append(int(m1))
                csocket2.send(intermediate_measurements.__str__())
            else:
                elements = msg[1:-1].split(', ')
                for i in elements:
                    measurements.append(int(i))
            measurements.append(int(m0))
            csocket1.send(measurements.__str__())

        while True:
            client_name, msg = yield from queue_protocol.pop()
            if "want to communicate with" not in msg and "Restore availability" not in msg and "Available" not in msg:
                break
            request.append((msg, client_name))
            # print(msg)
        if msg == "I'm the first":
            intermediate_measurements.append(int(m1))
            csocket2.send(intermediate_measurements.__str__())
        elif msg == "I'm last":
            measurements.append(int(m0))
            csocket1.send(measurements.__str__())

        # print(f"{self.jointly}: {msg}")
        else:
            if client_name == self.sender:
                elements = msg[1:-1].split(', ')
                for i in elements:
                    intermediate_measurements.append(int(i))
                intermediate_measurements.append(int(m1))
                csocket2.send(intermediate_measurements.__str__())
            else:
                elements = msg[1:-1].split(', ')
                for i in elements:
                    measurements.append(int(i))
            measurements.append(int(m0))
            csocket1.send(measurements.__str__())


        self.send_message(f"Restore availability {self.first}", context)
        self.restore_values()
        self.message_checker(context, request, queue_protocol)

    def create_quantum_link_last(self, queue_protocol, context, request):
        csocket = context.csockets[self.sender]
        epr_socket = context.epr_sockets[self.sender]
        connection = context.connection
        q = Qubit(connection)
        set_qubit_state(q, self.phi, self.theta)
        yield from connection.flush()
        epr = epr_socket.recv_keep()[0]
        yield from connection.flush()
        csocket.send("I'm last")
        intermediate_measurements = []
        while True:
            client_name, msg = yield from queue_protocol.pop()
            if "want to communicate with" not in msg and "Restore availability" not in msg and "Available" not in msg:
                break
            request.append((msg, client_name))
        elements = msg[1:-1].split(', ')
        for i in elements:
            intermediate_measurements.append(i)
        for i in intermediate_measurements:
            if i == '1':
                epr.X()
        yield from connection.flush()
        mo = epr.measure()
        yield from connection.flush()
        mo = int(mo)
        print(self.jointly + " I measured: " + mo.__str__())
        self.send_message(f"Restore availability {self.first}", context)
        self.restore_values()
        self.message_checker(context, request, queue_protocol)

    def create_quantum_link_direct_sender(self, context, request, queue_protocol):
        csocket = context.csockets[self.sender]
        epr_socket = context.epr_sockets[self.sender]
        connection = context.connection

        q = Qubit(connection)
        set_qubit_state(q, self.phi, self.theta)

        # Create EPR pairs
        epr = epr_socket.create_keep()[0]

        m1 = epr.measure()
        yield from connection.flush()

        # Send the correction information
        m1 = int(m1)

        csocket.send(m1)

        print(self.jointly + " I measured: " + m1.__str__())
        self.restore_values()
        self.end_time = time.time()
        elapsed_time = self.end_time - self.start_time


        with open('time.txt', 'a') as f:
            f.write(f"{self.jointly} connected with a delay of {elapsed_time} with {self.receiver}\n")
        self.receiver = ""
        self.restore_values()
        self.message_checker(context, request, queue_protocol)

    def create_quantum_link_direct_received(self, queue_protocol, context, request):
        csocket = context.csockets[self.sender]
        epr_socket = context.epr_sockets[self.sender]
        connection = context.connection
        csocket.send("would like to communicate with")

        epr = epr_socket.recv_keep()[0]
        yield from connection.flush()

        # Get the corrections
        while True:
            client_name, msg = yield from queue_protocol.pop()
            if msg.isdigit():
                break
            request.append((msg, client_name))
        m1 = int(msg)
        if int(m1) == 1:
            epr.Z()
        m2 = epr.measure()
        yield from connection.flush()
        m2 = int(m2)
        print(self.jointly + " I measured: " + m2.__str__())
        # self.availability = 1
        self.restore_values()
        self.message_checker(context, request, queue_protocol)

    def message_checker(self, context, request, queue_protocol):
        # print(f"{self.first}")
        request_non_startswith_first = [item for item in request if not item[0].startswith(self.first)]
        request_non_startswith_first = [item for item in request_non_startswith_first if not item[0].startswith("Restore availability") and "Available" not in item[0]]
        # print(f"{self.jointly}: {self.first}")
        request = request_non_startswith_first
        self.first = ""
        # print(request)
        if len(request) > 0:

            msg, client_name = request.pop()
            #
            # print(f"{self.jointly} ho ricevuto {msg}")
            connection = []
            # print("Ripristino")

            for i in range(len(self.link)):
                if self.link[i] != client_name:
                    connection.append(self.link[i])
            self.msg = msg
            if "want to communicate with" in msg:
                submission = self.msg.split("want to communicate with ")
                # print(submission)

                if self.jointly == submission[1]:
                    if self.availability == 1:
                        # print("start")
                        self.availability = 0
                        self.last = 1
                        self.sender = client_name
                        self.send_answer(context, 0)
                        string = msg.split(" ")

                        self.first = string[0]
                        if self.link_already_created == 0:
                            self.link_already_created = 1

                    else:
                        request.append((msg, client_name))
                else:
                    self.availability = 0
                    self.sender = client_name
                    string = msg.split(" ")
                    self.first = string[0]
                    self.ask_availability(context, connection)

            # elif msg == "direct connection":
            #     self.sender = client_name
            #     self.availability = 0
            #     print("direct connection")
            #     yield from self.create_quantum_link_direct_received(queue_protocol, context, request)

    def restore_values(self):
        self.msg = ""
        self.availability = 1
        self.sender = None
        self.sender2 = None
        self.initiator = 0
        self.last = 0
        self.link_already_created = 0

