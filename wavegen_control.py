# -*- coding: utf-8 -*-
"""
Wave generator control

"""

#client

import sys

if sys.version_info[0] < 3:
    raise RuntimeError('This script should be run under Python 3')

import numpy
import socket
import time

from find_ip_addr import find_ip_addr


class wavegen_control:
    MSIPA_CACHE_FN = 'wavegen_server_ip_address_cache.tmp'

    WAVEGEN_SERVER_PORT = 50000
    BUF_SIZE = 1024
    # each instance should have its own, so no definition here: server_ip_addr = None

    # - - - - - - - - - - - - - - - - -

    def __init__(self, server_ip_addr = None, msipa_cache_fn = None, verbose = True):
        self.verbose = verbose
        if msipa_cache_fn == None:
            self.msipa_cache_fn = self.MSIPA_CACHE_FN
        else:
            self.msipa_cache_fn = msipa_cache_fn

        # if we get an ip address argument, set that as the suggest server IP address, otherwise look in cache file
        if server_ip_addr != None:
            self.server_ip_addr = server_ip_addr
        else:
            try:
                # later: save the successfully determined wavegen server IP address in a file on disk
                # now: read the previously saved file as a first guess for the wavegen server IP address:
                self.server_ip_addr = None
                with open(self.msipa_cache_fn, 'r') as f:
                    self.server_ip_addr = f.readline()
            except FileNotFoundError:
                self.server_ip_adddr = None

        # - - - - - - - - - - - - - - - - - - - - - - -
        need_search = True

        if self.server_ip_addr != None  and  len(self.server_ip_addr) > 0:
            try:
                print('looking for wavegen server at', self.server_ip_addr,end=' ',flush=True)
                t = self.send_text('TEST', 2)
                if t[3:] == 'test completed ok':
                    print('...found')
                    need_search = False
                else:
                    print('wavegen server returned "', t, '" ', sep='')
                    print('todo: why not the correct response?')
                    need_search = True
            except TimeoutError:
                need_search = True
                print('...timed out')

        if need_search:
            self.server_ip_addrs = find_ip_addr('Raspberry Pi')

            if len(self.server_ip_addrs) > 1:
                raise RuntimeError("Too many possible servers: "+str(self.server_ip_addrs))
                # todo: ask which one to use
            if len(self.server_ip_addrs) < 1:
                raise RuntimeError("No server found: "+str(self.server_ip_addrs))
                # todo: ask for an IP addr
            self.server_ip_addr = self.server_ip_addrs[0]

        with open(self.msipa_cache_fn, 'w') as f:
            f.write(self.server_ip_addr)

    def __repr__(self):
        """ return a printable version: not a useful function """
        return self.server_ip_addr + '; ' + self.msipa_cache_fn + '; ' + self.verbose


    def __str__(self):
        """ return a string representation: """
        return self.__repr__()

    def __bool__(self):
        """ boolean test if valid - assumes valid if the server IP address is defined """
        return self.server_ip_addr != None

    def __enter__(self):
        """ no special processing after __init__() """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ no special processing after __init__() """

    def __del__(self):
        """ no special processing after __init__() """
    # - - - - - - - - - - - - - - - - -


    def send_text(self, text, timeout:int=None) -> str:
        """worker for below - opens a connection to send commands to the wavegen control server, closes when done"""
        """ note: timeout is not working - needs some MS specific iocontrol stuff (I think) """
        RETRIES = 30
        retry_count = 0
        while retry_count < RETRIES:  # Retries added 17-07-11
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                ##if timeout != None:
                ##	#not on windows: socket.settimeout(timeout)
                ##	s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack('LL', timeout, 0))
                s.connect((self.server_ip_addr, self.WAVEGEN_SERVER_PORT))
                break
            except ConnectionRefusedError:
                retry_count += 1
                print('...connection refused, at',time.ctime(),' Is wavegen_server process running on remote machine?',
                           '  Retry', retry_count, '/', RETRIES, "on", str(self.server_ip_addr))
            except TimeoutError:
                retry_count += 1
                print('...connection attempt timed out, at',time.ctime(),
                           '  Retry', retry_count, '/', RETRIES, "on", str(self.server_ip_addr))

        if retry_count >= RETRIES:
            input(" pausing in wavegen_control.py send_text() function, hit Enter to try again, or ^C: ")
            s.close()
            return self.send_text(text, timeout)  # tail-recurse if retry is requested

        buf = bytes(text, encoding='utf-8')
        s.send(buf)
        data = s.recv(self.BUF_SIZE)
        s.close()
        return_text = data.decode('utf-8')
        if self.verbose:
            print(' | response is', return_text)
            #print(' ',type(data), len(data), ' ', end='')
        return return_text


    def set_DC(self, voltage):
        """ Called to send command to motor control server to set a position
            The argument is a tuple from the positions array: pos[0] = index, pos[1] = x, pos[2] = y
        """
        try:
            if self.verbose:
                print('DC = ', voltage, sep='', end='', flush=True)
            self.send_text(voltage)  # cm

        except ConnectionResetError as err:
            print('*** connection to server failed: "'+err.strerror+'"')
            return False
        except ConnectionRefusedError as err:
            print('*** could not connect to server: "'+err.strerror+'"')
            return False
        except KeyboardInterrupt:
            print('\n______Halted due to Ctrl-C______')
            return False

        # todo: see http://code.activestate.com/recipes/408859/  recv_end() code
        #       We need to include a terminating character for reliability, e.g.: text += '\n'
        return True
