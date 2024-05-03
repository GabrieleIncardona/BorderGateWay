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
    collegamento = None
    mittente = None
    mittente2 = None
    iniziatore = 0
    ultimo = 0
    collegamento_gia_creato = 0
    ciclo = True

    def __init__(self, insieme, link, params: TeleportParams):
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
        self.insieme = insieme
        self.link = link
        self.phi = params.phi
        self.theta = params.theta

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="controller_program",
            csockets=self.link,
            epr_sockets=self.link,
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        def send_message(msg):
            csocket1 = context.csockets[self.link[0]]
            csocket2 = context.csockets[self.link[1]]
            self.iniziatore = 1
            self.msg = msg
            # yield from connection.flush()

            csocket1.send(msg)
            csocket2.send(msg)
            # print("Hello")

        def receive_message():
            queue_protocol = QueueProtocol()
            queue_protocol.start()

            listener = (
                CSocketListener(context, self.link[0], queue_protocol, self.logger))
            listener.start()

            listener = CSocketListener(context, self.link[1], queue_protocol, self.logger)
            listener.start()

            while self.ciclo:
                client_name, msg = yield from queue_protocol.pop()
                # print("io insieme:" + self.insieme + " ho ricevuto: " + client_name)
                # print("io insieme:" + self.insieme + " ho ricevuto: " + msg)

                if client_name == self.link[0]:
                    self.collegamento = self.link[1]
                else:
                    self.collegamento = self.link[0]
                self.msg = msg
                if self.msg.startswith("Voglio comunicare con "):
                    self.mittente = client_name
                    sottomessaggio = self.msg.split("Voglio comunicare con ")
                    if self.insieme == sottomessaggio[1]:
                        if self.disponibilita == 1:
                            self.disponibilita = 0
                            self.ultimo = 1
                            send_risposta()
                        else:
                            Notsend_risposta()
                    else:
                        if self.disponibilita == 1:
                            print("io insieme:" + self.insieme + " sto inviando: " + msg)
                            chiedi_disponibilita()
                        else:
                            Notsend_risposta()
                elif self.msg == "Disponibile":
                    if self.collegamento_gia_creato == 0:
                        self.collegamento_gia_creato = 1
                        self.mittente2 = self.mittente

                        if self.iniziatore == 0:
                            send_risposta()
                        else:
                            print("io insieme:" + self.insieme + " sto creando entanglement ")
                            self.mittente = client_name
                            self.mittente2 = client_name
                            yield from create_quantum_link()
                    else:
                        ripristina_disponibilita()
                elif self.msg.startswith("Invio epr"):
                    self.mittente = client_name
                    print("Sto eseguendo il collegamento entenglement")
                    self.ciclo = False
                    yield from rcv_quantum_link()

                elif self.msg == "Ripristina disponibilita":
                    ripristina_disponibilita()

                else:
                    return
                self.msg = " "

        def chiedi_disponibilita():
            csocket = context.csockets[self.collegamento]
            csocket.send(self.msg)

        def send_risposta():
            csocket = context.csockets[self.mittente]
            print("io insieme:" + self.insieme + " sto inviando: Disponibile")
            csocket.send("Disponibile")

        def Notsend_risposta():
            csocket = context.csockets[self.mittente]
            csocket.send("No disponibile")

        def ripristina_disponibilita():
            csocket = context.csockets[self.mittente]
            csocket.send("Ripristina disponibilita")

        def create_quantum_link():
            csocket = context.csockets[self.mittente2]
            epr_socket = context.epr_sockets[self.mittente2]
            connection = context.connection

            q = Qubit(connection)
            set_qubit_state(q, self.phi, self.theta)
            yield from connection.flush()
            print("QUBIT STATE")
            # Create EPR pairs
            csocket.send("Invio epr")
            epr = epr_socket.create_keep()[0]
            yield from connection.flush()
            print("EPR CREATE")
            # Teleport
            q.cnot(epr)
            q.H()

            m1 = q.measure()
            m2 = epr.measure()
            yield from connection.flush()

            m1, m2 = int(m1), int(m2)
            # self.logger.info(
            #    f"Performed teleportation protocol with measured corrections: m1 = {m1}, m2 = {m2}"
            # )
            csocket.send_structured(StructuredMessage("Corrections", f"{m1},{m2}"))
            print("m1: " + m1.__str__() + " m2: " + m2.__str__())
            original_dm = get_reference_state(self.phi, self.theta)

            return {"m1": m1, "m2": m2, "original_dm": original_dm}

        def rcv_quantum_link():
            csocket = context.csockets[self.mittente]
            epr_socket = context.epr_sockets[self.mittente]
            connection = context.connection
            print("WAIT EPR")
            epr = epr_socket.recv_keep()[0]
            yield from connection.flush()
            print("EPR RECEIVED")

            msg = yield from csocket.recv_structured()
            assert isinstance(msg, StructuredMessage)
            self.msg = msg.payload
            print(self.msg)
            m1, m2 = self.msg.split(",")
            print("HELLO")
            if int(m2) == 1:
                epr.X()
            if int(m1) == 1:
                epr.Z()

            yield from connection.flush()

            final_dm = get_qubit_state(epr, self.insieme)
            if self.ultimo == 0:
                yield from create_quantum_link()
            return {"final_dm": final_dm}

        if self.insieme == "A1":
            send_message("Voglio comunicare con D1")
        yield from receive_message()
