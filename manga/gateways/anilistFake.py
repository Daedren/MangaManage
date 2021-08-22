import json
from .anilist import TrackerGatewayInterface

class FakeAnilistGateway(TrackerGatewayInterface):
  def getAllEntries(self):
      with open('stubs/getAllEntries.json') as json_file:
        data = json.load(json_file)
        return data