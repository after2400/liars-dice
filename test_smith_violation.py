import logging

from game.components.script import game_orchestrator
from players.agent_smith import agent_smith
from players.finn import Finn

logging.basicConfig(level=logging.INFO)
try:
    players = [agent_smith(), Finn()]
    game_orchestrator(players)
except Exception as e:
    print(f"Caught exception: {type(e).__name__}: {e}")
