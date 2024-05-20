import random

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
    cycle = True
    receiver = ""

    def __init__(self, jointly, link, params: TeleportParams, senders, receivers):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.jointly = jointly
        self.link = link
        self.phi = params.phi
        self.theta = params.theta
        self.senders = senders
        self.receivers = receivers

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
                self.send_message(f"I want to communicate with {self.receiver}", context)
                print(f"{self.jointly} would like to communicate with {self.receiver}")

        yield from self.receive_message(context)

    def send_message(self, msg, context):
        if self.receiver in self.link:
            csocket1 = context.csockets[self.receiver]
            csocket1.send("direct connection")
            self.initiator = 1
            self.msg = msg
            self.availability = 0
            return
        else:
            csocket = []
            for i in range(len(self.link)):
                csocket.append(context.csockets[self.link[i]])
            self.initiator = 1
            self.msg = msg
            self.availability = 0
            # yield from connection.flush()
            for i in range(len(self.link)):
                csocket[i].send(msg)

    def receive_message(self, context):
        queue_protocol = QueueProtocol()
        queue_protocol.start()

        connection = []

        for i in range(len(self.link)):
            listener = (
                CSocketListener(context, self.link[i], queue_protocol, self.logger))
            listener.start()
        while self.cycle:
            client_name, msg = yield from queue_protocol.pop()

            for i in range(len(self.link)):
                if self.link[i] != client_name:
                    connection.append(self.link[i])

            self.msg = msg
            if self.msg.startswith("I want to communicate with "):
                self.sender = client_name
                submission = self.msg.split("I want to communicate with ")
                if self.jointly == submission[1]:
                    if self.availability == 1:
                        self.availability = 0
                        self.last = 1
                        self.send_answer(context)
                    else:
                        self.Notsend_answer(context)
                else:
                    if self.availability == 1:
                        self.ask_availability(context, connection)
                    else:
                        self.Notsend_answer(context)
            elif self.msg == "Available":
                if self.link_already_created == 0:
                    self.link_already_created = 1
                    self.sender2 = client_name

                    if self.initiator == 0:
                        self.send_answer(context)
                    else:
                        self.sender = client_name
                        self.sender2 = client_name
                        self.cycle = False
                        yield from self.create_quantum_link_initial(queue_protocol, context)
                else:
                    self.Restore_availability(context)

            elif self.msg.startswith("Sending epr"):
                self.sender = client_name
                self.cycle = False
                if self.last == 0:
                    yield from self.create_quantum_link_intermediate(queue_protocol, context)
                else:
                    yield from self.create_quantum_link_last(queue_protocol, context)
            elif self.msg == "Restore availability":
                self.Restore_availability(context)

            elif self.msg == "direct connection":
                self.sender = client_name
                self.availability = 0
                yield from self.create_quantum_link_direct_received(queue_protocol, context)

            elif self.msg == "would like to communicate with":
                self.sender = client_name
                yield from self.create_quantum_link_direct_sender(context)

            self.msg = " "

    def ask_availability(self, context, connection):
        for i in range(len(connection)):
            csocket = context.csockets[connection[i]]
            csocket.send(self.msg)

    def send_answer(self, context):
        csocket = context.csockets[self.sender]
        csocket.send("Available")

    def Notsend_answer(self, context):
        csocket = context.csockets[self.sender]
        csocket.send("No Available")

    def Restore_availability(self, context):
        csocket = context.csockets[self.sender]
        self.availability = 1
        csocket.send("Restore availability")

    def create_quantum_link_initial(self, queue_protocol, context):
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
        client_name, msg = yield from queue_protocol.pop()
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

    def create_quantum_link_intermediate(self, queue_protocol, context):
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
        client_name, msg = yield from queue_protocol.pop()
        
        if msg != "I'm the first":
            elements = msg[1:-1].split(', ')
            for i in elements:
                intermediate_measurements.append(int(i))
        epr0.cnot(epr1)
        epr0.H()
        m0 = epr0.measure()
        m1 = epr1.measure()
        yield from connection.flush()
        intermediate_measurements.append(int(m1))
        csocket2.send(intermediate_measurements.__str__())
        client_name, msg = yield from queue_protocol.pop()
        if msg != "I'm last":
            elements = msg[1:-1].split(', ')
            for i in elements:
                measurements.append(int(i))
        measurements.append(int(m0))
        csocket1.send(measurements.__str__())

    def create_quantum_link_last(self, queue_protocol, context):
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
        client_name, msg = yield from queue_protocol.pop()
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

    def create_quantum_link_direct_sender(self, context):
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

    def create_quantum_link_direct_received(self, queue_protocol, context):
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
            csocket1 = context.csockets[client_name]
            csocket1.send("No Available")
        m1 = int(msg)
        if int(m1) == 1:
            epr.Z()
        m2 = epr.measure()
        yield from connection.flush()
        m2 = int(m2)
        print(self.jointly + " I measured: " + m2.__str__())
