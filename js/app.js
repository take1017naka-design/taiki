/* PSVTアブレーション 用語・メモ帳
 * データはこの端末のブラウザ(localStorage)に保存されます。
 * 「データ管理」タブのエクスポート/インポートでバックアップ・Git管理してください。
 */

const STORAGE_KEY = "psvt-ablation-app-data-v1";

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function nowStr() {
  return new Date().toLocaleString("ja-JP");
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// エスケープ済みテキストに対して検索語を <mark> でハイライトする
function highlightText(str, query) {
  const escaped = escapeHtml(str);
  if (!query) return escaped;
  return escaped.replace(new RegExp(escapeRegExp(escapeHtml(query)), "ig"), (m) => `<mark>${m}</mark>`);
}

// 用語辞書の初期収録データ。version番号を上げて配列を追加すると、
// 既にlocalStorageにデータがある端末にも次回起動時に自動で追記される(mergeSeedTerms参照)。
const CURRENT_TERMS_SEED_VERSION = 8;

function seedTermsV1() {
  return [
    {
      term: "PSVT", reading: "はっさせいじょうしつせいひんぱく",
      category: "不整脈", description: "発作性上室性頻拍(Paroxysmal SupraVentricular Tachycardia)。突然始まり突然止まる規則正しい頻拍の総称。代表的な機序にAVNRT・AVRTがある。",
      related: "AVNRT, AVRT, WPW症候群, 心房頻拍(AT), Long RP/Short RP頻拍", memo: "",
    },
    {
      term: "AVNRT", reading: "ぼうしつけっせつりえんとりーせいひんぱく",
      category: "不整脈", description: "房室結節リエントリー性頻拍。房室結節内の遅伝導路(slow pathway)と速伝導路(fast pathway)の二重伝導路を旋回するリエントリー性頻拍。アブレーションではslow pathwayを焼灼することが多い。",
      related: "PSVT, Slow pathway(遅伝導路), Fast pathway(速伝導路), ジャンプ現象(AH jump), スロー・ファスト型AVNRT(Typical), ファスト・スロー型/スロー・スロー型AVNRT(Atypical), Koch三角(Koch's triangle), 房室結節(AV node)", memo: "",
    },
    {
      term: "AVRT", reading: "ぼうしつりえんとりーせいひんぱく",
      category: "不整脈", description: "房室リエントリー性頻拍。房室結節と副伝導路(Kent束など)を旋回するリエントリー性頻拍。WPW症候群に伴うことが多い。",
      related: "PSVT, WPW症候群, 副伝導路(Accessory pathway), 順行性AVRT(Orthodromic AVRT), 逆方向性AVRT(Antidromic AVRT), マハイム線維/マハイム型頻拍", memo: "",
    },
    {
      term: "WPW症候群", reading: "だぶりゅーぴーだぶりゅーしょうこうぐん",
      category: "不整脈", description: "Wolff-Parkinson-White症候群。副伝導路(Kent束)の存在によりデルタ波・PQ短縮を示し、AVRTを起こしやすい病態。",
      related: "AVRT, 副伝導路(Accessory pathway), 顕性WPW症候群/潜在性WPW症候群, 順行性AVRT(Orthodromic AVRT), 逆方向性AVRT(Antidromic AVRT)", memo: "",
    },
    {
      term: "His束", reading: "ひすそく",
      category: "解剖", description: "房室結節から続き、左右脚に分かれる特殊心筋の伝導路。カテーテルを置いてHis電位を記録し、房室伝導の評価やカテーテル位置の指標に用いる。",
      related: "房室結節(AV node), AH時間, HV時間, Koch三角(Koch's triangle), Para-Hisian pacing(パラヒス電位ペーシング), 完全房室ブロック(complete AV block)", memo: "",
    },
    {
      term: "冠静脈洞(CS)", reading: "かんじょうみゃくどう",
      category: "解剖", description: "Coronary Sinus。左房後壁を走行する静脈で、多極カテーテルを留置して左房側の興奮伝播順序を記録するのに使われる。",
      related: "Koch三角(Koch's triangle), 僧帽弁輪(MA), 卵円窩(Fossa ovalis)", memo: "",
    },
    {
      term: "エントレインメント", reading: "えんとれいんめんと",
      category: "手技・検査", description: "頻拍中にペーシングで頻拍レートより速く駆動し、頻拍がリエントリー性かどうか、また回路上の部位かを判定する手技。post-pacing interval(PPI)などで評価する。",
      related: "PPI(Post-Pacing Interval), Orthodromic His capture, Antidromic His capture, デクリメンタルペーシング/バーストペーシング", memo: "",
    },
    {
      term: "ERP(有効不応期)", reading: "いーあーるぴー",
      category: "生理検査", description: "Effective Refractory Period。刺激を加えても伝導・興奮が生じなくなる最長の連結期。房室結節や副伝導路の伝導特性評価に用いる。",
      related: "Wenckebach周期長(AVN Wenckebach cycle length), プログラム電気刺激(PES)/期外刺激, Slow pathway(遅伝導路), Fast pathway(速伝導路)", memo: "",
    },
  ];
}

// v2で追加した用語(2026-09時点でエビデンス確認済み: Coumel's law, para-Hisian pacingはPubMed/JACC等で内容照合)
function seedTermsV2() {
  return [
    {
      term: "心房頻拍(AT)", reading: "しんぼうひんぱく",
      category: "不整脈", description: "心房内の限局した部位が異常興奮源(または小さなリエントリー回路)となって生じる頻拍。頻拍回路に房室結節を含まないため、房室ブロックが生じても頻拍自体は持続することがある点がAVNRT/AVRTと異なる。",
      related: "PSVT, Long RP/Short RP頻拍, 完全房室ブロック(complete AV block)", memo: "",
    },
    {
      term: "順行性AVRT(Orthodromic AVRT)", reading: "じゅんこうせいえーぶいあーるてぃー",
      category: "不整脈", description: "房室結節を順行、副伝導路を逆行して旋回するAVRT。心室の興奮が正常のHis-Purkinje系を介するためQRS幅は狭い。AVRTの大部分を占める。",
      related: "AVRT, 逆方向性AVRT(Antidromic AVRT), 副伝導路(Accessory pathway), Coumel's law(クメール徴候), Antidromic His capture", memo: "",
    },
    {
      term: "逆方向性AVRT(Antidromic AVRT)", reading: "ぎゃくほうこうせいえーぶいあーるてぃー",
      category: "不整脈", description: "副伝導路を順行、房室結節(または別の副伝導路)を逆行して旋回するAVRT。心室興奮が副伝導路経由となるためQRS幅は広くなり、心室頻拍との鑑別が必要になる。",
      related: "AVRT, 順行性AVRT(Orthodromic AVRT), マハイム線維/マハイム型頻拍, 副伝導路(Accessory pathway)", memo: "",
    },
    {
      term: "マハイム線維/マハイム型頻拍", reading: "まはいむせんい",
      category: "不整脈", description: "房室結節に似た減衰伝導特性を持つ副伝導路(多くは右房室輪〜右脚方向を走行するatriofascicular fiber)。順行性伝導のみを示すことが多く、これを用いた頻拍はQRSが広く逆方向性AVRTに似た波形を示す。",
      related: "逆方向性AVRT(Antidromic AVRT), 副伝導路(Accessory pathway)", memo: "",
    },
    {
      term: "Long RP/Short RP頻拍", reading: "ろんぐあーるぴー・しょーとあーるぴーひんぱく",
      category: "不整脈", description: "頻拍のQRSから逆行性P波までの時間(RP)がPR間隔より短いか長いかによる分類。Short RPはtypical AVNRTや順行性AVRTに多く、Long RPはatypical AVNRT・PJRT・心房頻拍などで見られ、鑑別診断の手がかりとなる。",
      related: "AVNRT, AVRT, 心房頻拍(AT), スロー・ファスト型AVNRT(Typical), ファスト・スロー型/スロー・スロー型AVNRT(Atypical)", memo: "",
    },
    {
      term: "Coumel's law(クメール徴候)", reading: "くめーるちょうこう",
      category: "不整脈", description: "順行性AVRT中に副伝導路と同側の脚ブロックが出現すると、その脚を介する迂回路が長くなるため頻拍周期長とVA時間が延長する現象(VA時間で20ms超の延長がほぼ確実にAVRTを示唆)。副伝導路の左右局在診断に利用する。",
      related: "順行性AVRT(Orthodromic AVRT), VA time(VA interval), 副伝導路(Accessory pathway)", memo: "出典: PubMed/JACC(2026年時点で内容確認済み)",
    },
    {
      term: "顕性WPW症候群/潜在性WPW症候群", reading: "けんせい・せんざいせいだぶりゅーぴーだぶりゅー",
      category: "不整脈", description: "洞調律時のデルタ波の有無による分類。顕性は副伝導路が順行伝導能を持ちデルタ波が出現する。潜在性(concealed)は副伝導路が逆行伝導のみでデルタ波は出現しないが、AVRTは起こしうる。",
      related: "WPW症候群, 副伝導路(Accessory pathway), 順行性AVRT(Orthodromic AVRT)", memo: "",
    },
    {
      term: "スロー・ファスト型AVNRT(Typical)", reading: "すろー・ふぁすとがたえーぶいえぬあーるてぃー",
      category: "不整脈", description: "遅伝導路(slow pathway)を順行、速伝導路(fast pathway)を逆行して旋回するAVNRTで、AVNRTの大部分(typical)を占める。心房と心室がほぼ同時に興奮するためRP間隔が非常に短い。",
      related: "AVNRT, ジャンプ現象(AH jump), Slow pathway(遅伝導路), Fast pathway(速伝導路), Long RP/Short RP頻拍", memo: "",
    },
    {
      term: "ファスト・スロー型/スロー・スロー型AVNRT(Atypical)", reading: "あてぃぴかるえーぶいえぬあーるてぃー",
      category: "不整脈", description: "atypical AVNRTのうち、速伝導路を順行・遅伝導路を逆行するのがファスト・スロー型、2本の遅伝導路を用いるのがスロー・スロー型。いずれもLong RP頻拍を呈することが多い。",
      related: "AVNRT, Long RP/Short RP頻拍, Slow pathway(遅伝導路), Fast pathway(速伝導路), スロー・ファスト型AVNRT(Typical)", memo: "",
    },
    {
      term: "Koch三角(Koch's triangle)", reading: "こっほさんかく",
      category: "解剖", description: "三尖弁輪・Todaro腱・冠静脈洞口によって囲まれる右房内の三角形の領域。房室結節はこの三角の頂点付近に位置し、遅伝導路アブレーションの際の解剖学的な指標となる。",
      related: "Todaro腱(Tendon of Todaro), 三尖弁輪(TA), 冠静脈洞(CS), 房室結節(AV node), Slow pathway(遅伝導路), Fast pathway(速伝導路)", memo: "",
    },
    {
      term: "Todaro腱(Tendon of Todaro)", reading: "とだろけん",
      category: "解剖", description: "下大静脈弁の延長にあたる線維性の構造物で、Koch三角の一辺を形成する。房室結節・遅伝導路の位置を把握する際の目印となる。",
      related: "Koch三角(Koch's triangle), 房室結節(AV node)", memo: "",
    },
    {
      term: "卵円窩(Fossa ovalis)", reading: "らんえんか",
      category: "解剖", description: "心房中隔にある膜様の陥凹部。胎児期の卵円孔の遺残構造で、左房側の手技を行う際の経中隔穿刺(transseptal puncture)の穿刺部位となる。",
      related: "僧帽弁輪(MA), 冠静脈洞(CS), 心タンポナーデ(cardiac tamponade)", memo: "",
    },
    {
      term: "三尖弁輪(TA)", reading: "さんせんべんりん",
      category: "解剖", description: "Tricuspid Annulus。右房と右室の間の弁輪部。カテーテル位置の指標や、右側副伝導路の局在診断に用いられる。",
      related: "Koch三角(Koch's triangle), 僧帽弁輪(MA), 副伝導路(Accessory pathway)", memo: "",
    },
    {
      term: "僧帽弁輪(MA)", reading: "そうぼうべんりん",
      category: "解剖", description: "Mitral Annulus。左房と左室の間の弁輪部。左側副伝導路(左自由壁など)の局在診断に用いられる。",
      related: "三尖弁輪(TA), 副伝導路(Accessory pathway), 卵円窩(Fossa ovalis)", memo: "",
    },
    {
      term: "PPI(Post-Pacing Interval)", reading: "ぽすとぺーしんぐいんたーばる",
      category: "手技・検査", description: "頻拍中にエントレインメントペーシングを行った後、最後の刺激からその部位に興奮が戻ってくるまでの時間。頻拍周期長との差(PPI-TCL)が小さいほど、その部位が頻拍回路に近い/回路上にあることを示す。",
      related: "エントレインメント, VA time(VA interval)", memo: "",
    },
    {
      term: "VA time(VA interval)", reading: "ぶいえーたいむ",
      category: "手技・検査", description: "心室興奮の開始(V)から逆行性心房興奮(A)までの時間。頻拍機序の鑑別(AVNRTかAVRTかなど)や、Coumel's lawによる副伝導路局在診断に用いる。",
      related: "Coumel's law(クメール徴候), 順行性伝導/逆行性伝導, Para-Hisian pacing(パラヒス電位ペーシング)", memo: "",
    },
    {
      term: "Para-Hisian pacing(パラヒス電位ペーシング)", reading: "ぱらひすぺーしんぐ",
      category: "手技・検査", description: "His束近傍を高出力でペーシングしHis-右脚を巻き込んで捕捉した状態と、出力を下げてHis-右脚の捕捉が外れた状態とで、逆行性心房興奮のタイミング・パターンを比較する手技。副伝導路を介した逆行性伝導と房室結節を介した逆行性伝導を鑑別する。",
      related: "His束, 順行性伝導/逆行性伝導, 副伝導路(Accessory pathway), 差動性ペーシング(Differential pacing), VA time(VA interval)", memo: "出典: Circulation 1996, JACC EP 2019(2026年時点で内容確認済み)",
    },
    {
      term: "差動性ペーシング(Differential pacing)", reading: "さどうせいぺーしんぐ",
      category: "手技・検査", description: "異なる部位(例: 右室心尖部と右室基部近傍)からペーシングし、逆行性伝導の応答(タイミングやパターン)の違いを比較する手技。副伝導路の関与を評価する際などに用いられる。",
      related: "Para-Hisian pacing(パラヒス電位ペーシング), 順行性伝導/逆行性伝導", memo: "",
    },
    {
      term: "デクリメンタルペーシング/バーストペーシング", reading: "でくりめんたる・ばーすとぺーしんぐ",
      category: "手技・検査", description: "刺激周期を段階的に短くしていく漸増式の刺激(デクリメンタルペーシング)と、一定の速いレートで連続的に刺激するバーストペーシングの総称。頻拍の誘発や停止、伝導特性の評価に用いる。",
      related: "プログラム電気刺激(PES)/期外刺激, エントレインメント, Wenckebach周期長(AVN Wenckebach cycle length)", memo: "",
    },
    {
      term: "プログラム電気刺激(PES)/期外刺激", reading: "ぷろぐらむでんきしげき",
      category: "手技・検査", description: "Programmed Electrical Stimulation。一定の基本周期(S1)で刺激した後、連結期を段階的に短縮した期外刺激(S2, S3…)を加える手法。不応期の測定や頻拍の誘発に用いる。",
      related: "ERP(有効不応期), ジャンプ現象(AH jump), デクリメンタルペーシング/バーストペーシング, エコー心拍(echo beat)", memo: "",
    },
    {
      term: "AH時間", reading: "えーえいちじかん",
      category: "生理検査", description: "心房電位(A)からHis電位(H)までの伝導時間。房室結節の伝導時間を反映し、房室結節の伝導特性評価やジャンプ現象の判定に用いる。",
      related: "His束, HV時間, ジャンプ現象(AH jump), 房室結節(AV node)", memo: "",
    },
    {
      term: "HV時間", reading: "えいちぶいじかん",
      category: "生理検査", description: "His電位(H)から心室興奮開始(V)までの伝導時間。His-Purkinje系の伝導時間を反映する。",
      related: "His束, AH時間", memo: "",
    },
    {
      term: "Wenckebach周期長(AVN Wenckebach cycle length)", reading: "うぇんけばっはしゅうきちょう",
      category: "生理検査", description: "心房を漸増ペーシングした際に、房室結節でウェンケバッハ型の伝導遅延・ブロックが出現し始める最長の刺激周期長。房室結節の伝導能を評価する指標の一つ。",
      related: "房室結節(AV node), デクリメンタルペーシング/バーストペーシング, ERP(有効不応期)", memo: "",
    },
    {
      term: "ジャンプ現象(AH jump)", reading: "じゃんぷげんしょう",
      category: "生理検査", description: "期外刺激の連結期をわずかに短縮させた際に、AH時間が急激に(目安として50ms以上)延長する現象。速伝導路から遅伝導路への伝導の切り替わりを示し、二重房室結節伝導路(dual AV nodal physiology)の存在を示唆する。",
      related: "AH時間, AVNRT, エコー心拍(echo beat), Slow pathway(遅伝導路), Fast pathway(速伝導路)", memo: "",
    },
    {
      term: "エコー心拍(echo beat)", reading: "えこーしんぱく",
      category: "生理検査", description: "期外刺激後に、房室結節内の二重伝導路や副伝導路を介したリエントリーによって生じる単発の心拍。連続すればAVNRT/AVRTとして頻拍が持続する。",
      related: "ジャンプ現象(AH jump), AVNRT, プログラム電気刺激(PES)/期外刺激", memo: "",
    },
    {
      term: "順行性伝導/逆行性伝導", reading: "じゅんこうせい・ぎゃっこうせいでんどう",
      category: "生理検査", description: "心房から心室へ向かう伝導を順行性(antegrade)、心室から心房へ向かう伝導を逆行性(retrograde)と呼ぶ。副伝導路や房室結節がどちらの向きに伝導能を持つかは、頻拍の機序診断において重要。",
      related: "副伝導路(Accessory pathway), 房室結節(AV node), Para-Hisian pacing(パラヒス電位ペーシング), VA time(VA interval)", memo: "",
    },
    {
      term: "クライオアブレーション(cryoablation)", reading: "くらいおあぶれーしょん",
      category: "手技・検査", description: "カテーテル先端を冷却して組織を凝固させるアブレーション法。可逆的な冷却(cryomapping)で効果を確認してから本焼灼できる点が特徴で、房室ブロックのリスクを抑えたい遅伝導路アブレーションなどで選択されることがある。",
      related: "高周波アブレーション(RFカテーテルアブレーション), 完全房室ブロック(complete AV block), Slow pathway(遅伝導路)", memo: "",
    },
    {
      term: "高周波アブレーション(RFカテーテルアブレーション)", reading: "こうしゅうはあぶれーしょん",
      category: "手技・検査", description: "カテーテル先端から高周波(RF)電流を流し、抵抗熱により組織を熱凝固させるアブレーション法。PSVTアブレーションで広く用いられる標準的な方法。",
      related: "クライオアブレーション(cryoablation), インピーダンス(通電時)", memo: "",
    },
    {
      term: "インピーダンス(通電時)", reading: "いんぴーだんす",
      category: "手技・検査", description: "通電中のカテーテル先端-組織間の電気抵抗値。急激な低下・上昇は組織の炭化や血栓形成、パーフォレーションなどの異常を示唆することがあり、通電中モニタリングされる重要な指標。",
      related: "高周波アブレーション(RFカテーテルアブレーション), 心タンポナーデ(cardiac tamponade)", memo: "",
    },
    {
      term: "完全房室ブロック(complete AV block)", reading: "かんぜんぼうしつぶろっく",
      category: "合併症", description: "心房から心室への伝導が完全に途絶した状態。遅伝導路アブレーション(AVNRT)や中隔部の副伝導路アブレーションで、房室結節・His束周辺への熱障害により生じうる重篤な合併症で、恒久ペースメーカ植込みが必要になることがある。",
      related: "AVNRT, His束, Fast pathway(速伝導路), クライオアブレーション(cryoablation)", memo: "",
    },
    {
      term: "心タンポナーデ(cardiac tamponade)", reading: "しんたんぽなーで",
      category: "合併症", description: "心嚢内に血液などが急速に貯留し、心臓の拡張が妨げられて循環動態が悪化する状態。カテーテル操作や通電による心穿孔などで生じうる、緊急対応を要する合併症。",
      related: "インピーダンス(通電時), 卵円窩(Fossa ovalis), 血管迷走神経反射(vasovagal reaction)", memo: "",
    },
    {
      term: "血管迷走神経反射(vasovagal reaction)", reading: "けっかんめいそうしんけいはんしゃ",
      category: "合併症", description: "疼痛・不安・穿刺刺激などの誘因で迷走神経が興奮し、徐脈・血圧低下を来す反応。穿刺時や頻拍停止直後などに見られることがある。",
      related: "完全房室ブロック(complete AV block), 心タンポナーデ(cardiac tamponade)", memo: "",
    },
  ];
}

function seedTermsV3() {
  return [
    {
      term: "Orthodromic His capture", reading: "おーそどろみっくひすほかく",
      category: "手技・検査",
      description: "AVNRTのエントレインメント中に、His電位記録カテーテルが同時にとらえている局所心房電位が、頻拍自身の興奮伝播と同じ経路・向き(順方向≒orthodromic)で捕捉される現象。これが確認できると、頻拍回路とHis記録部位の間に「上部共通路(upper common pathway)」が存在しないことを示唆し、AVNRTの回路構造を推定する手がかりになる。なお、AVRTのエントレインメント中に心室からの逆行性伝導でHis電位自体が先に捕捉される現象は区別して「antidromic His capture」と呼ばれる。",
      related: "エントレインメント, His束, AVNRT, PPI(Post-Pacing Interval), Antidromic His capture, 順行性AVRT(Orthodromic AVRT)",
      memo: "出典: Circulation 1993「Orthodromic capture of the atrial electrogram during transient entrainment of AVNRT」、Wiley PACE/JCE「Antidromic His capture during entrainment of orthodromic AVRT」(2026年時点で要旨を確認)",
    },
  ];
}

function seedTermsV4() {
  return [
    {
      term: "Antidromic His capture", reading: "あんちどろみっくひすほかく",
      category: "手技・検査",
      description: "順行性AVRT(Orthodromic AVRT)を心室からのオーバードライブペーシングでエントレインメントする際に、His電位がペーシング部位からHis-Purkinje系を逆行性に(頻拍回路自体の伝導方向とは逆の\"antidromic\"な向きで)先に捕捉されてしまう現象。この場合H-H間隔がA-A間隔よりも先にペーシングへ同調してしまい、あたかもAVNRTのような所見を呈することがあるため、頻拍機序を誤診断しかねない診断上の落とし穴として知られる。",
      related: "Orthodromic His capture, エントレインメント, His束, 順行性AVRT(Orthodromic AVRT), AVNRT, PPI(Post-Pacing Interval)",
      memo: "出典: Nair et al., PACE 2010「Antidromic His Capture during Entrainment of Orthodromic AVRT」、Nair et al., J Cardiovasc Electrophysiol 2021「Antidromic His capture during ventricular entrainment of an orthodromic AVRT. What is the mechanism?」(2026年時点で要旨を確認)",
    },
  ];
}

function seedTermsV5() {
  return [
    {
      term: "Slow pathway(遅伝導路)", reading: "すろーぱすうぇい",
      category: "解剖",
      description: "房室結節の二重伝導路のうち、伝導速度は遅いが不応期が短い経路。Koch三角内でコンパクトAV結節よりも後下方、冠静脈洞口寄り・三尖弁輪に沿った領域を走行する。typical(スロー・ファスト型)AVNRTでは順行性の伝導路として頻拍回路の一部を担い、AVNRTのカテーテルアブレーションではこの遅伝導路を焼灼して頻拍を根治する。",
      related: "Fast pathway(速伝導路), AVNRT, Koch三角(Koch's triangle), ジャンプ現象(AH jump), 房室結節(AV node), スロー・ファスト型AVNRT(Typical)",
      memo: "",
    },
    {
      term: "Fast pathway(速伝導路)", reading: "ふぁすとぱすうぇい",
      category: "解剖",
      description: "房室結節の二重伝導路のうち、伝導速度は速いが不応期が長い経路。Koch三角の頂点付近、コンパクトAV結節・His束に近い前中隔寄りを走行する。typical AVNRTでは逆行性の伝導路として頻拍回路の一部を担う。His束・コンパクトAV結節に近接するため、この経路そのものを焼灼しようとすると完全房室ブロックのリスクが高く、通常アブレーションの標的にはしない。",
      related: "Slow pathway(遅伝導路), AVNRT, Koch三角(Koch's triangle), His束, 完全房室ブロック(complete AV block), 房室結節(AV node)",
      memo: "",
    },
  ];
}

function seedTermsV6() {
  return [
    {
      term: "房室結節(AV node)", reading: "ぼうしつけっせつ",
      category: "解剖",
      description: "右房下部、Koch三角の頂点付近に存在する特殊心筋の集塊。心房から心室への興奮伝導を仲介する通常唯一の生理的な伝導路で、伝導速度を意図的に遅らせるフィルターとして働く。しばしば内部にslow pathway・fast pathwayの二重伝導路を持ち、これがAVNRTの発生基盤となる。",
      related: "His束, Slow pathway(遅伝導路), Fast pathway(速伝導路), Koch三角(Koch's triangle), AVNRT, AH時間, Wenckebach周期長(AVN Wenckebach cycle length)",
      memo: "",
    },
    {
      term: "副伝導路(Accessory pathway)", reading: "ふくでんどうろ",
      category: "解剖",
      description: "正常の房室結節-His束系とは別に、心房と心室を直接つなぐ先天性の異常伝導路。代表的なものはKent束で、房室弁輪に沿ってどこにでも存在しうる。房室結節のような減衰伝導特性を持たず速く伝導するため、順行伝導能があれば洞調律時にデルタ波・PQ短縮(WPW症候群)を来し、AVRTの発生基盤となる。マハイム線維は例外的に房室結節様の減衰伝導特性を持つ副伝導路。",
      related: "WPW症候群, AVRT, 順行性AVRT(Orthodromic AVRT), 逆方向性AVRT(Antidromic AVRT), マハイム線維/マハイム型頻拍, 三尖弁輪(TA), 僧帽弁輪(MA), 顕性WPW症候群/潜在性WPW症候群",
      memo: "",
    },
  ];
}

function seedTermsV7() {
  return [
    {
      term: "High(フィルタ)/Low(フィルタ)", reading: "はい・ろーふぃるた",
      category: "機器",
      description: "ポリグラフ(生体アンプ)の周波数特性を決めるバンドパスフィルタの上限・下限カットオフ周波数の設定。「High」は通過帯域の上限周波数を指し、これより高い周波数成分を減衰させる(実質的にハイカット/ローパスとして働く)。「Low」は通過帯域の下限周波数を指し、これより低い周波数成分を減衰させる(実質的にローカット/ハイパスとして働く)。体表面心電図は基線動揺を抑えるため比較的低め(例: Low 0.05〜1Hz、High 40〜100Hz程度)、心内心電図やHis電位のような近距離電位は鋭い波形を見るため両方とも高め(例: Low 30〜50Hz、High 250〜500Hz程度)に設定することが多い。名称の「High/Low」は遮断される周波数帯そのものではなく通過帯域の上限・下限を表す点に注意。",
      related: "RMC-5000, His束, AH時間",
      memo: "出典: 心電図.com「フィルタとは？」ほか一般的なEPS用ポリグラフのフィルタ設定解説(2026年時点で内容確認)",
    },
  ];
}

function seedTermsV8() {
  return [
    {
      term: "RMC-5000", reading: "あーるえむしーごせん",
      category: "機器",
      description: "日本光電工業製の臨床用ポリグラフ(電気生理学的検査・心臓カテーテル検査用の多チャンネル生体情報記録装置)。心電図・観血/非観血血圧・心拍出量・SpO2などの基本測定に加え、導出18誘導心電図(synECi18)、心内心電図、呼吸、体温、CO2、BISなど多様な測定項目に対応する。同時圧・引抜き圧・FFR測定などカテーテル検査に特化した操作性、上下限アラーム/テクニカルアラーム、操作室と心カテ室を分けて操作できるリモートユニット機能などを備える。",
      related: "High(フィルタ)/Low(フィルタ)",
      memo: "出典: 日本光電 製品ページ「臨床用ポリグラフ RMC-5000」、日本光電ニュースリリース(2015年6月)(2026年時点で確認)",
    },
  ];
}

function withIds(termList) {
  return termList.map((t) => ({ id: uid(), memo: "", related: "", personalNote: "", image: "", ...t, updatedAt: nowStr() }));
}

// 追加用語のバッチ一覧。新しい用語を増やすときはここに関数を足す。
// CURRENT_TERMS_SEED_VERSIONを上げると、次回起動時に既存データへ
// (1)未登録の用語の追加 と (2)関連用語欄の追記マージ が行われる。
const SEED_BATCH_FNS = [seedTermsV1, seedTermsV2, seedTermsV3, seedTermsV4, seedTermsV5, seedTermsV6, seedTermsV7, seedTermsV8];

function mergeRelated(currentRelated, additionalRelated) {
  const list = (currentRelated || "").split(",").map((s) => s.trim()).filter(Boolean);
  const seen = new Set(list.map((s) => s.toLowerCase()));
  (additionalRelated || "").split(",").map((s) => s.trim()).filter(Boolean).forEach((r) => {
    if (!seen.has(r.toLowerCase())) {
      list.push(r);
      seen.add(r.toLowerCase());
    }
  });
  return list.join(", ");
}

// 既存データに、収録済みの全用語データを付き合わせる。
// 未登録の用語名は新規追加し、既存の用語は関連用語欄だけを追記マージする
// (解説・自分の理解メモ・出典など、ユーザーが書いた/編集した可能性のある項目は上書きしない)。
function mergeSeedTerms(existingTerms) {
  const byName = new Map(existingTerms.map((t) => [(t.term || "").trim().toLowerCase(), t]));
  const merged = [...existingTerms];
  SEED_BATCH_FNS.flatMap((fn) => fn()).forEach((seedTerm) => {
    const key = seedTerm.term.trim().toLowerCase();
    const existing = byName.get(key);
    if (!existing) {
      const created = withIds([seedTerm])[0];
      merged.push(created);
      byName.set(key, created);
    } else {
      existing.related = mergeRelated(existing.related, seedTerm.related);
    }
  });
  return merged;
}

// RMCメモの初期収録項目(トラブルシューティングのコツなど)。用語辞書と同じ考え方で、
// バッチを追加してCURRENT_RMC_SEED_VERSIONを上げると、既存データにも次回起動時に
// 自動で追記される(同じカテゴリ名・同じタイトルの項目が既にあれば追加しない)。
function rmcSeedItemsV1() {
  return [
    {
      category: "トラブルシューティング",
      title: "His電位が見にくい時の対応①計測手技の工夫",
      content: "・AとHisで基準点の考え方を分ける: Aは比較的鋭く安定しているのでキャリパーの片端をそこに固定し、His側は「見える中で一番再現性のある立ち上がり点」を許容範囲として割り切る、という運用も現実的です。\n・His電位が本当に不明瞭な拍は計測から除外: 無理に不明瞭な拍で判定せず、比較的明瞭に見えるHis電位が出た心拍で評価する方が誤差は小さくなります。\n・記録をフリーズして拡大観察: リアルタイムで判断しづらい場合、その場で止めて時間軸・振幅を最大にして見直す。",
    },
    {
      category: "トラブルシューティング",
      title: "His電位が見にくい時の対応②カテーテル位置・接触の対策",
      content: "・わずかな位置調整でHis電位の振幅が劇的に変わることが多い: 安定しない場合、数mm単位で前後・回転させてベストスポットを探し直す価値があります。\n・呼吸性の動きに合わせて基準を選ぶ: 吸気/呼気で位置がズレる場合、毎回同じ呼吸相(例: 呼気時)で計測すると再現性が上がることがあります。",
    },
    {
      category: "トラブルシューティング",
      title: "His電位が見にくい時の対応③表示・フィルタ面の対策",
      content: "・フィルタ帯域を調整: His記録用に高域を上げる(例: 100-500Hz程度)ことでシャープな成分が際立つことがあります。逆に低域フィルタが強すぎるとHis電位が減衰して見えにくくなるので、通常の心内電位設定(30-500Hz)と使い分ける。\n・ゲインを上げて拡大: His電位は振幅が小さいことが多いので、その電極だけゲインを上げて表示する。\n・バイポーラの極性・電極間隔を調整可能なら試す: 同じカテーテルでも隣接電極の組み合わせを変えるとHis電位がより明瞭に出ることがあります。",
    },
  ];
}

function rmcSeedItemsV2() {
  return [
    {
      category: "基本設定",
      title: "波形の立ち上がり点の定義①代表的な定義の仕方",
      content: "1. 基線からの逸脱点(deviation from baseline): 波形が基線(ノイズレベル)から明確に外れ始めた最初の点。最も直感的だが、ノイズが多いと「動き始め」の判定がぶれやすい。\n2. dV/dt最大点から逆算する方法: 立ち上がりが緩やかで「動き始め」がはっきりしない場合、最も急峻に変化している点(steepest slope)を先に見つけ、そこから接線を引いて基線との交点を求める方法。ノイズの影響を受けにくく、再現性が高いとされる。",
    },
    {
      category: "基本設定",
      title: "波形の立ち上がり点の定義②実務上の使い分け",
      content: "・ノイズが少なく波形がシャープなら、素直に「基線から動き始めた点」でOK。\n・ノイズが多い・立ち上がりがなだらかな波形では、視覚的な「動き始め」の判定はどうしてもブレるので、ピークやsteepest slope(急峻な傾きの点)を基準にした方が再現性は高くなる。\n・つまり定義としては合っていても、「動き始め」の視認性が低い波形ではその定義に固執せず、再現性の高い代替基準に切り替える判断が実務では重要。",
    },
  ];
}

const RMC_SEED_BATCH_FNS = [rmcSeedItemsV1, rmcSeedItemsV2];
const CURRENT_RMC_SEED_VERSION = 2;

// 既存カテゴリに一致する名前があれば項目を追記し(同名タイトルは重複させない)、
// なければ新しい大項目として追加する。
function mergeRmcSeedItems(categories) {
  RMC_SEED_BATCH_FNS.flatMap((fn) => fn()).forEach((seedItem) => {
    let cat = categories.find((c) => c.name === seedItem.category);
    if (!cat) {
      cat = { id: uid(), name: seedItem.category, items: [] };
      categories.push(cat);
    }
    const exists = cat.items.some((it) => (it.title || "").trim().toLowerCase() === seedItem.title.trim().toLowerCase());
    if (!exists) {
      cat.items.push({ id: uid(), title: seedItem.title, content: seedItem.content, updatedAt: nowStr() });
    }
  });
  return categories;
}

function defaultState() {
  return {
    termsSeedVersion: CURRENT_TERMS_SEED_VERSION,
    terms: withIds(SEED_BATCH_FNS.flatMap((fn) => fn())),
    rmcSeedVersion: CURRENT_RMC_SEED_VERSION,
    rmc: mergeRmcSeedItems([
      { id: uid(), name: "基本設定", items: [] },
      { id: uid(), name: "フィルタ設定", items: [] },
      { id: uid(), name: "記録条件", items: [] },
      { id: uid(), name: "カテーテル表示設定", items: [] },
      { id: uid(), name: "ペーシング設定", items: [] },
      { id: uid(), name: "トラブルシューティング", items: [] },
    ]),
    notes: [
      { id: uid(), name: "手技の流れ", items: [] },
      { id: uid(), name: "合併症・対応", items: [] },
      { id: uid(), name: "Tips・注意点", items: [] },
      { id: uid(), name: "ふりかえり", items: [] },
    ],
    scratch: [],
  };
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw);
    if (!parsed.terms || !parsed.rmc || !parsed.notes || !parsed.scratch) throw new Error("invalid");
    const seedVersion = parsed.termsSeedVersion || 1;
    if (seedVersion < CURRENT_TERMS_SEED_VERSION) {
      parsed.terms = mergeSeedTerms(parsed.terms);
      parsed.termsSeedVersion = CURRENT_TERMS_SEED_VERSION;
    }
    const rmcSeedVersion = parsed.rmcSeedVersion || 0;
    if (rmcSeedVersion < CURRENT_RMC_SEED_VERSION) {
      parsed.rmc = mergeRmcSeedItems(parsed.rmc);
      parsed.rmcSeedVersion = CURRENT_RMC_SEED_VERSION;
    }
    return parsed;
  } catch (e) {
    console.warn("failed to load state, using defaults", e);
    return defaultState();
  }
}

let state = loadState();

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  const statusEl = document.getElementById("data-status");
  if (statusEl) statusEl.textContent = `最終保存: ${nowStr()}`;
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 2200);
}

/* ---------- タブ切り替え ---------- */

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
}

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-btn");
  if (btn) switchTab(btn.dataset.tab);
});

/* ---------- ① 用語辞書 ---------- */

let termFormState = null; // { mode: 'add'|'edit', id? , prefill? }
let termImageDataUrl = null; // 編集中フォームの画像(data URL)。フォーム全体の再描画で消えないよう別管理

// 画像は端末のlocalStorageに保存されるため、容量を圧迫しないよう縮小・再圧縮してから保持する
function resizeImageFile(file, maxDim, quality) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error || new Error("read failed"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("image decode failed"));
      img.onload = () => {
        let { width, height } = img;
        if (width > maxDim || height > maxDim) {
          const scale = maxDim / Math.max(width, height);
          width = Math.round(width * scale);
          height = Math.round(height * scale);
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", quality));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

async function handleTermImageFile(event) {
  const file = event.target.files[0];
  if (!file) return;
  try {
    termImageDataUrl = await resizeImageFile(file, 1000, 0.82);
    updateTermImagePreview();
  } catch (e) {
    toast("画像の読み込みに失敗しました");
  }
}

function removeTermImage() {
  termImageDataUrl = null;
  updateTermImagePreview();
}

function updateTermImagePreview() {
  const wrap = document.getElementById("term-image-preview-wrap");
  const img = document.getElementById("term-image-preview");
  if (!wrap || !img) return;
  if (termImageDataUrl) {
    img.src = termImageDataUrl;
    wrap.hidden = false;
  } else {
    img.src = "";
    wrap.hidden = true;
  }
}

// 用語名の完全一致・前方一致を優先し、それ以外は他フィールドの一致順に並べる
// (PCI/EVTの検索アプリのように、探している語を上位に出す)
function matchRank(t, query) {
  const term = (t.term || "").toLowerCase();
  const reading = (t.reading || "").toLowerCase();
  if (term === query) return 0;
  if (term.startsWith(query)) return 1;
  if (reading.startsWith(query)) return 2;
  if (term.includes(query)) return 3;
  if (reading.includes(query)) return 4;
  if ((t.related || "").toLowerCase().includes(query)) return 5;
  if ((t.category || "").toLowerCase().includes(query)) return 6;
  if ((t.description || "").toLowerCase().includes(query)) return 7;
  if ((t.personalNote || "").toLowerCase().includes(query)) return 8;
  return 9;
}

function renderTerms() {
  const rawQuery = document.getElementById("term-search").value.trim();
  const query = rawQuery.toLowerCase();
  const list = document.getElementById("term-list");
  const items = [...state.terms]
    .filter((t) => {
      if (!query) return true;
      return [t.term, t.reading, t.description, t.related, t.category, t.personalNote]
        .some((f) => (f || "").toLowerCase().includes(query));
    })
    .sort((a, b) => {
      if (query) {
        const diff = matchRank(a, query) - matchRank(b, query);
        if (diff !== 0) return diff;
      }
      return (a.reading || a.term).localeCompare(b.reading || b.term, "ja");
    });

  if (items.length === 0) {
    if (query) {
      list.innerHTML = `
        <div class="empty-hint">
          <p>「${escapeHtml(rawQuery)}」に一致する用語は登録されていません。</p>
          <button class="btn btn-primary btn-small" onclick="openTermForm('add', null, '', '${escapeHtml(rawQuery)}')">「${escapeHtml(rawQuery)}」を新しい用語として追加</button>
        </div>`;
    } else {
      list.innerHTML = `<p class="empty-hint">まだ用語が登録されていません。「＋ 用語を追加」から登録してください。</p>`;
    }
  } else {
    list.innerHTML = items.map((t) => `
      <div class="card">
        <div class="card-head">
          <div>
            <p class="card-title">${highlightText(t.term, rawQuery)}</p>
            <p class="card-meta">${t.reading ? highlightText(t.reading, rawQuery) + " ・ " : ""}${t.category ? `<span class="card-badge">${escapeHtml(t.category)}</span>` : ""}更新: ${escapeHtml(t.updatedAt)}</p>
          </div>
          <div class="card-actions">
            <button class="btn btn-secondary btn-small" onclick="openTermForm('edit','${t.id}')">編集</button>
            <button class="btn btn-danger btn-small" onclick="deleteTerm('${t.id}')">削除</button>
          </div>
        </div>
        <div class="card-body">${highlightText(t.description, rawQuery)}</div>
        ${t.image ? `<img class="card-image" src="${t.image}" alt="${escapeHtml(t.term)}の解説画像">` : ""}
        ${t.related ? `<p class="card-meta">関連: ${highlightText(t.related, rawQuery)}</p>` : ""}
        ${t.memo ? `<p class="card-meta">出典・参考: ${escapeHtml(t.memo)}</p>` : ""}
        ${t.personalNote ? `<div class="personal-note"><span class="personal-note-label">📝 自分の理解メモ</span>${highlightText(t.personalNote, rawQuery)}</div>` : ""}
      </div>
    `).join("");
  }
  renderTermForm();
}

function openTermForm(mode, id, prefillDescription, prefillTerm) {
  termFormState = { mode, id, prefillDescription, prefillTerm };
  renderTermForm();
  document.getElementById("term-form-area").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeTermForm() {
  termFormState = null;
  termImageDataUrl = null;
  renderTermForm();
}

function renderTermForm() {
  const area = document.getElementById("term-form-area");
  if (!termFormState) { area.innerHTML = ""; return; }
  let data = { term: termFormState.prefillTerm || "", reading: "", category: "", description: termFormState.prefillDescription || "", related: "", memo: "", personalNote: "", image: "" };
  if (termFormState.mode === "edit") {
    const t = state.terms.find((x) => x.id === termFormState.id);
    if (t) data = { ...t };
  }
  termImageDataUrl = data.image || null;
  area.innerHTML = `
    <div class="form-box">
      <div class="form-row">
        <label>用語</label>
        <input type="text" id="f-term" value="${escapeHtml(data.term)}" placeholder="例: AVNRT">
      </div>
      <div class="form-row">
        <label>読み</label>
        <input type="text" id="f-reading" value="${escapeHtml(data.reading)}" placeholder="ひらがな読み">
      </div>
      <div class="form-row">
        <label>分類</label>
        <input type="text" id="f-category" value="${escapeHtml(data.category)}" placeholder="例: 不整脈 / 解剖 / 機器 / 手技">
      </div>
      <div class="form-row">
        <label>解説</label>
        <textarea id="f-description" rows="4" placeholder="意味・定義を記入">${escapeHtml(data.description)}</textarea>
      </div>
      <div class="form-row">
        <label>関連用語</label>
        <input type="text" id="f-related" value="${escapeHtml(data.related)}" placeholder="カンマ区切り">
      </div>
      <div class="form-row">
        <label>出典・参考</label>
        <input type="text" id="f-memo" value="${escapeHtml(data.memo)}" placeholder="調べた文献・サイトなど">
      </div>
      <div class="form-row">
        <label>📝 自分の理解メモ(任意)</label>
        <textarea id="f-personal-note" rows="3" placeholder="自分の言葉で言い換え・覚え方・実感したことなど">${escapeHtml(data.personalNote)}</textarea>
      </div>
      <div class="form-row">
        <label>解説画像(任意)</label>
        <input type="file" accept="image/*" id="f-image-input" onchange="handleTermImageFile(event)">
        <div id="term-image-preview-wrap" class="image-preview-wrap" ${termImageDataUrl ? "" : "hidden"}>
          <img id="term-image-preview" src="${termImageDataUrl ? termImageDataUrl : ""}" alt="プレビュー">
          <button type="button" class="btn btn-secondary btn-small" onclick="removeTermImage()">画像を削除</button>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" onclick="closeTermForm()">キャンセル</button>
        <button class="btn btn-primary" onclick="saveTermForm()">保存</button>
      </div>
    </div>
  `;
}

function saveTermForm() {
  const term = document.getElementById("f-term").value.trim();
  if (!term) { toast("用語名を入力してください"); return; }
  const payload = {
    term,
    reading: document.getElementById("f-reading").value.trim(),
    category: document.getElementById("f-category").value.trim(),
    description: document.getElementById("f-description").value.trim(),
    related: document.getElementById("f-related").value.trim(),
    memo: document.getElementById("f-memo").value.trim(),
    personalNote: document.getElementById("f-personal-note").value.trim(),
    image: termImageDataUrl || "",
    updatedAt: nowStr(),
  };
  if (termFormState.mode === "edit") {
    const t = state.terms.find((x) => x.id === termFormState.id);
    Object.assign(t, payload);
  } else {
    state.terms.push({ id: uid(), ...payload });
  }
  save();
  closeTermForm();
  renderTerms();
  toast("保存しました");
}

function deleteTerm(id) {
  if (!confirm("この用語を削除しますか？")) return;
  state.terms = state.terms.filter((t) => t.id !== id);
  save();
  renderTerms();
}

document.getElementById("term-add-btn").addEventListener("click", () => openTermForm("add"));
document.getElementById("term-search").addEventListener("input", renderTerms);

/* ---------- ② RMCメモ / ③ 自分用メモ (共通コンポーネント) ---------- */

const sections = {
  rmc: { containerId: "rmc-categories", label: "RMCメモ" },
  notes: { containerId: "notes-categories", label: "自分用メモ" },
};

let itemFormState = {}; // key(rmc/notes) -> {mode, categoryId, itemId}
let collapsedCategories = {}; // categoryId -> bool

function renderSection(key) {
  const cfg = sections[key];
  const container = document.getElementById(cfg.containerId);
  const categories = state[key];

  if (categories.length === 0) {
    container.innerHTML = `<p class="empty-hint">大項目がありません。「＋ 大項目を追加」から作成してください。</p>`;
    return;
  }

  container.innerHTML = categories.map((cat) => {
    const collapsed = !!collapsedCategories[cat.id];
    const form = itemFormState[key] && itemFormState[key].categoryId === cat.id ? renderItemFormHtml(key, cat) : "";
    const itemsHtml = cat.items.length
      ? cat.items.map((it) => `
        <div class="card">
          <div class="card-head">
            <div>
              <p class="card-title">${escapeHtml(it.title)}</p>
              <p class="card-meta">更新: ${escapeHtml(it.updatedAt)}</p>
            </div>
            <div class="card-actions">
              <button class="btn btn-secondary btn-small" onclick="openItemForm('${key}','${cat.id}','${it.id}')">編集</button>
              <button class="btn btn-danger btn-small" onclick="deleteItem('${key}','${cat.id}','${it.id}')">削除</button>
            </div>
          </div>
          <div class="card-body">${escapeHtml(it.content)}</div>
        </div>
      `).join("")
      : `<p class="empty-hint">まだ項目がありません。</p>`;

    return `
      <div class="category-block ${collapsed ? "collapsed" : ""}">
        <div class="category-header" onclick="toggleCategory('${cat.id}')">
          <h2>${escapeHtml(cat.name)}<span class="category-count">(${cat.items.length})</span></h2>
          <div class="category-actions" onclick="event.stopPropagation()">
            <button class="btn btn-secondary btn-small" onclick="openItemForm('${key}','${cat.id}')">＋ 項目追加</button>
            <button class="btn btn-secondary btn-small" onclick="renameCategory('${key}','${cat.id}')">名称変更</button>
            <button class="btn btn-danger btn-small" onclick="deleteCategory('${key}','${cat.id}')">削除</button>
          </div>
        </div>
        <div class="category-body">
          ${form}
          ${itemsHtml}
        </div>
      </div>
    `;
  }).join("");
}

function renderItemFormHtml(key, currentCat) {
  const st = itemFormState[key];
  let data = { title: "", content: "" };
  if (st.mode === "edit") {
    const it = currentCat.items.find((i) => i.id === st.itemId);
    if (it) data = { ...it };
  }
  const categoryOptions = state[key].map((c) => `<option value="${c.id}" ${c.id === currentCat.id ? "selected" : ""}>${escapeHtml(c.name)}</option>`).join("");
  return `
    <div class="form-box">
      <div class="form-row">
        <label>タイトル</label>
        <input type="text" id="if-title-${key}" value="${escapeHtml(data.title)}" placeholder="例: フィルタ設定の基本値">
      </div>
      <div class="form-row">
        <label>内容</label>
        <textarea id="if-content-${key}" rows="4" placeholder="設定値・手順・注意点など">${escapeHtml(data.content)}</textarea>
      </div>
      <div class="form-row">
        <label>大項目(移動する場合はここで変更)</label>
        <select id="if-category-${key}">${categoryOptions}</select>
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" onclick="closeItemForm('${key}')">キャンセル</button>
        <button class="btn btn-primary" onclick="saveItemForm('${key}','${currentCat.id}')">保存</button>
      </div>
    </div>
  `;
}

function toggleCategory(id) {
  collapsedCategories[id] = !collapsedCategories[id];
  renderAll();
}

function openItemForm(key, categoryId, itemId) {
  itemFormState[key] = { mode: itemId ? "edit" : "add", categoryId, itemId };
  renderSection(key);
}

function closeItemForm(key) {
  delete itemFormState[key];
  renderSection(key);
}

function saveItemForm(key, formCategoryId) {
  const st = itemFormState[key];
  const title = document.getElementById(`if-title-${key}`).value.trim();
  const content = document.getElementById(`if-content-${key}`).value.trim();
  const targetCategoryId = document.getElementById(`if-category-${key}`).value;
  if (!title) { toast("タイトルを入力してください"); return; }

  const sourceCat = state[key].find((c) => c.id === formCategoryId);
  if (st.mode === "edit") {
    const idx = sourceCat.items.findIndex((i) => i.id === st.itemId);
    const item = sourceCat.items[idx];
    item.title = title; item.content = content; item.updatedAt = nowStr();
    if (targetCategoryId !== formCategoryId) {
      sourceCat.items.splice(idx, 1);
      state[key].find((c) => c.id === targetCategoryId).items.push(item);
    }
  } else {
    const targetCat = state[key].find((c) => c.id === targetCategoryId);
    targetCat.items.push({ id: uid(), title, content, updatedAt: nowStr() });
  }
  save();
  closeItemForm(key);
  toast("保存しました");
}

function deleteItem(key, categoryId, itemId) {
  if (!confirm("この項目を削除しますか？")) return;
  const cat = state[key].find((c) => c.id === categoryId);
  cat.items = cat.items.filter((i) => i.id !== itemId);
  save();
  renderSection(key);
}

function addCategory(key) {
  const name = prompt("新しい大項目の名前を入力してください");
  if (!name || !name.trim()) return;
  state[key].push({ id: uid(), name: name.trim(), items: [] });
  save();
  renderSection(key);
}

function renameCategory(key, id) {
  const cat = state[key].find((c) => c.id === id);
  const name = prompt("大項目の名前を変更", cat.name);
  if (!name || !name.trim()) return;
  cat.name = name.trim();
  save();
  renderSection(key);
}

function deleteCategory(key, id) {
  const cat = state[key].find((c) => c.id === id);
  if (cat.items.length > 0) {
    if (!confirm(`「${cat.name}」には${cat.items.length}件の項目があります。中の項目もすべて削除されますが、よろしいですか？`)) return;
  } else if (!confirm(`「${cat.name}」を削除しますか？`)) {
    return;
  }
  state[key] = state[key].filter((c) => c.id !== id);
  save();
  renderSection(key);
}

document.getElementById("rmc-add-category-btn").addEventListener("click", () => addCategory("rmc"));
document.getElementById("notes-add-category-btn").addEventListener("click", () => addCategory("notes"));

/* ---------- 気になるメモ ---------- */

function renderScratch() {
  const list = document.getElementById("scratch-list");
  if (state.scratch.length === 0) {
    list.innerHTML = `<p class="empty-hint">気になることが登録されていません。</p>`;
    return;
  }
  const noteOptions = state.notes.map((c) => `<option value="notes:${c.id}">自分用メモ / ${escapeHtml(c.name)}</option>`).join("");
  const rmcOptions = state.rmc.map((c) => `<option value="rmc:${c.id}">RMCメモ / ${escapeHtml(c.name)}</option>`).join("");

  list.innerHTML = [...state.scratch].reverse().map((s) => `
    <div class="card">
      <div class="card-head">
        <div>
          <p class="card-meta"><span class="scratch-status open">未解決</span>${escapeHtml(s.createdAt)}</p>
        </div>
        <div class="card-actions">
          <button class="btn btn-secondary btn-small" onclick="copyScratchText('${s.id}')">コピー</button>
          <button class="btn btn-danger btn-small" onclick="deleteScratch('${s.id}')">削除</button>
        </div>
      </div>
      <div class="card-body">${escapeHtml(s.text)}</div>
      <div class="form-row" style="margin-top:0.6rem;">
        <label>解決したら保存先を選んで記録</label>
        <select id="scratch-target-${s.id}">
          <option value="">-- 保存先を選択 --</option>
          <option value="term">用語辞書に用語として追加</option>
          <optgroup label="自分用メモ">${noteOptions}</optgroup>
          <optgroup label="RMCメモ">${rmcOptions}</optgroup>
        </select>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary btn-small" onclick="resolveScratch('${s.id}')">記録する</button>
      </div>
    </div>
  `).join("");
}

document.getElementById("scratch-add-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("scratch-input");
  const text = input.value.trim();
  if (!text) return;
  state.scratch.push({ id: uid(), text, createdAt: nowStr() });
  input.value = "";
  save();
  renderScratch();
});

function deleteScratch(id) {
  state.scratch = state.scratch.filter((s) => s.id !== id);
  save();
  renderScratch();
}

// クリップボードにコピーして、調べてほしい内容をチャットへ貼り付けやすくする
function copyScratchText(id) {
  const s = state.scratch.find((x) => x.id === id);
  if (!s) return;
  const text = s.text;
  const done = () => toast("コピーしました。チャットに貼り付けてください");
  const fail = () => toast("コピーに失敗しました。手動で選択してコピーしてください");
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, fail);
  } else {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      done();
    } catch (e) {
      fail();
    }
  }
}

function resolveScratch(id) {
  const sel = document.getElementById(`scratch-target-${id}`);
  const value = sel.value;
  if (!value) { toast("保存先を選択してください"); return; }
  const s = state.scratch.find((x) => x.id === id);

  if (value === "term") {
    state.scratch = state.scratch.filter((x) => x.id !== id);
    save();
    switchTab("terms");
    openTermForm("add", null, s.text);
    renderTerms();
    toast("用語追加フォームに内容を入れました。用語名を入力して保存してください");
    return;
  }

  const [key, categoryId] = value.split(":");
  const cat = state[key].find((c) => c.id === categoryId);
  const firstLine = s.text.split("\n")[0].slice(0, 40) || "気になるメモより";
  cat.items.push({ id: uid(), title: firstLine, content: s.text, updatedAt: nowStr() });
  state.scratch = state.scratch.filter((x) => x.id !== id);
  save();
  switchTab(key);
  renderAll();
  toast(`「${cat.name}」に記録しました`);
}

/* ---------- データ管理 ---------- */

document.getElementById("export-btn").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  a.href = url;
  a.download = `psvt-ablation-data-${ts}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("import-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(reader.result);
      if (!parsed.terms || !parsed.rmc || !parsed.notes || !parsed.scratch) throw new Error("形式が正しくありません");
      if (!confirm("現在のデータを上書きしてインポートします。よろしいですか？")) return;
      state = parsed;
      save();
      renderAll();
      toast("インポートしました");
    } catch (err) {
      alert("インポートに失敗しました: " + err.message);
    }
  };
  reader.readAsText(file);
  e.target.value = "";
});

document.getElementById("reset-btn").addEventListener("click", () => {
  if (!confirm("すべてのデータを初期状態に戻します。元に戻せません。よろしいですか？")) return;
  state = defaultState();
  save();
  renderAll();
  toast("初期データにリセットしました");
});

/* ---------- 初期描画 ---------- */

function renderAll() {
  renderTerms();
  renderSection("rmc");
  renderSection("notes");
  renderScratch();
}

renderAll();
save();
