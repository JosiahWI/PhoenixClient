#!/usr/bin/python3

import asyncio
from subprocess import Popen
import sys

from client import Client
import shell_chat_conf as conf

class ShellLogger:

    def __init__(self, filename, shell=False):
        self.logfile = open(filename, 'w+')
        if shell:
            self.shell = Popen(
                f'{conf.console} --command="tail -f {filename}"', shell=True)

    async def send(self, message):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.logfile.write, message + '\n')
        await loop.run_in_executor(None, self.logfile.flush)

    async def close(self):
        self.logfile.close()

class ShellChat:

    __slots__ = ('uri', 'debug', 'client', 'logged_in', 'logshell', 'msgshell',
                 'cmds')
    def __init__(self):
        self.uri = conf.phoenix_uri
        self.debug = True
        self.client = Client(self.uri, logger=self.log)
        self.logged_in = False
        self.logshell = ShellLogger('log.txt')
        self.msgshell = ShellLogger('msg.txt', shell=True)
        self.cmds = {
                '/exit' : self.close,
                '/login' : self.login,
                '/register' : self.register,
            }

    async def log(self, message):
        if self.debug:
            await self.logshell.send(f'INFO: {message}')

    async def __c_login(self, data):
        if not data['result']:
            raise FailedLogin(data)
        self.logged_in = True
        sys.stdout.write(f"Logged in as {data['username']}.\n>>")

    async def __c_message(self, data):
        await self.msgshell.send(f"<{data['name']}> {data['message']}")

    async def __c_register(self, data):
        self.logged_in = True
        sys.stdout.write("Registered and logged in.\n>>")

    async def __c_terminate(self, data):
        await self.close()

    async def __c_warning(self, data):
        await self.logshell.send(f"WARNING: {data['msg']}")

    async def messenger(self):
        while True:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(None, input, ">>")
            if message[0] == '/':
                args = message.split(' ')
                cmd = self.cmds[args[0]]
                await cmd(args)
                continue
            if not self.logged_in:
                print("Not logged in. Please use /login <email> <password> to "\
                      "login, or /register <name> <email> <password> to "\
                      "register, if you don't have an account yet.")
                continue
            message_data = {
                    'type' : 'MESSAGE',
                    'channel' : ' 1\u200b1',
                    'message' : message,
                }
            request = {
                    'data' : message_data,
                    'expected' : '',
                }
            await self.client.queue_request(request)
            await asyncio.sleep(0.1)

    async def register(self, args):
        if len(args) != 4:
            sys.stdout.write(">>Wrong number of arguments to /register.\n")
            return
        register_data = {
                'type' : 'REGISTER',
                'username' : args[1],
                'email' : args[2],
                'password' : args[3],
            }
        request = {
                'data' : register_data,
                'expected' : 'login',
                'handler_callback' : self.__c_register,
            }
        await self.client.queue_request(request)

    async def login(self, args):
        if len(args) != 3:
            sys.stdout.write(">>Wrong number of arguments to /login.\n")
            return
        login_data = {
                'type' : 'LOGIN',
                'email' : args[1],
                'password' : args[2],
            }
        request = {
                'data' : login_data,
                'expected' : 'login',
                'handler_callback' : self.__c_login,
            }
        await self.client.queue_request(request)

    async def run(self):
        print("Welcome to ShellClient. Commands are /exit to logout "\
              "/register <username> <email> <password> to register "\
              "and /login <email> <password> to login. Have fun!")
        await self.client.add_static_listener('message', self.__c_message)
        await self.msgshell.send("Message Logger:")
        await self.client.add_static_listener('terminate', self.__c_terminate)
        await self.client.add_static_listener('warning', self.__c_warning)
        await self.client.run()
        await self.messenger()

    async def close(self, args):
        sys.stdout.write("Logging out.\n")
        await self.client.close()
        await self.logshell.close()
        await self.msgshell.close()
        sys.exit()

class FailedLogin(Exception):
    pass

if __name__ == '__main__':
    shellchat = ShellChat()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(shellchat.run())
    loop.run_forever()
