# ローカル（Windows）での作業手順

クラウド上の Claude Code（claude.ai/code）ではなく、自分の PC で作業するための手順です。

---

## なぜローカルなのか、そして何が守られるのか

| | クラウド（claude.ai/code） | ローカル（この手順） |
|---|---|---|
| リポジトリの置き場所 | Anthropic のコンテナ | あなたの PC |
| `data/` の実データ | 置けない（置けば外部に出る） | PC 内に留まる |
| Claude に読ませたファイル | API に送信される | **API に送信される** |

**重要**: ローカルにしても、Claude に読ませたファイルの中身は Anthropic の API に
送られます。「ローカル = 完全にオフライン」ではありません。個人情報を外に出さない
唯一の確実な方法は、**そのファイルを Claude に触らせないこと**です。
本リポジトリの `.gitignore` と `.claude/settings.json` はそのための仕組みです。

---

## 1. Git for Windows を入れる

https://git-scm.com/downloads/win からインストーラを取得して実行します。
設定はすべて既定のままで構いません。

これを入れておくと Claude Code が Git Bash を使えるようになり、Linux/macOS 向けの
コマンド例がそのまま動きます。入れない場合は PowerShell が使われます。

インストール後、PowerShell を開いて確認します。

```powershell
git --version
```

## 2. Claude Code を入れる

PowerShell（スタートメニューで「PowerShell」と入力）を開いて実行します。
**管理者権限は不要**です。

```powershell
irm https://claude.ai/install.ps1 | iex
```

> コマンドプロンプト（`C:\>` で `PS` が付かない画面）を使っている場合はこちら:
> ```
> curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
> ```

PowerShell を一度閉じて開き直し、確認します。

```powershell
claude --version
claude doctor
```

`claude doctor` はインストール状態と設定を点検して結果を表示します。

## 3. リポジトリをクローンする

作業用フォルダを決めてクローンします（例: `C:\Users\<ユーザー名>\projects`）。

```powershell
mkdir $env:USERPROFILE\projects
cd $env:USERPROFILE\projects
git clone https://github.com/take1017naka-design/taiki.git
cd taiki
```

## 4. 保護の仕組みを有効化する（必須）

コミット前チェックを有効にし、実データ用フォルダを作ります。

```powershell
git config core.hooksPath .githooks
mkdir data
```

- `git config core.hooksPath .githooks` — 個人情報を含みやすいファイルを
  `git commit` の直前で検出して止めます
- `data` — 実データ置き場。`.gitignore` により Git に載らず、
  `.claude/settings.json` により Claude も読めません

## 5. Claude Code を起動してログイン

```powershell
claude
```

初回はブラウザが開くのでログインします（Claude Pro / Max / Team / Enterprise の
いずれかの契約が必要です。無料プランでは Claude Code は使えません）。
ブラウザが自動で開かない場合は `c` キーで URL をコピーして貼り付けます。

## 6. 動作確認

Claude Code のプロンプトで次を試し、保護が効いていることを確認してください。

```
data/ の中身を読んでみて
```

`Read` が拒否されれば設定は正しく効いています。

---

## 日々の使い方

```powershell
cd $env:USERPROFILE\projects\taiki
git pull origin main
claude
```

作業が終わったら:

```powershell
git add .
git commit -m "変更内容の説明"
git push -u origin main
```

`git commit` が赤字で止まった場合、個人情報を含むファイルを混ぜている可能性が
あります。メッセージに従って `data/` へ移してください。

### コミット前フックが見ているもの

1. **拡張子** — `.csv` `.xlsx` `.dcm` `.pdf` など、データが入りやすい形式
   （`sample_data/` 配下と `sample_` / `dummy_` / `test_` で始まるファイルは除外）
2. **フォルダ** — `data/` `raw/` `private/` `secret/` に置かれたファイル
3. **中身** — 患者氏名・カルテ番号・保険証番号などの項目名のあとに `:` や `=` が
   続き、その先に値が書かれている行。説明のために項目名を文章中で挙げるだけの
   行は通ります

誤検知だと確認できた場合のみ `git commit --no-verify` で回避できます。

---

## 実データを扱うときの原則

1. 実データは `data/` にだけ置く
2. Claude に見せるのは `sample_data/` のダミーデータだけ
3. 実データを処理するスクリプトは、**結果として個人情報を画面に出さない**
   （件数・平均・グラフなど、集計値だけを出力する）

3 が特に重要です。deny 設定は Claude のファイル読み取りとシェルの `cat` 等を
止めますが、あなたが書いた Python スクリプトが `data/` を開いて中身を
`print()` する処理までは止められません。その出力は Claude の目に入ります。

悪い例:

```python
df = pd.read_csv("data/export.csv")
print(df.head())        # 患者データがそのまま画面に出る
```

良い例:

```python
df = pd.read_csv("data/export.csv")
print(f"{len(df)} 件, 列: {list(df.columns)}")   # 構造だけ
print(df["年齢"].describe())                      # 集計値だけ
```

---

## クラウド版との使い分け

クラウド版（claude.ai/code）は、リポジトリを Anthropic のコンテナにクローンして
動きます。**個人情報を含むファイルは絶対に置かないでください。**
コードの設計相談・リファクタリング・ドキュメント作成など、実データを伴わない作業
であればクラウド版も安全に使えます。

---

## 困ったとき

```powershell
claude doctor     # インストールと設定の診断
```

公式ドキュメント: https://code.claude.com/docs/en/setup
