# Erdos Agent MVP

Codexでエルディッシュ問題を扱うための、最初の小さな研究オペレーション用MVPです。

目的は「いきなり解く」ことではなく、問題の出自や未解決ラベルをSolverから隠したうえで、triage、匿名化パケット、statement audit、claim cardを作ることです。

## 方針

- Solverには問題番号、Erdős Problems由来、open/solved、賞金、URLを渡さない
- Literature Agentは検索してよいが、Solverには匿名化した数学的Result Cardだけ渡す
- novelty判定と投稿判断は、最後のstatus-aware Referee Gateで行う
- 自動投稿はしない
- Leanが通っても、定理文と元問題の一致は別途確認する

## セットアップ

```bash
python3 -m erdos_agent init
```

## 問題JSONを作る

```bash
python3 -m erdos_agent new 728 \
  --statement-file statement.txt \
  --title "local private title" \
  --tag "number theory"
```

## MVPパイプラインを走らせる

```bash
python3 -m erdos_agent pipeline 728
```

生成物:

```text
data/problems/ep0728.json
data/manifests/math-task-xxxxxxxxxxxx.json
packets/blind/math-task-xxxxxxxxxxxx.md
packets/literature/math-task-xxxxxxxxxxxx.md
reports/triage/ep0728.json
reports/statement_audits/ep0728.md
reports/attempts/ep0728.claim.md
```

## 公式GitHubデータを取り込む

まずメタデータだけ取り込む場合:

```bash
python3 -m erdos_agent ingest-github
```

open扱いの問題だけ取り込む場合:

```bash
python3 -m erdos_agent ingest-github --status open
```

最初の数件だけ、公式ページのLaTeX表示からstatementも取る場合:

```bash
python3 -m erdos_agent ingest-github --status open --limit 5 --fetch-statements
```

`--fetch-statements` は `https://www.erdosproblems.com/latex/<番号>` にアクセスします。全件取得はサイトへ連続アクセスするため、必要な範囲に絞って使う想定です。

## 複数問題をtriageする

```bash
python3 -m erdos_agent triage-all --status open --limit 30
```

生成物:

```text
reports/triage/index.json
reports/triage/epNNNN.json
```

`triage-all` はデフォルトでopen問題だけを見ます。全ステータスを見る場合:

```bash
python3 -m erdos_agent triage-all --status all --limit 50
```

## 解けた問題から横展開候補を探す

seed問題に似たopen問題を探します。自分で解いた問題だけでなく、誰かが新しく解いた問題をseedにする運用も想定しています。

```bash
python3 -m erdos_agent transfer-search 728 --status open --limit 20
```

生成物:

```text
reports/analogies/ep0728.json
```

現時点のMVPでは、タグ、statement/remarks内の数学用語、共有参考文献、OEIS、formalization metadataを使って近さを計算します。将来的には、解法の核を匿名化した `Method Card` にして、似たopen問題へBlind Solverとして再投入する設計にします。

## Literature findingからピボットする

検索エージェントが有望な論文・手法・構成を見つけたら、findingとして保存します。

```bash
python3 -m erdos_agent add-finding 9 \
  --paper-key "Cr71" \
  --title "On the sum of a prime and of two powers of two" \
  --summary "Uses a construction related to primes plus powers of two." \
  --method-tag "additive basis" \
  --method-tag "primes" \
  --example "Odd integers not represented as p + 2^k + 2^l"
```

そのfindingから、似たopen問題へのピボット候補を出します。

```bash
python3 -m erdos_agent pivot-from-finding ep0009-cr71 --status open --limit 20
```

## 数学exampleを保存する

```bash
python3 -m erdos_agent add-example distinct-subset-sums-powers-of-two \
  --statement "The powers of two have distinct subset sums." \
  --tag "subset sums" \
  --role "model construction"
```

知識ベースは `kb/` 以下に作られます。設計メモは [docs/knowledge_base.md](docs/knowledge_base.md) と [docs/agent_protocol.md](docs/agent_protocol.md) を見てください。

## 推奨運用

1. `pipeline` で匿名化パケットとtriageを作る
2. `packets/blind/*.md` だけをBlind Solverへ渡す
3. Literature Agentには `packets/literature/*.md` を渡す
4. Literature Agentの出典つき報告はSupervisorだけが保持する
5. Solverへは匿名化したResult Cardだけを渡す
6. Claim Cardを埋める
7. 人間が読んでからLean/計算/文献で検証する
8. Referee Gateを通るまで投稿しない

## 現時点のスコープ

このMVPはOpenAI APIやLeanをまだ直接呼びません。まず情報隔離、公式メタデータ取り込み、triageランキング、成果物の形を固定するための土台です。
