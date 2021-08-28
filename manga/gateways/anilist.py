import http.client
import sys
import json
from functools import reduce


class TrackerGatewayInterface:
    def getProgressFor(self, mediaId):
        pass

    def searchMediaBy(self, title):
        pass

    def getAllEntries(self):
        pass


class AnilistGateway(TrackerGatewayInterface):
    def __init__(self, authToken: str, userId: str) -> None:
        self.token = authToken
        self.userId = userId

    def __prepareRequest(self, query, variables):
        conn = http.client.HTTPSConnection("graphql.anilist.co")
        headers = {"Content-Type": "application/json", "Authorization": self.token}

        body = json.dumps({"query": query, "variables": variables})
        conn.request("POST", "", body, headers)
        res = conn.getresponse()
        data = res.read()
        utfData = data.decode("utf-8")

        result = json.loads(utfData)
        return result

    def getProgressFor(self, mediaId):
        try:
            query = """
          query($mediaId: Int, $userId: Int) {
  MediaList(userId: $userId, mediaId: $mediaId) {
      mediaId,
      progress,
      status
    }
    }
  """
            variables = {"mediaId": mediaId, "userId": self.userId}
            result = self.__prepareRequest(query, variables)
            errors = result.get("errors")
            if errors is not None:
                print("Error in getProgressFor %s" % mediaId)
                print(result["errors"])
                return
            entries = result["data"]["MediaList"]["progress"]
            return entries
        except Exception as e:
            print("Error in getProgressFor %s" % mediaId)
            print(e)

    def searchMediaBy(self, title):
        query = """
      query($searchId: String) {
    Media(search: $searchId) {
      id,
      title {
        romaji
        english
        native
        userPreferred
      }
    }
  }"""
        variables = {"searchId": title}

        result = self.__prepareRequest(query, variables)
        print(result)
        media = result["data"]["Media"]
        titleObj = media["title"]
        titles = [
            titleObj["romaji"],
            titleObj["english"],
            titleObj["native"],
            titleObj["userPreferred"],
        ]
        return (media["id"], titles)

    def getAllEntries(self):
        query = """
      query($userId: Int) {
    MediaListCollection(userId: $userId, type: MANGA) {
      lists {
        entries {
          ...mediaListEntry
        }
      }
    }
  }

  fragment mediaListEntry on MediaList {
    progress
    media {
      id
      synonyms
      countryOfOrigin
      title {
        romaji
        english
      }
      status
      chapters
    }
  }
      """

        variables = {"userId": self.userId}

        result = self.__prepareRequest(query, variables)
        errors = result.get("errors")
        if errors is not None:
            print(result["errors"])
            return
        lists = result["data"]["MediaListCollection"]["lists"]
        mapped = map((lambda x: x["entries"]), lists)
        reduced = reduce((lambda x, y: x + y), mapped)
        return reduced

    if __name__ == "__main__":
        if len(sys.argv) == 2:
            print(getProgressFor(sys.argv[1]))
        else:
            print(getAllEntries())
