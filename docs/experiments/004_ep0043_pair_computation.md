# Experiment 004: EP43 Sidon Pair Computation

Date: 2026-05-14

Seed problem: `ep0043`

Goal: before trying proof generation, build exact small-case data for the EP43
formulation itself:

```text
A, B subset {1, ..., N}
A and B are Sidon sets
(A-A) cap (B-B) = {0}
maximize binom(|A|, 2) + binom(|B|, 2)
```

The comparison baseline is `binom(f(N), 2)`, where `f(N)` is the maximum size of a
Sidon subset of `{1, ..., N}`.

## Added Computation Mode

The computation worker now detects EP43-style statements and selects:

```text
sidon_pair_disjoint_diffs_exact
```

The generated harness enumerates Sidon subsets, stores their positive-difference masks,
and searches pairs whose masks are disjoint. It reports:

- the best unrestricted pair value
- one witness pair `(A, B)`
- `f_N`
- the baseline `binom(f_N, 2)`
- the excess over baseline
- the best equal-size pair value and witness

Generated local artifacts:

```text
computations/ep0043/README.md
computations/ep0043/search.py
computations/ep0043/results.md
```

These remain ignored by Git.

## Commands Run

```bash
python3 -m erdos_agent create-run --problem 43 --agent computation --priority 1
python3 -m erdos_agent run-next-agent --agent computation
python3 computations/ep0043/search.py --max-n 20
python3 -m erdos_agent proof-route-packet 43 --route difference-packing
python3 -m erdos_agent queue-proof-route 43 --route difference-packing
python3 -m erdos_agent run-next-agent --agent blind_solver
```

## Small-Case Summary

Exact search through `N = 20` did not show a large violation signal.

| N range | max unrestricted excess | max equal-size excess |
|---|---:|---:|
| 1..10 | 3 | 1 |
| 1..14 | 3 | 2 |
| 1..20 | 3 | 2 |

Selected rows:

| N | value | baseline | excess | equal-size value | equal-size excess |
|---:|---:|---:|---:|---:|---:|
| 10 | 9 | 6 | 3 | 6 | 0 |
| 14 | 12 | 10 | 2 | 12 | 2 |
| 16 | 13 | 10 | 3 | 12 | 2 |
| 20 | 18 | 15 | 3 | 12 | -3 |

## Interpretation

This is not a proof. It is useful triage data:

- No small counterexample suggests growth beyond the `+O(1)` allowance.
- The unrestricted optimum often comes from one large Sidon set plus a small compatible
  second set.
- The equal-size variant appears more restrictive in these small cases, with no signal
  yet against a constant-factor improvement.

## Next Proof-Oriented Step

Use the generated proof-search packet:

```text
packets/blind/math-task-b2ab29b556e1-difference-packing.md
```

The packet asks for:

1. Express EP43 as a packing problem for positive difference sets.
2. Ask whether every Sidon pair with disjoint positive-difference masks can be injected,
   up to `O(1)` slack, into the positive-difference set of a maximum Sidon set.
3. Compare this with the `popular differences`/generalized Sidon literature candidate
   before any source-aware idea is passed to a blind solver.

The queue handoff generated:

```text
reports/attempts/ep0043-difference_packing-blind-handoff.md
```
