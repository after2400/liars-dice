from game.components.exceptions import SecurityViolation
from game.components.script import game_orchestrator
from players.agent_smith import agent_smith
from players.finn import Finn

try:
    players = [agent_smith(), Finn()]
    game_orchestrator(players)
except SecurityViolation as e:
    print(f"Caught expected violation: {e}")
except Exception as e:
    print(f"Caught unexpected exception: {type(e).__name__}: {e}")
