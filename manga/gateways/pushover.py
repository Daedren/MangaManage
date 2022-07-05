import http.client
import urllib
from cross.decorators import Logger
from cross.debug import debugger_is_active


class PushServiceInterface:
    def sendPush(self, msg: str):
        pass


@Logger
class PushoverGateway(PushServiceInterface):
    def __init__(self, tokenUser: str, tokenApp: str) -> None:
        self.tokenUser = tokenUser
        self.tokenApp = tokenApp

    def sendPush(self, msg: str):
        if debugger_is_active():
            self.logger.debug(f'Push omitted: {msg}')
            return
        conn = http.client.HTTPSConnection("api.pushover.net:443")
        conn.request(
            "POST",
            "/1/messages.json",
            urllib.parse.urlencode(
                {
                    "token": self.tokenApp,
                    "user": self.tokenUser,
                    "message": msg,
                }
            ),
            {"Content-type": "application/x-www-form-urlencoded"},
        )
        response = conn.getresponse()
        self.logger.debug(f'{response.status} {response.reason}')
        self.logger.debug(response.read())


if __name__ == "__main__":
    print(PushoverGateway.sendPush("test message"))
