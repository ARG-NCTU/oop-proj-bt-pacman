
# ghost_bt.py
# Behavior-Tree versions of Pacman ghosts using py_trees
# Mirrors the logic of RandomGhost, DirectionalGhost, ChasingGhost, ImperfectGhost.

from game import Agent, Actions, Directions
import util
from distanceCalculator import computeDistances, getDistanceOnGrid
import py_trees as pt
from py_trees.common import Status


# ---------- 工具：命名空間化黑板鍵 ----------
def ns_key(gi, name):
    return f"g{gi}_{name}"


# ---------- 通用行為節點 ----------
class WriteState(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        state = self.bb.get(ns_key(self.index, "state"))
        if state is None:
            return Status.FAILURE
        # 讀基本資料
        ghost_state = state.getGhostState(self.index)
        legal = state.getLegalActions(self.index)
        self.bb.set(ns_key(self.index, "ghost_state"), ghost_state)
        self.bb.set(ns_key(self.index, "ghost_pos"), state.getGhostPosition(self.index))
        self.bb.set(ns_key(self.index, "is_scared"), ghost_state.scaredTimer > 0)
        self.bb.set(ns_key(self.index, "legal_actions"), legal)
        self.bb.set(ns_key(self.index, "pacman_pos"), state.getPacmanPosition())
        # 距離快取（layout 不變，快取可重用）
        if self.bb.get(ns_key(self.index, "dist_cache")) is None:
            self.bb.set(ns_key(self.index, "dist_cache"), computeDistances(state.data.layout))
        return Status.SUCCESS


class CheckAnyLegal(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        legal = self.bb.get(ns_key(self.index, "legal_actions")) or []
        return Status.SUCCESS if len(legal) > 0 else Status.FAILURE


class SetSpeed(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        is_scared = self.bb.get(ns_key(self.index, "is_scared"))
        self.bb.set(ns_key(self.index, "speed"), 0.5 if is_scared else 1.0)
        return Status.SUCCESS


class BuildActionVectors(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        speed = self.bb.get(ns_key(self.index, "speed")) or 1.0
        legal = self.bb.get(ns_key(self.index, "legal_actions")) or []
        vecs = [Actions.directionToVector(a, speed) for a in legal]
        self.bb.set(ns_key(self.index, "action_vectors"), vecs)
        return Status.SUCCESS


class ComputeNewPositions(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        pos = self.bb.get(ns_key(self.index, "ghost_pos"))
        vecs = self.bb.get(ns_key(self.index, "action_vectors")) or []
        new_positions = [(pos[0] + v[0], pos[1] + v[1]) for v in vecs]
        self.bb.set(ns_key(self.index, "new_positions"), new_positions)
        return Status.SUCCESS


class ComputeDistancesToPacman(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        pac = self.bb.get(ns_key(self.index, "pacman_pos"))
        new_positions = self.bb.get(ns_key(self.index, "new_positions")) or []
        dist_cache = self.bb.get(ns_key(self.index, "dist_cache"))
        dists = [getDistanceOnGrid(dist_cache, p, pac) for p in new_positions]
        self.bb.set(ns_key(self.index, "dists_to_pac"), dists)
        return Status.SUCCESS


class SelectBestActions(pt.behaviour.Behaviour):
    """
    mode='nearest' -> 追擊: 選取距離最小
    mode='farthest' -> 逃跑: 選取距離最大
    """
    def __init__(self, name, index, mode='nearest'):
        super().__init__(name)
        self.index = index
        self.mode = mode
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        legal = self.bb.get(ns_key(self.index, "legal_actions")) or []
        dists = self.bb.get(ns_key(self.index, "dists_to_pac")) or []
        if not legal or not dists:
            return Status.FAILURE
        target = min(dists) if self.mode == 'nearest' else max(dists)
        best_actions = [a for a, d in zip(legal, dists) if d == target]
        self.bb.set(ns_key(self.index, "best_actions"), best_actions)
        return Status.SUCCESS


class SetBestProb(pt.behaviour.Behaviour):
    def __init__(self, name, index, prob_attack, prob_scared):
        super().__init__(name)
        self.index = index
        self.prob_attack = prob_attack
        self.prob_scared = prob_scared
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        is_scared = self.bb.get(ns_key(self.index, "is_scared"))
        self.bb.set(ns_key(self.index, "best_prob"), self.prob_scared if is_scared else self.prob_attack)
        return Status.SUCCESS


class BuildDistribution(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        legal = self.bb.get(ns_key(self.index, "legal_actions")) or []
        best = self.bb.get(ns_key(self.index, "best_actions")) or []
        best_prob = self.bb.get(ns_key(self.index, "best_prob"))
        if not legal:
            self.bb.set(ns_key(self.index, "distribution"), util.Counter())
            return Status.SUCCESS
        # 建表
        dist = util.Counter()
        if best and best_prob is not None:
            for a in best:
                dist[a] = best_prob / len(best)
        # 其餘機率均分到所有合法動作
        remain = 1.0 - (sum(dist.values()))
        for a in legal:
            dist[a] += remain / len(legal)
        dist.normalize()
        self.bb.set(ns_key(self.index, "distribution"), dist)
        return Status.SUCCESS


class BuildUniformDistribution(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        legal = self.bb.get(ns_key(self.index, "legal_actions")) or []
        dist = util.Counter()
        for a in legal:
            dist[a] = 1.0
        dist.normalize()
        self.bb.set(ns_key(self.index, "distribution"), dist)
        return Status.SUCCESS


class ReturnEmptyDistribution(pt.behaviour.Behaviour):
    def __init__(self, name, index):
        super().__init__(name)
        self.index = index
        self.bb = pt.blackboard.Blackboard()

    def update(self):
        self.bb.set(ns_key(self.index, "distribution"), util.Counter())
        return Status.SUCCESS


# ---------- 基底 BT 鬼 ----------
class BTGhostBase(Agent):
    def __init__(self, index, prob_attack=0.8, prob_scared=0.8, mode="directional"):
        super().__init__()
        self.index = index
        self.prob_attack = prob_attack
        self.prob_scared = prob_scared
        self.mode = mode  # "directional" / "chasing" / "imperfect" / "random"
        self.tree = self._build_tree()

    def _build_tree(self):
        gi = self.index
        # 感知序列
        seq_perception = pt.composites.Sequence("perception")
        seq_perception.add_children([
            WriteState("read_state", gi),
            CheckAnyLegal("any_legal", gi),
            SetSpeed("set_speed", gi),
            BuildActionVectors("build_vectors", gi),
            ComputeNewPositions("new_positions", gi),
            ComputeDistancesToPacman("dists_to_pac", gi),
        ])

        # 追或逃 Selector
        sel_mode = pt.composites.Selector("mode_selector")

        # flee branch
        seq_flee = pt.composites.Sequence("flee_seq")
        seq_flee.add_children([
            SelectBestActions("choose_farthest", gi, mode="farthest"),
            SetBestProb("best_prob_flee", gi, self.prob_attack, self.prob_scared),  # 實際上 SetBestProb 會依 is_scared 自行選用
        ])

        # chase branch
        seq_chase = pt.composites.Sequence("chase_seq")
        seq_chase.add_children([
            SelectBestActions("choose_nearest", gi, mode="nearest"),
            SetBestProb("best_prob_chase", gi, self.prob_attack, self.prob_scared),
        ])

        sel_mode.add_children([seq_flee, seq_chase])

        # 建表
        seq_build = pt.composites.Sequence("build_and_output")
        seq_build.add_children([BuildDistribution("build_dist", gi)])

        # 若沒有合法動作，fallback 到空表
        full = pt.composites.Sequence("full_pipeline")
        full.add_children([seq_perception, sel_mode, seq_build])

        fallback = pt.composites.Selector("root_fallback")
        fallback.add_children([full, ReturnEmptyDistribution("return_empty", gi)])

        return pt.trees.BehaviourTree(fallback)

    def getDistribution(self, state):
        # 餵入 state 到黑板
        bb = pt.blackboard.Blackboard()
        bb.set(ns_key(self.index, "state"), state)
        # tick
        self.tree.tick()
        # 取出 distribution
        dist = bb.get(ns_key(self.index, "distribution"))
        return dist if dist is not None else util.Counter()

    # pacman 框架會呼叫 getAction -> chooseFromDistribution
    def getAction(self, state):
        dist = self.getDistribution(state)
        if len(dist) == 0:
            return Directions.STOP
        else:
            return util.chooseFromDistribution(dist)


# ---------- 四種鬼 ----------
class BTRandomGhost(BTGhostBase):
    def __init__(self, index):
        super().__init__(index=index, mode="random")

    def _build_tree(self):
        gi = self.index
        seq_perception = pt.composites.Sequence("perception_random")
        seq_perception.add_children([
            WriteState("read_state", gi),
            CheckAnyLegal("any_legal", gi),
        ])

        seq_build = pt.composites.Sequence("build_and_output")
        seq_build.add_children([BuildUniformDistribution("uniform_dist", gi)])

        full = pt.composites.Sequence("full_random")
        full.add_children([seq_perception, seq_build])

        fallback = pt.composites.Selector("root_fallback")
        fallback.add_children([full, ReturnEmptyDistribution("return_empty", gi)])
        return pt.trees.BehaviourTree(fallback)


class BTDirectionalGhost(BTGhostBase):
    def __init__(self, index, prob_attack=0.8, prob_scaredFlee=0.8):
        super().__init__(index=index, prob_attack=prob_attack, prob_scared=prob_scaredFlee, mode="directional")


class BTChasingGhost(BTGhostBase):
    def __init__(self, index, prob_attack=0.9, prob_scaredFlee=0.7):
        # 可稍微偏向追擊
        super().__init__(index=index, prob_attack=prob_attack, prob_scared=prob_scaredFlee, mode="chasing")


class BTImperfectGhost(BTGhostBase):
    def __init__(self, index, prob_attack=0.99, prob_scaredFlee=0.99):
        # 幾乎總是選最佳動作
        super().__init__(index=index, prob_attack=prob_attack, prob_scared=prob_scaredFlee, mode="imperfect")
