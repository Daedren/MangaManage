from typing import Mapping
from collections import namedtuple
import json
from models.tracker import TrackerSeries
from .anilist import TrackerGatewayInterface


class FakeAnilistGateway(TrackerGatewayInterface):
    def getAllEntries(self) -> Mapping[int, TrackerSeries]:
        with open("stubs/getAllEntries.json") as json_file:
            data = json.load(json_file, object_hook=self.__jsonDecode)
            to_return = dict()
            for item in data.items():
                to_return[int(item[0])] = item[1]
            return to_return

    def __jsonDecode(self, param_dict):
        # return TrackerSeries(), titles, status, chapters, country_of_origin, progress)
        return namedtuple('X', list(param_dict.keys()))(*param_dict.values())
