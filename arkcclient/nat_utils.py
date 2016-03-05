import socket
import asyncore
import logging
import time
import threading

from server import ServerReceiver


class punching_server(asyncore.dispatcher):

    def __init__(self, ctl):
        asyncore.dispatcher.__init__(self)
        self.ctl = ctl
        # A client-server matching with client's address as key and server's
        # address as value
        self.client_matching = {}
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind(("127.0.0.1", ctl.punching_server_port))
        self.listen(6)

    def handle_accept(self):
        conn, self.cli_addr = self.accept()
        punching_server_handler(conn)


class punching_server_handler(asyncore.dispatcher):

    def __init__(self, sock):
        asyncore.dispatcher.__init__(self, sock)
        self.read_buffer = ""
        self.write_buffer = ""
        self.sent_buffer = 0
        self.read_finished = 0

    def handle_write(self):
        sent = self.send(self.write_buffer)
        self.write_buffer = self.write_buffer[sent:]

    def match_client(self, data):
        # TODO: recieve authentication strings from client and server, then
        # match them in client_matching, at last return 0 if
        # its from client or 1 if its from server
        pass

    def handle_read(self):
        self.read_buffer += self.recv(512)
        if '\n' in self.read_buffer:
            self.read_finished = 1
            # all below should be done in matching
            self.match_client(self.read_buffer.split('\n'[0]))
#             if :
#
#                 for cli, ser in self.client_matching.items():
#                     if ser == self.cli_addr:
#                         self.write_buffer = str(
#                             cli[0]) + ' ' + str(cli[1] + '\n')
#                         self.client_matching.pop(cli)
#                         break
#             else:
#                 ser = self.client_matching[self.cli_addr]
#                 self.write_buffer = str(ser[0] + ' ' + str(ser[1]) + '\n')

    def writable(self):
        return len(self.write_buffer) > 0

        if not self.write_buffer:
            if self.source == 1:
                return (self.cli_addr in self.client_matching.values())
            elif self.source == 0:
                return (self.cli_addr in self.client_matching.keys())
            else:
                return 0
        else:
            return (self.sent_buffer == len(self.write_buffer))

    def readable(self):
        return not self.read_finished


class tcp_punching_connect(asyncore.dispatcher):

    def __init__(self, addr, binding_port, ctl):
        asyncore.dispatcher.__init__(self)
        self.remote_addr = addr
        self.port = binding_port
        self.ctl = ctl
        self.finished = False
        self.wbuffer = self.auth_string()
        self.rbuffer = ""
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(("127.0.0.1", self.port))
        self.connect(self.remote_addr)

    def readable(self):
        return not (self.finished)

    def handle_connect(self):
        pass

    def writable(self):
        return (len(self.wbuffer) > 0)

    def handle_write(self):
        sent = self.send(self.wbuffer)
        self.wbuffer = self.buffer[sent:]

    def auth_string(self):
        pass

    def handle_read(self):
        self.rbuffer += self.recv(512)
        if ('\n' in self.rbuffer):
            data = self.rbuffer.split(" ")
            if len(data) != 2:
                self.close()  # TODO: return failure
        # TODO: recv may not get complete message back!
        addr = (data[0], int(data[1]))
        self.p = threading.Thread(
            target=tcp_punching_send(addr, self.port, self.ctl))
        self.p.start()
        self.finished = True


class tcp_punching_send(threading.Thread):

    def __init__(self, addr, port, ctl):
        self.ctl = ctl
        self._stopevent = threading.Event()
        self._stopevent.set()
        self.addr = addr
        self.port = port
        threading.Thread.__init__(self)

    def run(self):
        # TODO: counting
        # TODO: be reused
        while True:
            self._stopevent.wait()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", self.port))
            s.settimeout(3)
            try:
                s.connect(self.addr)
                ServerReceiver(s, self.ctl)
            except Exception as err:
                # error processing should be in types
                s.close()

    def join(self, timeout=None):
        self._stopevent.clear()
        threading.Thread.join(self, timeout)
