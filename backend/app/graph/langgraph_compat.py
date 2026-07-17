"""LangGraph 兼容层 — 纯 Python 实现 StateGraph，无需安装 langgraph"""
from __future__ import annotations
from typing import Any, Callable, Optional

NodeFunc = Callable[[dict], dict]
CondFunc = Callable[[dict], str]


class _Node:
    def __init__(self, name: str, func: NodeFunc):
        self.name = name
        self.func = func
    def run(self, state: dict) -> dict:
        return self.func(state)


class _Edge:
    def __init__(self, source: str, target: str):
        self.source = source
        self.target = target


class _ConditionalEdge:
    def __init__(self, source: str, router: CondFunc, targets: dict[str, str]):
        self.source = source
        self.router = router
        self.targets = targets


class StateGraph:
    def __init__(self, state_schema: type):
        self._state_schema = state_schema
        self._nodes: dict[str, _Node] = {}
        self._edges: list[_Edge] = []
        self._conditional_edges: list[_ConditionalEdge] = []
        self._entry_point: Optional[str] = None

    def add_node(self, name: str, func: NodeFunc):
        self._nodes[name] = _Node(name, func)

    def add_edge(self, source: str, target: str):
        self._edges.append(_Edge(source, target))

    def add_conditional_edges(self, source: str, router: CondFunc, targets: dict[str, str]):
        self._conditional_edges.append(_ConditionalEdge(source, router, targets))

    def set_entry_point(self, name: str):
        self._entry_point = name

    def compile(self) -> CompiledGraph:
        return CompiledGraph(self)


class END:
    """图结束哨兵"""
    pass


class CompiledGraph:
    def __init__(self, graph: StateGraph):
        self._graph = graph

    def invoke(self, state: dict) -> dict:
        g = self._graph
        current = g._entry_point
        if current is None:
            raise ValueError("未设置入口节点")

        while current is not None and current != "END":
            node = g._nodes.get(current)
            if node is None:
                raise ValueError(f"节点不存在: {current}")

            state.update(node.run(state))

            next_node = None
            # 优先检查条件边
            for ce in g._conditional_edges:
                if ce.source == current:
                    target_key = ce.router(state)
                    next_node = ce.targets.get(target_key)
                    break
            # 再检查普通边
            if next_node is None:
                for e in g._edges:
                    if e.source == current:
                        next_node = e.target
                        break

            current = next_node

        return state
