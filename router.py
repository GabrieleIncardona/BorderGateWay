import logging
import select
import asyncio  # Aggiunto asyncio per gestire il timeout

import numpy
from netqasm.sdk import Qubit
from netqasm.sdk.classical_communication.message import StructuredMessage
from netqasm.sdk.toolbox.state_prep import set_qubit_state

from squidasm.run.stack.run import run
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
    insieme = ""
    msg = ""
    disponibilita = 1
    collegamento = None
    mittente = None
    mittente2 = None
    iniziatore = 0
    ultimo = 0
    collegamento_gia_creato = 0

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
            csockets=[self.link],
            epr_sockets=[self.link],
            max_qubits=2,
        )

    async def run(self, context: ProgramContext):
        async def send_message(msg):
            csocket1 = context.csockets[self.link[0]]
            csocket2 = context.csockets[self.link[1]]
            self.iniziatore = 1
            self.msg = msg

            csocket1.send(self.msg)
            csocket2.send(self.msg)

        async def receive_message():
            csocket1 = context.csockets[self.link[0]]
            csocket2 = context.csockets[self.link[1]]

            socket_list = [csocket1, csocket2]

            lettura, _, _ = select.select(socket_list, [], [], 100)  # Timeout di 100 secondi

            if not lettura:  # Se il timeout è scaduto
                return

            for sock in lettura:
                if sock == csocket1:
                    self.collegamento = self.link[0]
                    self.mittente = self.link[1]  # Memorizza il mittente
                elif sock == csocket2:
                    self.collegamento = self.link[1]
                    self.mittente = self.link[0]  # Memorizza il mittente

                self.msg = sock.recv(1024).decode()

            if self.msg.startswith("Voglio collegarmi con "):
                sottomessaggio = self.msg.split("Voglio collegarmi con ")
                if self.insieme == sottomessaggio[1]:
                    if self.disponibilita == 1:
                        self.disponibilita = 0
                        self.ultimo = 1
                        await send_risposta()
                    else:
                        await chiedi_disponibilita()
                else:
                    if self.disponibilita == 1:
                        await send_message(self.msg)
                    else:
                        await Notsend_risposta()
            elif self.msg == "Disponibile":
                if self.collegamento_gia_creato == 0:
                    self.collegamento_gia_creato = 1
                    self.mittente2 = self.mittente
                    if self.iniziatore == 0:
                        await send_risposta()
                    else:
                        await create_quantum_link()
                else:
                    await ripristina_disponibilita()
            elif self.msg.startswith("Performed teleportation protocol with measured corrections:"):
                if self.ultimo == 0:
                    await create_quantum_link()

            elif self.msg == "Ripristina disponibilita":
                await ripristina_disponibilita()

        async def chiedi_disponibilita():
            csocket = context.csockets[self.collegamento]
            csocket.send(self.msg)

        async def send_risposta():
            csocket = context.csockets[self.mittente]
            csocket.send("Disponibile")

        async def Notsend_risposta():
            csocket = context.csockets[self.mittente]
            csocket.send("No disponibile")

        async def ripristina_disponibilita():
            csocket = context.csockets[self.mittente]
            csocket.send("Ripristina disponibilita")

        async def create_quantum_link():
            csocket = context.csockets[self.mittente2]
            epr_socket = context.epr_sockets[self.mittente2]
            connection = context.connection

            q = Qubit(connection)
            set_qubit_state(q, self.phi, self.theta)

            # Create EPR pairs
            epr = epr_socket.create_keep()[0]

            # Teleport
            q.cnot(epr)
            q.H()
            m1 = q.measure()
            m2 = epr.measure()
            connection.flush()

            m1, m2 = int(m1), int(m2)

            self.logger.info(
                f"Performed teleportation protocol with measured corrections: m1 = {m1}, m2 = {m2}"
            )

            csocket.send_structured(StructuredMessage("Corrections", f"{m1},{m2}"))

            original_dm = get_reference_state(self.phi, self.theta)

            return {"m1": m1, "m2": m2, "original_dm": original_dm}

        if self.insieme == "A1":
            await send_message("Voglio comunicare con D1")

        while 1:
            await receive_message()  # Attendere la ricezione del messaggio
