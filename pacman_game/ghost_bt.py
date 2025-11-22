# ghost_bt.py
# ----------
# Behavior Tree-based Ghost Agents for Pacman.

import random
from typing import Callable, List, Optional, Tuple

from game import Directions, Agent, Actions
from util import manhattanDistance


##################################################
# Behavior Tree building blocks
##################################################

class BTStatus:
    SUCCESS = 1
    FAILURE = 0


class BTNode:
    def tick(self, state, agent) -> Tuple[int, Optional[str]]:
        """
        Returns (status, action)
        status: BTStatus.SUCCESS or BTStatus.FAILURE
        action: a Directions.* action string if decided; otherwise None
        """
        raise NotImplementedError


class Selector(BTNode):
    """Try children in order; return first SUCCESS."""
    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, state, agent):
        for child in self.children:
            status, action = child.tick(state, agent)
            if status == BTStatus.SUCCESS:
                return BTStatus.SUCCESS, action
        return BTStatus.FAILURE, None


class Sequence(BTNode):
    """All children must succeed; returns last action."""
    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, state, agent):
        last_action = None
        for child in self.children:
            status, action = child.tick(state, agent)
            if status == BTStatus.FAILURE:
                return BTStatus.FAILURE, None
            if action is not None:
                last_action = action
        return BTStatus.SUCCESS, last_action


class Condition(BTNode):
    def __init__(self, pred: Callable):
        self.pred = pred

    def tick(self, state, agent):
        return (BTStatus.SUCCESS, None) if self.pred(state, agent) else (BTStatus.FAILURE, None)


class ActionNode(BTNode):
    def __init__(self, fn: Callable):
        self.fn = fn

    def tick(self, state, agent):
        action = self.fn(state, agent)
        if action is None:
            return BTStatus.FAILURE, None
        return BTStatus.SUCCESS, action


class RandomChance(BTNode):
    """Succeeds with probability p; otherwise fails."""
    def __init__(self, p: float):
        self.p = p

    def tick(self, state, agent):
        return (BTStatus.SUCCESS, None) if random.random() < self.p else (BTStatus.FAILURE, None)


##################################################
# Helpers (含索引保護，避免 Invalid index)
##################################################

def normalize_index(state, idx: int) -> int:
    """
    夾住鬼的 index 到有效範圍 1..(#agents-1)。
    有些地圖/迴合切換時，engine 可能先呼叫到未就緒 index；
    夾住可以避免 getGhostState() 丟錯。
    """
    try:
        total_agents = state.getNumAgents()  # 包含 Pacman
    except Exception:
        return max(1, idx)
    max_ghost_index = max(1, total_agents - 1)
    if idx < 1:
        return 1
    if idx > max_ghost_index:
        return max_ghost_index
    return idx


def legal_actions_without_stop(state, index):
    gi = normalize_index(state, index)
    legal = list(state.getLegalActions(gi))
    if Directions.STOP in legal:
        legal.remove(Directions.STOP)
    return legal


def _next_pos(pos, action):
    dx, dy = Actions.directionToVector(action)
    return (pos[0] + dx, pos[1] + dy)


def best_towards(state, ghost_index, target_pos) -> Optional[str]:
    gi = normalize_index(state, ghost_index)
    ghost_state = state.getGhostState(gi)
    ghost_pos = ghost_state.getPosition()
    legal = legal_actions_without_stop(state, gi)
    if not legal:
        return None
    best = None
    best_dist = None
    for a in legal:
        np = _next_pos(ghost_pos, a)
        d = manhattanDistance(np, target_pos)
        if best_dist is None or d < best_dist:
            best_dist = d
            best = a
    return best


def best_away(state, ghost_index, target_pos) -> Optional[str]:
    gi = normalize_index(state, ghost_index)
    ghost_state = state.getGhostState(gi)
    ghost_pos = ghost_state.getPosition()
    legal = legal_actions_without_stop(state, gi)
    if not legal:
        return None
    best = None
    best_dist = None
    for a in legal:
        np = _next_pos(ghost_pos, a)
        d = manhattanDistance(np, target_pos)
        if best_dist is None or d > best_dist:
            best_dist = d
            best = a
    return best


def random_move(state, ghost_index) -> Optional[str]:
    gi = normalize_index(state, ghost_index)
    legal = legal_actions_without_stop(state, gi)
    return random.choice(legal) if legal else None


def is_scared(state, ghost_index) -> bool:
    gi = normalize_index(state, ghost_index)
    return state.getGhostState(gi).scaredTimer > 0


##################################################
# Base class for BT Ghosts
##################################################

class BTGhostBase(Agent):
    """
    A Ghost controlled by a Behavior Tree.
    Subclasses specify a 'mode' and we build a tree accordingly.
    """
    def __init__(self, index, prob_attack=0.8, prob_scared=0.8, mode="random"):
        self.index = index
        self.prob_attack = float(prob_attack)
        self.prob_scared = float(prob_scared)
        self.mode = mode
        self.tree = self._build_tree(mode)

    def getAction(self, state):
        status, action = self.tree.tick(state, self)
        if action is None:
            action = random_move(state, self.index) or Directions.STOP
        return action

    def _build_tree(self, mode: str) -> BTNode:
        flee_leaf = ActionNode(lambda s, a: best_away(s, a.index, s.getPacmanPosition()))
        chase_leaf = ActionNode(lambda s, a: best_towards(s, a.index, s.getPacmanPosition()))
        random_leaf = ActionNode(lambda s, a: random_move(s, a.index))
        scared_cond = Condition(lambda s, a: is_scared(s, a.index))
        not_scared = Condition(lambda s, a: not is_scared(s, a.index))

        if mode == "random":
            return Selector([random_leaf])

        if mode == "directional":
            #####################################
            # WRITE YOUR CODE HERE
            #####################################

        if mode == "chasing":
            #####################################
            # WRITE YOUR CODE HERE
            #####################################

        if mode == "imperfect":
            #####################################
            # WRITE YOUR CODE HERE
            #####################################

        return Selector([random_leaf])


##################################################
# Specific BT Ghosts (names kept for compatibility)
##################################################

class BTRandomGhost(BTGhostBase):
    def __init__(self, index):
        super().__init__(index=index, mode="random")


class BTDirectionalGhost(BTGhostBase):
    def __init__(self, index, prob_attack=0.8, prob_scaredFlee=0.8):
        super().__init__(index=index, prob_attack=prob_attack,
                         prob_scared=prob_scaredFlee, mode="directional")


class BTChasingGhost(BTGhostBase):
    def __init__(self, index, prob_attack=0.9, prob_scaredFlee=0.7):
        super().__init__(index=index, prob_attack=prob_attack,
                         prob_scared=prob_scaredFlee, mode="chasing")


class BTImperfectGhost(BTGhostBase):
    def __init__(self, index, prob_attack=0.99, prob_scaredFlee=0.99):
        super().__init__(index=index,
                         prob_attack=prob_attack,
                         prob_scared=prob_scaredFlee,
                         mode="imperfect")
