from json import dumps
from typing import Union

import tornado.gen
import tornado.web

from common.sentry import sentry
from common.web import requestsManager
from constants import exceptions
from objects import glob


class handler(requestsManager.asyncRequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    @sentry.captureTornado
    def asyncGet(self) -> None:
        statusCode = 400
        data: dict[str, Union[int, str]] = {'message': 'unknown error'}
        try:
            # Check arguments
            if not requestsManager.checkArguments(self.request.arguments, ['u']):
                raise exceptions.invalidArgumentsException()

            # Get userID and its verified cache thing
            # -1: Not in cache
            # 0: Not verified (multiacc)
            # 1: Verified
            userID = self.get_argument('u')
            data['result'] = glob.verifiedCache[userID] if userID in glob.verifiedCache else -1

            # Status code and message
            statusCode = 200
            data['message'] = 'ok'
        except exceptions.invalidArgumentsException:
            statusCode = 400
            data['message'] = 'missing required arguments'
        finally:
            # Add status code to data
            data['status'] = statusCode

            # Send response
            self.add_header('Access-Control-Allow-Origin', '*')
            self.add_header('Content-Type', 'application/json')

            # jquery meme
            output: list[str] = []
            if 'callback' in self.request.arguments:
                output.extend((self.get_argument('callback'), '('))
            output.append(dumps(data))
            if 'callback' in self.request.arguments:
                output.append(')')

            self.write(''.join(output))
            self.set_status(statusCode)
