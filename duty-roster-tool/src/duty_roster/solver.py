"""待機当番の割り当て。

やっていること:

1. 日曜は「対象5名から1人1回ずつ」なので、まず日曜だけを総当たりで組む。
2. 残りの日は、回数配分(quota)をぴったり満たす形で貪欲に組み、
   入れ替え（2日分のスワップ）による局所探索でコストを下げる。
3. 日曜の組み合わせ候補ごとに 1〜2 を試し、最も良い解を採用する。

回数配分は「組み方の制約」として常に厳密に守られる（スワップは回数を変えない）。
優先順位・連日回避・土日祝の偏りはコストとして扱い、低い順に最適化する。
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field

from .config import Config
from .rules import SAT, SUN, RuleEngine


# 2000-01-02 は日曜。日曜始まりの週番号を出すための基準日。
WEEK_ANCHOR = dt.date(2000, 1, 2)


def week_index(day: dt.date) -> int:
    return (day - WEEK_ANCHOR).days // 7


@dataclass
class Solution:
    assignment: dict[dt.date, str]
    cost: float
    counts: dict[str, int]
    violations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Solver:
    def __init__(self, cfg: Config, engine: RuleEngine, fixed: dict[dt.date, str] | None = None):
        self.cfg = cfg
        self.engine = engine
        self.days = engine.days
        self.members = engine.members
        self.fixed = dict(fixed or {})
        self.open_days = [d for d in self.days if d not in self.fixed]
        self.quota = cfg.quota(engine.days_in_month)
        self.quota_notes: list[str] = []
        self.remaining_quota = self._remaining_quota()

        w = cfg.weights
        self.tier_weights = [float(x) for x in w["tier"]]
        self.w_fallback = float(w["fallback_tier"])
        self.w_consec = float(w["consecutive"])
        self.w_inelig = float(w["ineligible"])
        self.w_group_run = float(w["group_run"])
        self.w_fair = float(w["holiday_fairness"])
        # 日曜は「1人1回ずつ」の総当たりで優先順位を満たす組み合わせを探すルールなので、
        # 優先順位のコストを重くして、平日側の都合で崩されないようにする。
        self.sunday_tier_multiplier = float(w.get("sunday_tier_multiplier", 20))

        self.w_holiday_not_working = float(w.get("holiday_not_working", 0))
        self.w_short_gap = float(w.get("short_gap", 0))
        self.w_week_overload = float(w.get("week_overload", 0))

        self.group = set(cfg.consecutive_group)
        self.max_run = cfg.consecutive_group_max_run
        self.max_per_week = cfg.max_per_week
        self.min_gap_days = cfg.min_gap_days

        # (人, 日) ごとの可否・優先順位コストを先に展開しておく
        self.ok: dict[tuple[str, dt.date], bool] = {}
        self.tier_cost: dict[tuple[str, dt.date], float] = {}
        for day in self.days:
            # 祝日は、その日に出勤している人がいればその人を優先する
            holiday_workers = set(engine.holiday_workers(day))
            for name in self.members:
                elig = engine.eligibility(name, day)
                self.ok[(name, day)] = elig.ok
                tier = engine.tier(name, day)
                base = (
                    self.tier_weights[tier]
                    if tier is not None and tier < len(self.tier_weights)
                    else self.w_fallback
                )
                if day.weekday() == SUN:
                    base *= self.sunday_tier_multiplier
                if holiday_workers and name not in holiday_workers:
                    base += self.w_holiday_not_working
                # 条件付きで可の候補は追加コストを載せ、最後の手段にする
                self.tier_cost[(name, day)] = base + elig.penalty
        self.red_days = {d for d in self.days if engine.is_red_day(d) or d.weekday() == SAT}

    def _remaining_quota(self) -> dict[str, int]:
        """先に決めたぶんを引いた残りの回数。合計が残り日数と合うように調整する。"""
        remaining = dict(self.quota)
        for name in self.fixed.values():
            remaining[name] = remaining.get(name, 0) - 1
        for name, value in remaining.items():
            if value < 0:
                self.quota_notes.append(
                    f"{name}: 指定された日数が目標 {self.quota.get(name, 0)} 回を超えています"
                )
                remaining[name] = 0

        target = len(self.open_days)
        # 多すぎる場合は目標に対して余裕のある人から減らす
        while sum(remaining.values()) > target:
            name = max(remaining, key=lambda n: (remaining[n], n))
            remaining[name] -= 1
        # 少なすぎる場合は目標に対して少ない人から増やす
        while sum(remaining.values()) < target:
            name = min(
                remaining,
                key=lambda n: (remaining[n] + sum(1 for v in self.fixed.values() if v == n)
                               - self.quota.get(n, 0), n),
            )
            remaining[name] += 1
        return remaining

    # -- 評価 --------------------------------------------------------------
    def evaluate(self, assignment: dict[dt.date, str]) -> float:
        cost = 0.0
        for day, name in assignment.items():
            if day in self.fixed:
                continue  # 指定された日は評価しない（ルールに関係なく入れる）
            if not self.ok[(name, day)]:
                cost += self.w_inelig
            cost += self.tier_cost[(name, day)]

        # 同じ人の待機が近接しないように散らす
        days_of: dict[str, list[dt.date]] = {}
        for day, name in assignment.items():
            days_of.setdefault(name, []).append(day)
        for mine in days_of.values():
            mine.sort()
            for earlier, later in zip(mine, mine[1:]):
                gap = (later - earlier).days
                if gap == 1:
                    cost += self.w_consec
                elif gap < self.min_gap_days:
                    cost += self.w_short_gap

        # 同じ週（日曜始まり）に集中しないように
        if self.w_week_overload and self.max_per_week:
            per_week: dict[tuple[str, int], int] = {}
            for day, name in assignment.items():
                key = (name, week_index(day))
                per_week[key] = per_week.get(key, 0) + 1
            for count in per_week.values():
                if count > self.max_per_week:
                    cost += self.w_week_overload * (count - self.max_per_week)

        days = self.days

        if self.group and self.max_run >= 1:
            window = self.max_run + 1
            for i in range(len(days) - window + 1):
                if all(assignment.get(days[i + k]) in self.group for k in range(window)):
                    cost += self.w_group_run

        if self.w_fair and self.red_days:
            pool = [n for n in self.members if any(self.ok[(n, d)] for d in self.red_days)]
            if pool:
                counts = {n: 0 for n in pool}
                for day in self.red_days:
                    name = assignment.get(day)
                    if name in counts:
                        counts[name] += 1
                mean = sum(counts.values()) / len(pool)
                cost += self.w_fair * sum((c - mean) ** 2 for c in counts.values())
        return cost

    # -- 日曜の組み合わせ --------------------------------------------------
    def sunday_options(self, limit: int) -> list[dict[dt.date, str]]:
        sundays = [d for d in self.open_days if d.weekday() == SUN]
        if not sundays:
            return [{}]
        pool = self.cfg.weekend_pool or self.members
        # 指定済みの日曜に入っている人は、1人1回ルールのうえで使用済み扱い
        already = {n for d, n in self.fixed.items() if d.weekday() == SUN}
        options: list[tuple[float, dict[dt.date, str]]] = []

        def dfs(index: int, used: set[str], chosen: dict[dt.date, str], cost: float) -> None:
            if len(options) > 20000:
                return
            if index == len(sundays):
                options.append((cost, dict(chosen)))
                return
            day = sundays[index]
            cands = [
                n
                for n in pool
                if self.ok[(n, day)] and (n not in used or not self.cfg.sunday_once_each)
            ]
            for name in cands:
                chosen[day] = name
                used.add(name)
                dfs(index + 1, used, chosen, cost + self.tier_cost[(name, day)])
                used.discard(name)
                del chosen[day]

        dfs(0, set(already), {}, 0.0)
        if not options:
            return []
        options.sort(key=lambda x: x[0])
        return [opt for _, opt in options[:limit]]

    # -- 構築 --------------------------------------------------------------
    def construct(self, sunday_choice: dict[dt.date, str], rng: random.Random) -> dict[dt.date, str] | None:
        remaining = dict(self.remaining_quota)
        for name in sunday_choice.values():
            remaining[name] = remaining.get(name, 0) - 1
        if any(v < 0 for v in remaining.values()):
            return None

        assignment = {**self.fixed, **sunday_choice}
        open_days = [d for d in self.open_days if d not in assignment]
        # 候補が少ない日から埋める
        open_days.sort(key=lambda d: (sum(1 for n in self.members if self.ok[(n, d)]), d))

        for day in open_days:
            pool = [n for n in self.members if remaining.get(n, 0) > 0]
            cands = [n for n in pool if self.ok[(n, day)]] or pool
            if not cands:
                return None
            prev_day = day - dt.timedelta(days=1)
            next_day = day + dt.timedelta(days=1)
            scored = []
            for name in cands:
                score = self.tier_cost[(name, day)]
                if not self.ok[(name, day)]:
                    score += self.w_inelig
                if assignment.get(prev_day) == name or assignment.get(next_day) == name:
                    score += self.w_consec
                else:
                    near = [
                        d
                        for offset in range(2, max(2, self.min_gap_days))
                        for d in (day - dt.timedelta(days=offset), day + dt.timedelta(days=offset))
                        if assignment.get(d) == name
                    ]
                    score += self.w_short_gap * len(near)
                if self.max_per_week:
                    same_week = sum(
                        1
                        for d, n in assignment.items()
                        if n == name and week_index(d) == week_index(day)
                    )
                    if same_week >= self.max_per_week:
                        score += self.w_week_overload
                if name in self.group and self._would_extend_run(assignment, day, name):
                    score += self.w_group_run
                # 残り回数が多い人を優先して消化する
                score -= remaining[name] * 5.0
                score += rng.random() * 8.0
                scored.append((score, name))
            scored.sort()
            chosen = scored[0][1]
            assignment[day] = chosen
            remaining[chosen] -= 1
        return assignment

    def _would_extend_run(self, assignment: dict[dt.date, str], day: dt.date, name: str) -> bool:
        """name を day に置いたとき、グループの連続が上限を超えるか。"""
        if self.max_run < 1:
            return False
        run = 1
        d = day - dt.timedelta(days=1)
        while assignment.get(d) in self.group:
            run += 1
            d -= dt.timedelta(days=1)
        d = day + dt.timedelta(days=1)
        while assignment.get(d) in self.group:
            run += 1
            d += dt.timedelta(days=1)
        return run > self.max_run

    # -- 局所探索 ----------------------------------------------------------
    def improve(
        self, assignment: dict[dt.date, str], sundays: list[dt.date], rng: random.Random, iterations: int
    ) -> tuple[dict[dt.date, str], float]:
        best = dict(assignment)
        best_cost = self.evaluate(best)
        others = [d for d in self.open_days if d not in sundays]
        groups = [g for g in (others, sundays) if len(g) >= 2]
        if not groups:
            return best, best_cost
        for _ in range(iterations):
            bucket = groups[rng.randrange(len(groups))]
            d1, d2 = rng.sample(bucket, 2)
            if best[d1] == best[d2]:
                continue
            best[d1], best[d2] = best[d2], best[d1]
            cost = self.evaluate(best)
            if cost < best_cost - 1e-9:
                best_cost = cost
            else:
                best[d1], best[d2] = best[d2], best[d1]
        return best, best_cost

    # -- 実行 --------------------------------------------------------------
    def solve(self) -> Solution:
        search = self.cfg.search
        rng = random.Random(int(search["seed"]))
        sundays = [d for d in self.open_days if d.weekday() == SUN]
        notes: list[str] = list(self.quota_notes)
        if self.fixed:
            notes.append(
                "先に決めた担当（ルール判定の対象外）: "
                + "、".join(f"{d:%m/%d}={n}" for d, n in sorted(self.fixed.items()))
            )

        options = self.sunday_options(int(search["sunday_candidates"]))
        if not options:
            notes.append(
                "日曜を『1人1回ずつ』で組める組み合わせがありませんでした。"
                "重複を許して割り当てています（日曜のルールを要確認）。"
            )
            saved = self.cfg.raw["roles"]["sunday_once_each"]
            self.cfg.raw["roles"]["sunday_once_each"] = False
            options = self.sunday_options(int(search["sunday_candidates"])) or [{}]
            self.cfg.raw["roles"]["sunday_once_each"] = saved

        best: dict[dt.date, str] | None = None
        best_cost = float("inf")
        restarts = max(1, int(search["restarts"]) // max(1, len(options)))
        iterations = int(search["local_search_iterations"])

        for fixed in options:
            for _ in range(restarts):
                built = self.construct(fixed, rng)
                if built is None:
                    continue
                improved, cost = self.improve(built, sundays, rng, iterations)
                if cost < best_cost:
                    best, best_cost = improved, cost

        if best is None:
            raise RuntimeError(
                "待機表を組めませんでした。回数配分または待機不可条件を見直してください。"
            )

        counts = {n: 0 for n in self.members}
        for name in best.values():
            counts[name] = counts.get(name, 0) + 1
        return Solution(
            assignment=best,
            cost=best_cost,
            counts=counts,
            violations=self.collect_violations(best),
            notes=notes + self.collect_conditional_notes(best) + self.collect_spread_notes(best),
        )

    def collect_spread_notes(self, assignment: dict[dt.date, str]) -> list[str]:
        """間隔が近い・同じ週に集中している箇所を書き出す。"""
        out = []
        days_of: dict[str, list[dt.date]] = {}
        for day, name in assignment.items():
            days_of.setdefault(name, []).append(day)
        for name, mine in sorted(days_of.items()):
            mine.sort()
            for earlier, later in zip(mine, mine[1:]):
                gap = (later - earlier).days
                if 1 < gap < self.min_gap_days:
                    out.append(f"{name}: {earlier:%m/%d} と {later:%m/%d}（間隔{gap}日）")
        if self.max_per_week:
            per_week: dict[tuple[str, int], list[dt.date]] = {}
            for day, name in assignment.items():
                per_week.setdefault((name, week_index(day)), []).append(day)
            for (name, _), days in sorted(per_week.items(), key=lambda x: (x[0][0], x[0][1])):
                if len(days) > self.max_per_week:
                    span = "・".join(f"{d:%m/%d}" for d in sorted(days))
                    out.append(f"{name}: 同じ週に{len(days)}回（{span}）")
        return out

    def collect_conditional_notes(self, assignment: dict[dt.date, str]) -> list[str]:
        """条件付きで可の候補を使った日を書き出す。"""
        out = []
        for day in self.open_days:
            elig = self.engine.eligibility(assignment[day], day)
            if elig.conditional:
                out.append(f"{day:%m/%d} {assignment[day]}: {elig.note}")
        return out

    # -- 検証 --------------------------------------------------------------
    def collect_violations(self, assignment: dict[dt.date, str]) -> list[str]:
        out: list[str] = []
        engine = self.engine
        for day in self.open_days:
            name = assignment[day]
            elig = engine.eligibility(name, day)
            if not elig.ok:
                out.append(f"{day:%m/%d}({'月火水木金土日'[day.weekday()]}) {name}: 待機不可の日に割当（{elig.reason}）")
            if engine.tier(name, day) is None:
                out.append(
                    f"{day:%m/%d} {name}: 優先順位のどれにも当てはまりません"
                    f"（翌日={engine.next_duty_text(name, day)}）"
                )
        for name, target in self.quota.items():
            actual = sum(1 for v in assignment.values() if v == name)
            if actual != target:
                out.append(f"{name}: 回数が目標 {target} 回に対して {actual} 回")

        sundays = [d for d in self.days if d.weekday() == SUN]
        seen: dict[str, dt.date] = {}
        for day in sundays:
            name = assignment[day]
            if name in seen:
                out.append(f"日曜の重複: {name}（{seen[name]:%m/%d} と {day:%m/%d}）")
            seen[name] = day

        if self.group and self.max_run >= 1:
            window = self.max_run + 1
            for i in range(len(self.days) - window + 1):
                span = self.days[i : i + window]
                if all(assignment[d] in self.group for d in span):
                    names = "・".join(assignment[d] for d in span)
                    out.append(
                        f"{span[0]:%m/%d}〜{span[-1]:%m/%d}: "
                        f"{'・'.join(sorted(self.group))}が{window}日連続（{names}）"
                    )
        return out


def solve(
    cfg: Config, engine: RuleEngine, fixed: dict[dt.date, str] | None = None
) -> Solution:
    return Solver(cfg, engine, fixed).solve()
