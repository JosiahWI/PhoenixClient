import asyncio
import certifi
import json
import ssl
import websockets

async def default_logger(message):
    print(f'INFO: {message}')

class Client:
    """
    A websockets client that can be used for testing a server.
    
    uri: The uri to connect to.
    """

    __slots__ = ('uri', 'conn', 'active_requests', 'request_queue', 'log')
    def __init__(self, uri, logger=default_logger):
        """
        Initialize a Client instance.
        """
        self.uri = uri
        self.conn = None
        self.active_requests = {}
        self.request_queue = []
        self.log = logger

    async def __connect(self):
        """
        Connect to the server.
        """
        await self.log(f'Connecting to {self.uri}.')
        ssl_context = None
        # Check whether ssl should be enabled.
        if self.uri[:3] == 'wss':
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        self.conn = await websockets.connect(self.uri, ssl=ssl_context)
        await self.log('Connected.')

    async def __send_requests(self):
        """
        Checks the queue for waiting requests and sends one of each
        type that is not already in progress.
        """
        # Unfortunately is blocking, may consider improving this.
        await self.log('Starting request queue manager.')
        while True:
            for request in self.request_queue:
                expected_response = request['expected']
                if request.get('static_listener'):
                    await self.log(f'Adding listener {expected_response}.')
                    self.active_requests[expected_response] = request
                    self.request_queue.remove(request)
                    continue
                #if not self.active_requests.get(request['expected']):
                if not self.active_requests.get(expected_response):
                    if expected_response:
                        self.active_requests[expected_response] = request
                    data = request['data']
                    await self.log(f'Sending protocol, {data}.')
                    await self.conn.send( json.dumps(data) )
                    # Remove from the queue.
                    self.request_queue.remove(request)
            await asyncio.sleep(0.1)

    async def __start_listener(self):
        """
        Listens for incoming messages and passes them to the callback
        in the matching request.
        """
        await self.log('Starting message listener.')
        async for msg in self.conn:
            data = json.loads(msg)
            # Match the response with the its request, or get
            # the default handler if it exists.
            matched_request = self.active_requests.get(
                data['type'],
                self.active_requests.get('default'))
            if not matched_request:
                raise UnrecognizedProtocolError(data)
            handler = matched_request['handler_callback']
            # Remove the request from the active ones unless it is
            # a static listener.
            if not matched_request.get('static_listener'):
                del self.active_requests[data['type']]
            await handler(data)

    async def add_static_listener(self, protocol_name, callback):
        request = {
                'expected' : protocol_name,
                'handler_callback' : callback,
                'static_listener' : True,
            }
        await self.queue_request(request)

    async def queue_request(self, request):
        await self.log(f'Queued new request: {request}.')
        self.request_queue.append(request)

    async def run(self):
        await self.__connect()
        asyncio.ensure_future(self.__send_requests())
        asyncio.ensure_future(self.__start_listener())

    async def close(self):
        await self.log('INFO: letting connection drop.')
        await self.conn.close()

class UnrecognizedProtocolError(Exception):

    def __init__(self, data):
        self.data = data
        self.message = 'The following response was not expected or is '\
                       f'not a recognized protocol: {data}.'

    def __str__(self):
        return self.message
