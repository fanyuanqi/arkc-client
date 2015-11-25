import threading
import logging
import os
import random
import string
import binascii
import hashlib
import dns.resolver

from time import sleep

from common import get_ip
import pyotp

CLOSECHAR = chr(4) * 5
DNSSERVERADDR = "114.114.114.114"

class coordinate(object):

    '''Used to request connections and deal with part of authentication'''

    def __init__(self, ctl_domain, localcert, localcert_sha1, remotecert, localpub, required, remote_port, swapcount=5):
        self.remotepub = remotecert
        self.localcert = localcert
        self.localcert_sha1 = localcert_sha1
        self.authdata = localpub
        self.required = required
        self.remote_port = remote_port
        self.swapcount = swapcount
        self.ctl_domain = ctl_domain
        self.ip = get_ip()
        self.clientreceivers = {}
        self.ready = None

        self.recvs = []  # For serverreceivers
        self.str = (''.join(random.choice(string.ascii_letters) for i in range(16))).encode('ASCII')  # #TODO:stronger random required
        self.check = threading.Event()
        self.check.set()
        req = threading.Thread(target=self.reqconn)
        req.setDaemon(True)
        req.start()

    def newconn(self, recv):
        # Called when receive new connections
        self.recvs.append(recv)
        if self.ready is None:
            self.ready = recv
            recv.preferred = True
        self.refreshconn()
        if len(self.recvs) + 2 >= self.required:
            self.check.clear()
        logging.info("Running socket %d" % len(self.recvs))

    def closeconn(self, conn):
        # Called when a connection is closed
        if self.ready is not None:
            if self.ready.closing:
                if len(self.recvs) > 0:
                    self.ready = self.recvs[0]
                    self.recvs[0].preferred = True
                    self.refreshconn()
                else:
                    self.ready = None
        try:
            self.recvs.remove(conn)
        except ValueError as err:
            pass
        if len(self.recvs) < self.required:
            self.check.set()
        logging.info("Running socket %d" % len(self.recvs))

    def reqconn(self):
        # Sending DNS queries
        my_resolver = dns.resolver.Resolver()
        my_resolver.nameservers = [DNSSERVERADDR]
        while True:
            self.check.wait()  # Start the request when the client needs connections
            requestdata = self.generatereq()
            my_resolver.query(requestdata + "." + self.ctl_domain)
            sleep(0.1)


    def generatereq(self):
        # Generate strings for authentication
        """
            The return encrypted message should be
            (required_connection_number (HEX, 2 bytes) +
            used_remote_listening_port (HEX, 4 bytes) +
            sha1(cert_pub) ,
            pyotp.TOTP(pri_sha1 + ip_in_number_form + salt) , ## TODO: client identity must be checked
            main_pw,##must send in encrypted form to avoid MITM
            ip_in_number_form,
            salt
            Total length is 2 + 4 + 40 = 46, 16, 16, ?, 16
        """

        required_hex = "%X" % min((self.required), 255)
        remote_port_hex = '%X' % self.remote_port
        if len(required_hex) == 1:
            required_hex = '0' + required_hex
        remote_port_hex = '0' * (4 - len(remote_port_hex)) + remote_port_hex
        myip = self.ip
        salt = binascii.hexlify(os.urandom(16)).decode("ASCII")
        h = hashlib.sha256()
        h.update((self.localcert_sha1 + str(myip) + salt).encode('utf-8'))
        hotp = pyotp.TOTP(h.hexdigest()).now()
        return  (required_hex + \
                remote_port_hex + \
                self.authdata + '.' + \
                str(hotp) + '.' + \
                binascii.hexlify(self.str).decode("ASCII") + '.' + \
                str(myip) + '.' + \
                salt)

    def issufficient(self):
        return len(self.recvs) >= self.required

    def refreshconn(self):
        next_conn = random.choice(self.recvs)
        self.ready.preferred = False
        self.ready = next_conn
        next_conn.preferred = True

    def register(self, clirecv):
        cli_id = None
        if len(self.recvs) == 0:
            return None
        while (cli_id is None) or (cli_id in self.clientreceivers):
            a = list(string.ascii_letters)
            random.shuffle(a)
            cli_id = ''.join(a[:2])
        self.clientreceivers[cli_id] = clirecv
        return cli_id

    def remove(self, cli_id):
        if len(self.recvs) > 0:
            self.ready.id_write(cli_id, CLOSECHAR)
        self.clientreceivers.pop(cli_id)
