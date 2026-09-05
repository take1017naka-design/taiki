# taiki

## セットアップ

自分の PC（Windows）で作業する手順は **[docs/local-setup.md](docs/local-setup.md)** を参照してください。

## 個人情報の取り扱い

このリポジトリは患者個人情報を一切含みません。実データは `data/`（Git 管理外・
Claude 読み取り不可）にのみ置いてください。詳細は [CLAUDE.md](CLAUDE.md) を参照。

クローン後、次のコマンドで誤コミット防止のフックを有効化してください。

```bash
git config core.hooksPath .githooks
mkdir data
```
