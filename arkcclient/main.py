#! /usr/bin/env python3

# By ArkC developers
# Released under GNU General Public License 2

import asyncore
import argparse
import logging
import json
import sys
import random
import os
import stat
import requests

sys.path.insert(0, os.path.dirname(__file__))

from common import certloader, generate_RSA
from coordinator import Coordinate
from server import ServerControl
from client import ClientControl

# Const used in the client.

DEFAULT_LOCAL_HOST = "127.0.0.1"
DEFAULT_REMOTE_HOST = ''
DEFAULT_LOCAL_PORT = 8001
DEFAULT_REQUIRED = 3
DEFAULT_DNS_SERVERS = [["8.8.8.8", 53]]
DEFAULT_OBFS4_EXECADDR = "obfs4proxy"


def main():
    parser = argparse.ArgumentParser(description=None)
    try:
        # Load arguments
        parser.add_argument(
            "-v", dest="v", action="store_true", help="show detailed logs")
        parser.add_argument(
            "-vv", dest="vv", action="store_true", help="show debug logs")
        parser.add_argument('-kg', '--keygen', dest="kg", action="store_true",
                            help="Generate a key string and quit, overriding other options")
        parser.add_argument('--get-meek', dest="dlmeek", action="store_true",
                            help="Download meek to home directory, overriding normal options")
        parser.add_argument('-c', '--config', dest="config", default=None,
                            help="Specify a configuration files, REQUIRED for ArkC Client to start")
        parser.add_argument('-fs', '--frequent-swap', dest="fs", action="store_true",
                            help="Use frequent connection swapping")
        parser.add_argument('-pn', '--public-addr', dest="pn", action="store_true",
                            help="Disable UPnP when you have public network IP address (or NAT has been manually configured)")

        parser.add_argument("-v6", dest="ipv6", default="",
                            help="Enable this option to use IPv6 address (only use it if you have one)")
        print("""ArkC Client V0.1.2,  by ArkC Technology.
The programs is distributed under GNU General Public License Version 2.
""")

        options = parser.parse_args()

        if options.kg:
            print("Generating 2048 bit RSA key.")
            print("Writing to home directory " + os.path.expanduser('~'))
            pri_sha1 = generate_RSA(os.path.expanduser(
                '~' + os.sep + 'arkc_pri.asc'), os.path.expanduser('~' + os.sep + 'arkc_pub.asc'))
            print("SHA1 of the private key is " + pri_sha1)
            print(
                "Please save the above settings to client and server side config files.")
            quit()
        elif options.dlmeek:
            if sys.platform == 'linux2':
                link = "https://github.com/projectarkc/meek/releases/download/v0.2/meek-server"
                localfile = os.path.expanduser('~') + os.sep + "meek-server"
            elif sys.platform == 'win32':
                link = "https://github.com/projectarkc/meek/releases/download/v0.2/meek-server.exe"
                localfile = os.path.expanduser(
                    '~') + os.sep + "meek-server.exe"
            else:
                print(
                    "MEEK for ArkC has no compiled executable for your OS platform. Please compile and install from source.")
                print(
                    "Get source at https://github.com/projectarkc/meek/tree/master/meek-server")
                quit()
            print(
                "Downloading meek plugin (meek-server) from github to your home directory.")
            meekfile = requests.get(link, stream=True)
            if meekfile.status_code == '200':
                print("Saving to " + localfile)
            else:
                print("Error downloading.")
                quit()
            with open(localfile, 'wb') as f:
                for chunk in meekfile.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            if sys.platform == 'linux2':
                st = os.stat(localfile)
                os.chmod(localfile, st.st_mode | stat.S_IEXEC)
                print("File made executable.")
            print("Download complete.\nYou may change obfs_level and update pt_exec to " +
                  localfile + " to use meek.")
            quit()
        elif options.config is None:
            logging.fatal("Config file (-c or --config) must be specified.\n")
            parser.print_help()
            quit()

        data = {}

        # Load json configuration file
        try:
            data_file = open(options.config)
            data = json.load(data_file)
            data_file.close()
        except Exception as err:
            logging.fatal(
                "Fatal error while loading configuration file.\n" + err)
            quit()

        if "control_domain" not in data:
            logging.fatal("missing control domain")
            quit()

        # Apply default values
        if "local_host" not in data:
            data["local_host"] = DEFAULT_LOCAL_HOST

        if "local_port" not in data:
            data["local_port"] = DEFAULT_LOCAL_PORT

        if "remote_host" not in data:
            data["remote_host"] = DEFAULT_REMOTE_HOST

        if "remote_port" not in data:
            data["remote_port"] = random.randint(20000, 60000)
            logging.info(
                "Using random port " + str(data["remote_port"]) + " as remote listening port")

        if "number" not in data:
            data["number"] = DEFAULT_REQUIRED

        if data["number"] > 100:
            data["number"] = 100

        if "dns_servers" not in data:
            data["dns_servers"] = DEFAULT_DNS_SERVERS

        if "pt_exec" not in data:
            data["pt_exec"] = DEFAULT_OBFS4_EXECADDR

        if "debug_ip" not in data:
            data["debug_ip"] = None

        if "obfs_level" not in data:
            data["obfs_level"] = 0
        elif 1 <= int(data["obfs_level"]) <= 2:
            logging.error(
                "Support for obfs4proxy is experimental with known bugs. Run this mode at your own risk.")

        # Load certificates
        try:
            serverpub_data = open(data["remote_cert"], "r").read()
            serverpub = certloader(serverpub_data).importKey()
        except KeyError as e:
            logging.fatal(
                e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while loading remote host certificate.")
            print (err)
            quit()

        try:
            clientpri_data = open(data["local_cert"], "r").read()
            clientpri_data = clientpri_data.strip(' ').lstrip('\n')
            clientpri = certloader(clientpri_data).importKey()
            clientpri_sha1 = certloader(clientpri_data).getSHA1()
            print("Using private key with SHA1: " + clientpri_sha1 +
                  ". Please make sure it is identical the string in server-side config.")
            if not clientpri.has_private():
                print(
                    "Fatal error, no private key included in local certificate.")
        except KeyError as e:
            logging.fatal(
                e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while loading local certificate.")
            print (err)
            quit()

        try:
            clientpub_data = open(data["local_cert_pub"], "r").read()
            clientpub_data = clientpub_data.strip(' ').lstrip('\n')
            clientpub_sha1 = certloader(clientpub_data).getSHA1()
        except KeyError as e:
            logging.fatal(
                e.tostring() + "is not found in the config file. Quitting.")
            quit()
        except Exception as err:
            print ("Fatal error while calculating SHA1 digest.")
            print (err)
            quit()

        # TODO: make it more elegant
        if options.vv:
            logging.basicConfig(
                stream=sys.stdout, level=logging.DEBUG, format="%(levelname)s: %(asctime)s; %(message)s")
        elif options.v:
            logging.basicConfig(
                stream=sys.stdout, level=logging.INFO, format="%(levelname)s: %(asctime)s; %(message)s")
        else:
            logging.basicConfig(
                stream=sys.stdout, level=logging.WARNING, format="%(levelname)s: %(asctime)s; %(message)s")

        if options.fs:
            swapfq = 3
        else:
            swapfq = 8

    except IOError as e:
        print ("An error occurred: \n")
        print(e)

    # Start the main event loop
    try:
        ctl = Coordinate(
            data["control_domain"],
            clientpri,
            clientpri_sha1,
            serverpub,
            clientpub_sha1,
            data["number"],
            data["remote_host"],
            data["remote_port"],
            data["dns_servers"],
            data["debug_ip"],
            swapfq,
            data["pt_exec"],
            data["obfs_level"],
            options.ipv6,
            options.pn
        )
        sctl = ServerControl(
            data["remote_host"],
            ctl.remote_port,
            ctl,
            pt=bool(data["obfs_level"])
        )
        cctl = ClientControl(
            ctl,
            data["local_host"],
            data["local_port"]
        )

    except KeyError as e:
        print(e)
        logging.fatal("Bad config file. Quitting.")
        quit()

    except Exception as e:
        print ("An error occurred: \n")
        print(e)

    logging.info("Listening to local services at " +
                 data["local_host"] + ":" + str(data["local_port"]))
    logging.info("Listening to remote server at " +
                 data["remote_host"] + ":" + str(ctl.remote_port))

    try:
        asyncore.loop(use_poll=1)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()