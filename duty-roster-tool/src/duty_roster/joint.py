"""待機と予備を同時に組む（joint mode）。

待機を先に確定してから予備を埋めると、待機の決め方しだいで予備が
「連日」や「翌日が手術室」しか残らない日ができる。ここでは両方を同時に
動かして、日ごとの可否（○・△）の中から連日の少ない組み合わせを探す。

やっていること:

1. これまでどおりの2段階（待機 → 予備）で出発点を作る。必ず解ける形なので、
   同時最適化が失敗しても最低限その解に戻せる。
2. 待機の回数配分（quota）を崩さない手だけを使って、待機と予備を一緒に動かす。

   * 待機の2日入れ替え（回数は変わらない）
   * 予備の入れ替え（1日ぶんの差し替え・2日の交換）
   * 待機と予備の役割交換（1日）＋回数を戻すための待機入れ替え（別の1日）

3. コストは「待機のコスト＋予備のコスト」。連日や翌日手術室の重みは
   これまでと同じものをそのまま使う。

待機側のコストのほうが重い（回数・優先順位・日曜1人1回）ので、
同時に動かしても待機表が大きく崩れることはない。
"""

from __future__ import annotations

import datetime as dt
import random

from .backup import BackupSolution, BackupSolver
from .config import Config
from .rules import RuleEngine
from .solver import Solution, Solver


class JointSolver:
    def __init__(
        self,
        cfg: Config,
        engine: RuleEngine,
        fixed_primary: dict[dt.date, str] | None = None,
        fixed_backup: dict[dt.date, str] | None = None,
        holiday_history: dict[str, int] | None = None,
    ):
        self.cfg = cfg
        self.engine = engine
        self.days = engine.days
        self.members = engine.members
        self.primary_solver = Solver(cfg, engine, fixed_primary)
        self.fixed_primary = self.primary_solver.fixed
        self.fixed_backup = dict(fixed_backup or {})
        self.holiday_history = holiday_history
        # 予備側は待機表を差し替えながら使うので、あとで rebind する
        self.backup_solver: BackupSolver | None = None

    # -- コスト ------------------------------------------------------------
    def evaluate(
        self, primary: dict[dt.date, str], backup: dict[dt.date, str]
    ) -> float:
        assert self.backup_solver is not None
        self.backup_solver.rebind(primary)
        return self.primary_solver.evaluate(primary) + self.backup_solver.evaluate(backup)

    # -- 予備の修復 --------------------------------------------------------
    def repair_backup(
        self,
        primary: dict[dt.date, str],
        backup: dict[dt.date, str],
        rng: random.Random,
        days: list[dt.date] | None = None,
    ) -> None:
        """待機が変わった日の予備を、破綻しない値に直す（その場で書き換える）。

        * 自動確定（待機が依存2名）の日はバックアップ役に戻す
        * 待機と予備が同じ人になった日は別の人に差し替える
        """
        solver = self.backup_solver
        assert solver is not None
        solver.rebind(primary)
        for day in days if days is not None else self.days:
            if day in solver.fixed:
                backup[day] = solver.fixed[day]
                continue
            if day in solver.forced:
                backup[day] = solver.forced[day]
                continue
            if backup.get(day) is None or backup[day] == primary.get(day):
                cands = solver.candidates(day)
                backup[day] = cands[rng.randrange(len(cands))] if cands else backup.get(day, "")

    # -- 手 ----------------------------------------------------------------
    def _swap_primary(
        self,
        primary: dict[dt.date, str],
        backup: dict[dt.date, str],
        rng: random.Random,
        bucket: list[dt.date],
    ) -> tuple[dict[dt.date, str], dict[dt.date, str]] | None:
        """待機を2日ぶん入れ替える（回数は変わらない）。"""
        if len(bucket) < 2:
            return None
        d1, d2 = rng.sample(bucket, 2)
        if primary[d1] == primary[d2]:
            return None
        new_p = dict(primary)
        new_p[d1], new_p[d2] = new_p[d2], new_p[d1]
        new_b = dict(backup)
        self.repair_backup(new_p, new_b, rng)
        return new_p, new_b

    def _change_backup(
        self,
        primary: dict[dt.date, str],
        backup: dict[dt.date, str],
        rng: random.Random,
    ) -> tuple[dict[dt.date, str], dict[dt.date, str]] | None:
        """予備を1日ぶん差し替える。"""
        solver = self.backup_solver
        assert solver is not None
        solver.rebind(primary)
        open_days = [d for d in self.days if d not in solver.forced]
        if not open_days:
            return None
        day = open_days[rng.randrange(len(open_days))]
        cands = [n for n in solver.candidates(day) if n != backup[day]]
        if not cands:
            return None
        new_b = dict(backup)
        new_b[day] = cands[rng.randrange(len(cands))]
        return dict(primary), new_b

    def _swap_backup(
        self,
        primary: dict[dt.date, str],
        backup: dict[dt.date, str],
        rng: random.Random,
    ) -> tuple[dict[dt.date, str], dict[dt.date, str]] | None:
        """予備を2日ぶん交換する。"""
        solver = self.backup_solver
        assert solver is not None
        solver.rebind(primary)
        open_days = [d for d in self.days if d not in solver.forced]
        if len(open_days) < 2:
            return None
        d1, d2 = rng.sample(open_days, 2)
        if backup[d1] == backup[d2]:
            return None
        if backup[d1] == primary[d2] or backup[d2] == primary[d1]:
            return None
        new_b = dict(backup)
        new_b[d1], new_b[d2] = new_b[d2], new_b[d1]
        return dict(primary), new_b

    def _exchange_roles(
        self,
        primary: dict[dt.date, str],
        backup: dict[dt.date, str],
        rng: random.Random,
        bucket: list[dt.date],
    ) -> tuple[dict[dt.date, str], dict[dt.date, str]] | None:
        """ある日の待機と予備を入れ替え、待機の回数は別の日で戻す。

        d1 で待機 p と予備 b を交換すると p が1回減り b が1回増えるので、
        待機が b の別の日 d2 を p に替えて回数を元に戻す。
        """
        if not bucket:
            return None
        d1 = bucket[rng.randrange(len(bucket))]
        p, b = primary[d1], backup[d1]
        if p == b:
            return None
        # 交換後の可否をざっと見る（詳細はコストで評価する）
        cands = [
            d2
            for d2 in bucket
            if d2 != d1 and primary[d2] == b and backup.get(d2) != p
        ]
        if not cands:
            return None
        d2 = cands[rng.randrange(len(cands))]
        new_p = dict(primary)
        new_b = dict(backup)
        new_p[d1], new_b[d1] = b, p
        new_p[d2] = p
        self.repair_backup(new_p, new_b, rng)
        return new_p, new_b

    # -- 実行 --------------------------------------------------------------
    def solve(self) -> tuple[Solution, BackupSolution]:
        conf = self.cfg.joint_search
        rng = random.Random(int(self.cfg.search["seed"]) + 11)

        # 1. これまでどおりの2段階で出発点を作る
        base_primary = self.primary_solver.solve()
        self.backup_solver = BackupSolver(
            self.cfg,
            self.engine,
            base_primary.assignment,
            self.fixed_backup,
            self.holiday_history,
        )
        base_backup = self.backup_solver.solve()

        best_p = dict(base_primary.assignment)
        best_b = dict(base_backup.assignment)
        best_cost = self.evaluate(best_p, best_b)

        # 待機を動かしてよい日（先に決めた日は動かさない）
        movable = [d for d in self.days if d not in self.fixed_primary]
        sundays = [d for d in movable if d.weekday() == 6]
        others = [d for d in movable if d.weekday() != 6]
        # 日曜は「1人1回ずつ」なので日曜どうしでしか入れ替えない
        buckets = [g for g in (others, sundays) if len(g) >= 2]

        iterations = max(1, int(conf.get("iterations", 12000)))
        cur_p, cur_b, cur_cost = dict(best_p), dict(best_b), best_cost
        for _ in range(iterations):
            roll = rng.random()
            if roll < 0.35 and buckets:
                move = self._swap_primary(
                    cur_p, cur_b, rng, buckets[rng.randrange(len(buckets))]
                )
            elif roll < 0.60:
                move = self._change_backup(cur_p, cur_b, rng)
            elif roll < 0.80:
                move = self._swap_backup(cur_p, cur_b, rng)
            elif buckets:
                move = self._exchange_roles(
                    cur_p, cur_b, rng, buckets[rng.randrange(len(buckets))]
                )
            else:
                move = None
            if move is None:
                continue
            new_p, new_b = move
            cost = self.evaluate(new_p, new_b)
            if cost < cur_cost - 1e-9:
                cur_p, cur_b, cur_cost = new_p, new_b, cost
                if cost < best_cost - 1e-9:
                    best_p, best_b, best_cost = dict(new_p), dict(new_b), cost

        # 2. 出発点より悪くなることはないが、念のため確認して良いほうを返す
        if best_cost > self.evaluate(base_primary.assignment, base_backup.assignment) - 1e-9:
            best_p = dict(base_primary.assignment)
            best_b = dict(base_backup.assignment)

        # 3. 決まった待機表に対して、予備だけを本来のソルバで組み直す。
        #    同時探索は待機を動かすことに使い、予備の詰めはこちらに任せる。
        polished = BackupSolver(
            self.cfg, self.engine, best_p, self.fixed_backup, self.holiday_history
        ).solve()
        if self.evaluate(best_p, polished.assignment) < self.evaluate(best_p, best_b) - 1e-9:
            best_b = dict(polished.assignment)

        return self._finish(best_p, best_b, self.primary_solver.base_notes)

    def _finish(
        self,
        primary: dict[dt.date, str],
        backup: dict[dt.date, str],
        primary_notes: list[str],
    ) -> tuple[Solution, BackupSolution]:
        solver = self.primary_solver
        bsolver = self.backup_solver
        assert bsolver is not None
        bsolver.rebind(primary)

        p_counts = {n: 0 for n in self.members}
        for name in primary.values():
            p_counts[name] = p_counts.get(name, 0) + 1
        solution = Solution(
            assignment=primary,
            cost=solver.evaluate(primary),
            counts=p_counts,
            violations=solver.collect_violations(primary),
            notes=(
                primary_notes
                + solver.collect_conditional_notes(primary)
                + solver.collect_spread_notes(primary)
            ),
        )

        b_counts = {n: 0 for n in self.members}
        for name in backup.values():
            b_counts[name] = b_counts.get(name, 0) + 1
        backup_solution = BackupSolution(
            assignment=backup,
            cost=bsolver.evaluate(backup),
            counts=b_counts,
            forced=dict(bsolver.forced),
            violations=bsolver.collect_violations(backup),
            notes=bsolver.collect_notes(backup),
        )
        return solution, backup_solution


def solve_joint(
    cfg: Config,
    engine: RuleEngine,
    fixed_primary: dict[dt.date, str] | None = None,
    fixed_backup: dict[dt.date, str] | None = None,
    holiday_history: dict[str, int] | None = None,
) -> tuple[Solution, BackupSolution]:
    return JointSolver(
        cfg, engine, fixed_primary, fixed_backup, holiday_history
    ).solve()
