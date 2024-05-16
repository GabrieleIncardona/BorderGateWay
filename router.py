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
    disponibilita = 1
    mittente = None
    mittente2 = None
    iniziatore = 0
    ultimo = 0
    collegamento_gia_creato = 0
    ciclo = True
    receveid = ""

    def __init__(self, insieme, link, params: TeleportParams, senders, receiveds):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.insieme = insieme
        self.link = link
        self.phi = params.phi
        self.theta = params.theta
        self.senders = senders
        self.receiveds = receiveds

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="controller_program",
            csockets=self.link,
            epr_sockets=self.link,
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        # self.disponibilita = 1

        # if self.insieme == "A1":
        #    self.send_message("Voglio comunicare con D1", context)

        if self.insieme in self.senders:
            self.receveid = random.choice(self.receiveds)
            if self.insieme != self.receveid:
                self.send_message(f"Voglio comunicare con {self.receveid}", context)
                print(f"{self.insieme} would like to communicate with {self.receveid}")

        yield from self.receive_message(context)

    def send_message(self, msg, context):
        if self.receveid in self.link:
            csocket1 = context.csockets[self.receveid]
            csocket1.send("direct connection")
            self.iniziatore = 1
            self.msg = msg
            self.disponibilita = 0
            return
        else:
            csocket = []
            for i in range(len(self.link)):
                csocket.append(context.csockets[self.link[i]])
            self.iniziatore = 1
            self.msg = msg
            self.disponibilita = 0
            # yield from connection.flush()
            for i in range(len(self.link)):
                csocket[i].send(msg)

    def receive_message(self, context):
        # if self.insieme == "B1":
        #    print(f"{self.insieme:} {self.link}")
        queue_protocol = QueueProtocol()
        queue_protocol.start()

        collegamento = []

        for i in range(len(self.link)):
            listener = (
                CSocketListener(context, self.link[i], queue_protocol, self.logger))
            listener.start()
        while self.ciclo:
            client_name, msg = yield from queue_protocol.pop()
            # print(client_name)

            for i in range(len(self.link)):
                if self.link[i] != client_name:
                    collegamento.append(self.link[i])
                    #print(f"{self.insieme} {self.link[i]}")

            self.msg = msg
            # print(f"{self.insieme} ho ricevuto {self.msg} ")
            if self.msg.startswith("Voglio comunicare con "):
                self.mittente = client_name
                sottomessaggio = self.msg.split("Voglio comunicare con ")
                if self.insieme == sottomessaggio[1]:
                    if self.disponibilita == 1:
                        self.disponibilita = 0
                        self.ultimo = 1
                        self.send_risposta(context)
                    else:
                        self.Notsend_risposta(context)
                else:
                    if self.disponibilita == 1:
                        self.chiedi_disponibilita(context, collegamento)
                    else:
                        self.Notsend_risposta(context)
            elif self.msg == "Disponibile":
                if self.collegamento_gia_creato == 0:
                    self.collegamento_gia_creato = 1
                    self.mittente2 = client_name

                    #print(f"{self.insieme} disponibile")

                    if self.iniziatore == 0:
                        self.send_risposta(context)
                    else:
                        # print("io insieme:" + self.insieme + " sto creando entanglement ")
                        self.mittente = client_name
                        self.mittente2 = client_name
                        self.ciclo = False
                        yield from self.create_quantum_link_iniziale(queue_protocol, context)
                else:
                    self.ripristina_disponibilita(context)

            elif self.msg.startswith("Invio epr"):
                self.mittente = client_name
                self.ciclo = False
                # print("io insieme:" + self.insieme + " sto creando entanglement ")
                if self.ultimo == 0:
                    yield from self.create_quantum_link_intermedio(queue_protocol, context)
                else:
                    yield from self.create_quantum_link_ultimo(queue_protocol, context)
            elif self.msg == "Ripristina disponibilita":
                self.ripristina_disponibilita(context)

            elif self.msg == "direct connection":
                self.mittente = client_name
                yield from self.create_quantum_link_direct_received(queue_protocol, context)

            elif self.msg == "would like to communicate with":
                self.mittente = client_name
                yield from self.create_quantum_link_direct_sender(context)

            self.msg = " "

    def chiedi_disponibilita(self, context, collegamento):
        #print(f"{self.insieme} {collegamento}")
        for i in range(len(collegamento)):
            csocket = context.csockets[collegamento[i]]
            csocket.send(self.msg)

    def send_risposta(self, context):
        csocket = context.csockets[self.mittente]
        csocket.send("Disponibile")

    def Notsend_risposta(self, context):
        csocket = context.csockets[self.mittente]
        csocket.send("No disponibile")

    def ripristina_disponibilita(self, context):
        csocket = context.csockets[self.mittente]
        self.disponibilita = 1
        csocket.send("Ripristina disponibilita")

    def create_quantum_link_iniziale(self, queue_protocol, context):
        csocket = context.csockets[self.mittente2]
        epr_socket = context.epr_sockets[self.mittente2]
        connection = context.connection
        q = Qubit(connection)
        set_qubit_state(q, self.phi, self.theta)
        yield from connection.flush()
        # Create EPR pairs
        csocket.send("Invio epr")
        epr = epr_socket.create_keep()[0]
        yield from connection.flush()

        # invio segnale di buffer
        csocket.send("sono il primo")
        misurazioni_ottenute = []
        client_name, msg = yield from queue_protocol.pop()
        # print(f"{self.insieme } ho ricevuto {msg}")
        elementi = msg[1:-1].split(', ')
        for i in elementi:
            misurazioni_ottenute.append(i)
        for i in misurazioni_ottenute:
            if i == '1':
                epr.Z()
        yield from connection.flush()
        # print(f"{self.insieme}: {get_qubit_state(epr, node_name=self.insieme, full_state=True)}")
        mo = epr.measure()
        yield from connection.flush()
        mo = int(mo)
        print(self.insieme + " ho misurato: " + mo.__str__())

    def create_quantum_link_intermedio(self, queue_protocol, context):
        csocket1 = context.csockets[self.mittente]
        csocket2 = context.csockets[self.mittente2]
        epr_socket1 = context.epr_sockets[self.mittente]
        epr_socket2 = context.epr_sockets[self.mittente2]
        misurazioni_intermedie = []
        misurazioni = []

        connection = context.connection
        epr0 = epr_socket1.recv_keep()[0]
        yield from connection.flush()

        csocket2.send("Invio epr")
        epr1 = epr_socket2.create_keep()[0]
        yield from connection.flush()
        client_name, msg = yield from queue_protocol.pop()
        # print(f"{self.insieme} ho ricevuto {msg} da {client_name}")
        if msg != "sono il primo":
            elementi = msg[1:-1].split(', ')
            for i in elementi:
                misurazioni_intermedie.append(int(i))
        epr0.cnot(epr1)
        epr0.H()
        m0 = epr0.measure()
        m1 = epr1.measure()
        yield from connection.flush()
        misurazioni_intermedie.append(int(m1))
        csocket2.send(misurazioni_intermedie.__str__())
        client_name, msg = yield from queue_protocol.pop()
        if msg != "sono l'ultimo":
            elementi = msg[1:-1].split(', ')
            for i in elementi:
                misurazioni.append(int(i))
        misurazioni.append(int(m0))
        csocket1.send(misurazioni.__str__())

    def create_quantum_link_ultimo(self, queue_protocol, context):
        csocket = context.csockets[self.mittente]
        epr_socket = context.epr_sockets[self.mittente]
        connection = context.connection
        q = Qubit(connection)
        set_qubit_state(q, self.phi, self.theta)
        yield from connection.flush()
        epr = epr_socket.recv_keep()[0]
        yield from connection.flush()
        csocket.send("sono l'ultimo")
        misurazioni_intermedie = []
        client_name, msg = yield from queue_protocol.pop()
        elementi = msg[1:-1].split(', ')
        # print(f"{self.insieme} ho ricevuto {msg}")
        for i in elementi:
            misurazioni_intermedie.append(i)
        for i in misurazioni_intermedie:
            if i == '1':
                epr.X()
        yield from connection.flush()
        # print(f"{self.insieme}: {get_qubit_state(epr, node_name=self.insieme, full_state=True)}")
        mo = epr.measure()
        yield from connection.flush()
        mo = int(mo)
        print(self.insieme + " ho misurato: " + mo.__str__())

    def create_quantum_link_direct_sender(self, context):
        csocket = context.csockets[self.mittente]
        epr_socket = context.epr_sockets[self.mittente]
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

        print(self.insieme + " ho misurato: " + m1.__str__())

    def create_quantum_link_direct_received(self, queue_protocol, context):
        csocket = context.csockets[self.mittente]
        epr_socket = context.epr_sockets[self.mittente]
        connection = context.connection
        csocket.send("would like to communicate with")

        epr = epr_socket.recv_keep()[0]
        yield from connection.flush()

        # Get the corrections
        client_name, msg = yield from queue_protocol.pop()
        m1 = int(msg)
        if int(m1) == 1:
            epr.X()
        m2 = epr.measure()
        yield from connection.flush()
        m2 = int(m2)
        print(self.insieme + " ho misurato: " + m2.__str__())