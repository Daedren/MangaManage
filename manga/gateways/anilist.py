import http.client
import json
from functools import reduce
from typing import List, Mapping
from models.tracker import TrackerSeries


class TrackerGatewayInterface:
    def getProgressFor(self, mediaId):
        pass

    def searchMediaBy(self, title):
        pass

    def getAllEntries(self) -> Mapping[int, TrackerSeries]:
        pass


class AnilistGateway(TrackerGatewayInterface):
    def __init__(self, authToken: str, userId: str) -> None:
        self.token = authToken
        self.userId = userId
        self.cache = {}

    def __prepareRequest(self, query, variables):
        query_key = (query, str(variables))
        cache_value = self.cache.get(query_key)
        if cache_value is not None:
            return cache_value

        conn = http.client.HTTPSConnection("graphql.anilist.co")
        headers = {"Content-Type": "application/json", "Authorization": self.token}

        body = json.dumps({"query": query, "variables": variables})
        conn.request("POST", "", body, headers)
        res = conn.getresponse()
        data = res.read()
        utfData = data.decode("utf-8")

        result = json.loads(utfData)

        if res.status == 200:
            self.cache[query_key] = result

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

    def searchMediaBy(self, title) -> Mapping[int, TrackerSeries]:
        query = """
      query($searchId: String) {
    Media(search: $searchId, format: MANGA) {
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
  }"""
        variables = {"searchId": title}

        result = self.__prepareRequest(query, variables)
        errors = result.get("errors")
        if errors is not None:
            print(result["errors"])
            return

        models: List[TrackerSeries] = []
        series = result["data"]["Media"]
        main_titles = [
            series["title"]["english"],
            series["title"]["romaji"],
        ]
        all_titles = main_titles + series["synonyms"]
        non_empty_all_titles = list(filter(None, all_titles))

        models.append(
            TrackerSeries(
                series["id"],
                non_empty_all_titles,
                series["status"],
                series["chapters"],
                series["countryOfOrigin"],
                0,
            )
        )

        # Create anilist ID keyed dictionary
        model_dictionary = dict((v.tracker_id, v) for v in models)
        return model_dictionary

    def getAllEntries(self) -> Mapping[int, TrackerSeries]:
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

        # Merge all of the user's manga lists
        lists = result["data"]["MediaListCollection"]["lists"]
        mapped = map((lambda x: x["entries"]), lists)
        reduced = reduce((lambda x, y: x + y), mapped)

        models: List[TrackerSeries] = []
        for series in reduced:
            main_titles = [
                series["media"]["title"]["english"],
                series["media"]["title"]["romaji"],
            ]
            all_titles = main_titles + series["media"]["synonyms"]
            non_empty_all_titles = list(filter(None, all_titles))

            models.append(
                TrackerSeries(
                    series["media"]["id"],
                    non_empty_all_titles,
                    series["media"]["status"],
                    series["media"]["chapters"],
                    series["media"]["countryOfOrigin"],
                    series["progress"],
                )
            )

        # Create anilist ID keyed dictionary
        model_dictionary = dict((v.tracker_id, v) for v in models)
        return model_dictionary

    def addPlanToRead(self, mediaId):
        query = """
        mutation($mediaId: Int, $status: MediaListStatus) {
          SaveMediaListEntry (mediaId: $mediaId, status: $status) {
            id
            status
          }
        }
        """

        variables = {
          "mediaId": mediaId,
          "status": "PLANNING"
        }

        result = self.__prepareRequest(query, variables)
        errors = result.get("errors")
        if errors is not None:
            print(result["errors"])
            return
        self.cache = {}
        