import http.client
import urllib


class PushServiceInterface:
    def sendPush(self, msg: str):
        pass


class PushoverGateway(PushServiceInterface):
    def __init__(self, tokenUser: str, tokenApp: str) -> None:
        self.tokenUser = tokenUser
        self.tokenApp = tokenApp

    def sendPush(self, msg: str):
        conn = http.client.HTTPSConnection("api.pushover.net:443")
        conn.request(
            "POST",
            "/1/messages.json",
            urllib.parse.urlencode(
                {
                    "token": self.tokenUser,
                    "user": self.tokenUser,
                    "message": msg,
                }
            ),
            {"Content-type": "application/x-www-form-urlencoded"},
        )
        conn.getresponse()


if __name__ == "__main__":
    print(PushoverGateway.sendPush("test message"))
