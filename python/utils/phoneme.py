"""
English to Katakana phonetic converter.
Converts English text to katakana approximation for VOICEVOX synthesis.
Uses a phonetic mapping approach — no external dependencies required.

Strategy:
1. Check whole-word dictionary first (most accurate)
2. Apply suffix rules (e.g., -tion -> ション, -ing -> イング)
3. Fall back to character-by-character phoneme mapping
"""

import re
import logging

logger = logging.getLogger('stts.utils.phoneme')

# ============================================================
# Common English words -> Katakana (highest accuracy)
# ============================================================
WORD_DICT = {
    # Greetings & basics
    'hello': 'ハロー', 'hi': 'ハイ', 'hey': 'ヘイ', 'bye': 'バイ',
    'goodbye': 'グッドバイ', 'welcome': 'ウェルカム', 'morning': 'モーニング',
    'evening': 'イーブニング', 'afternoon': 'アフタヌーン',

    # Pronouns
    'i': 'アイ', 'you': 'ユー', 'your': 'ユア', 'yours': 'ユアズ',
    'my': 'マイ', 'mine': 'マイン', 'me': 'ミー', 'myself': 'マイセルフ',
    'he': 'ヒー', 'him': 'ヒム', 'his': 'ヒズ', 'himself': 'ヒムセルフ',
    'she': 'シー', 'her': 'ハー', 'hers': 'ハーズ', 'herself': 'ハーセルフ',
    'they': 'ゼイ', 'them': 'ゼム', 'their': 'ゼア', 'theirs': 'ゼアズ',
    'we': 'ウィー', 'us': 'アス', 'our': 'アワー', 'ours': 'アワーズ',
    'it': 'イット', 'its': 'イッツ', 'itself': 'イットセルフ',
    'who': 'フー', 'whom': 'フーム', 'whose': 'フーズ',
    'someone': 'サムワン', 'anyone': 'エニワン', 'everyone': 'エブリワン',
    'nobody': 'ノーバディ', 'somebody': 'サムバディ', 'anybody': 'エニバディ',
    'everybody': 'エブリバディ',

    # Articles & determiners
    'the': 'ザ', 'a': 'ア', 'an': 'アン',
    'this': 'ディス', 'that': 'ザット', 'these': 'ジーズ', 'those': 'ゾーズ',
    'some': 'サム', 'any': 'エニー', 'many': 'メニー', 'much': 'マッチ',
    'all': 'オール', 'each': 'イーチ', 'every': 'エブリー',
    'both': 'ボース', 'few': 'フュー', 'several': 'セベラル',
    'other': 'アザー', 'another': 'アナザー',

    # Be verbs
    'is': 'イズ', 'am': 'アム', 'are': 'アー',
    'was': 'ワズ', 'were': 'ワー', 'be': 'ビー', 'been': 'ビーン',
    'being': 'ビーイング',

    # Common verbs
    'have': 'ハヴ', 'has': 'ハズ', 'had': 'ハド', 'having': 'ハヴィング',
    'do': 'ドゥー', 'does': 'ダズ', 'did': 'ディド', 'doing': 'ドゥーイング',
    'done': 'ダン',
    'will': 'ウィル', 'would': 'ウッド', 'shall': 'シャル',
    'can': 'キャン', 'could': 'クッド',
    'should': 'シュッド', 'may': 'メイ', 'might': 'マイト', 'must': 'マスト',
    'go': 'ゴー', 'going': 'ゴーイング', 'gone': 'ゴーン', 'went': 'ウェント',
    'come': 'カム', 'coming': 'カミング', 'came': 'ケイム',
    'get': 'ゲット', 'getting': 'ゲッティング', 'got': 'ガット', 'gotten': 'ガットン',
    'make': 'メイク', 'making': 'メイキング', 'made': 'メイド',
    'take': 'テイク', 'taking': 'テイキング', 'took': 'トゥック', 'taken': 'テイクン',
    'give': 'ギヴ', 'giving': 'ギヴィング', 'gave': 'ゲイヴ', 'given': 'ギヴン',
    'say': 'セイ', 'saying': 'セイイング', 'said': 'セド',
    'tell': 'テル', 'telling': 'テリング', 'told': 'トールド',
    'see': 'シー', 'seeing': 'シーイング', 'saw': 'ソー', 'seen': 'シーン',
    'know': 'ノウ', 'knowing': 'ノウイング', 'knew': 'ニュー', 'known': 'ノウン',
    'think': 'シンク', 'thinking': 'シンキング', 'thought': 'ソート',
    'want': 'ウォント', 'wanting': 'ウォンティング',
    'need': 'ニード', 'needing': 'ニーディング',
    'try': 'トライ', 'trying': 'トライイング', 'tried': 'トライド',
    'feel': 'フィール', 'feeling': 'フィーリング', 'felt': 'フェルト',
    'look': 'ルック', 'looking': 'ルッキング', 'looked': 'ルックト',
    'find': 'ファインド', 'finding': 'ファインディング', 'found': 'ファウンド',
    'put': 'プット', 'putting': 'プッティング',
    'keep': 'キープ', 'keeping': 'キーピング', 'kept': 'ケプト',
    'let': 'レット', 'letting': 'レッティング',
    'begin': 'ビギン', 'beginning': 'ビギニング', 'began': 'ビガン',
    'seem': 'シーム', 'show': 'ショー', 'shown': 'ショウン', 'showed': 'ショウド',
    'hear': 'ヒア', 'heard': 'ハード', 'listen': 'リッスン',
    'turn': 'ターン', 'leave': 'リーヴ', 'left': 'レフト',
    'call': 'コール', 'called': 'コールド',
    'ask': 'アスク', 'asked': 'アスクト',
    'move': 'ムーヴ', 'moving': 'ムーヴィング', 'moved': 'ムーヴド',
    'live': 'リヴ', 'living': 'リヴィング',
    'believe': 'ビリーヴ', 'happen': 'ハプン',
    'run': 'ラン', 'running': 'ランニング',
    'walk': 'ウォーク', 'walking': 'ウォーキング',
    'talk': 'トーク', 'talking': 'トーキング',
    'read': 'リード', 'reading': 'リーディング',
    'write': 'ライト', 'writing': 'ライティング', 'wrote': 'ロウト', 'written': 'リトゥン',
    'learn': 'ラーン', 'learning': 'ラーニング',
    'play': 'プレイ', 'playing': 'プレイング',
    'work': 'ワーク', 'working': 'ワーキング',
    'use': 'ユーズ', 'using': 'ユージング', 'used': 'ユーズド',
    'help': 'ヘルプ', 'helping': 'ヘルピング',
    'love': 'ラヴ', 'like': 'ライク', 'hate': 'ヘイト',
    'eat': 'イート', 'eating': 'イーティング',
    'drink': 'ドリンク', 'drinking': 'ドリンキング',
    'sleep': 'スリープ', 'sleeping': 'スリーピング',
    'wait': 'ウェイト', 'waiting': 'ウェイティング',
    'watch': 'ウォッチ', 'watching': 'ウォッチング',
    'buy': 'バイ', 'bought': 'ボート',
    'pay': 'ペイ', 'paid': 'ペイド',
    'send': 'センド', 'sent': 'セント',
    'sit': 'シット', 'sitting': 'シッティング',
    'stand': 'スタンド', 'standing': 'スタンディング',
    'speak': 'スピーク', 'speaking': 'スピーキング', 'spoke': 'スポーク',
    'change': 'チェンジ', 'changing': 'チェンジング',
    'follow': 'フォロー', 'following': 'フォローイング',
    'stop': 'ストップ', 'start': 'スタート', 'open': 'オープン', 'close': 'クローズ',

    # Contractions
    "don't": 'ドント', "doesn't": 'ダズント', "didn't": 'ディドゥント',
    "can't": 'キャント', "couldn't": 'クドゥント', "won't": 'ウォント',
    "wouldn't": 'ウドゥント', "shouldn't": 'シュドゥント',
    "isn't": 'イズント', "aren't": 'アーント', "wasn't": 'ワズント',
    "weren't": 'ワーント', "hasn't": 'ハズント', "haven't": 'ハヴント',
    "hadn't": 'ハドゥント',
    "i'm": 'アイム', "i've": 'アイヴ', "i'll": 'アイル', "i'd": 'アイド',
    "you're": 'ユーアー', "you've": 'ユーヴ', "you'll": 'ユール', "you'd": 'ユード',
    "he's": 'ヒーズ', "he'll": 'ヒール', "he'd": 'ヒード',
    "she's": 'シーズ', "she'll": 'シール', "she'd": 'シード',
    "it's": 'イッツ', "it'll": 'イットゥル',
    "we're": 'ウィーアー', "we've": 'ウィーヴ', "we'll": 'ウィール',
    "they're": 'ゼイアー', "they've": 'ゼイヴ', "they'll": 'ゼイル',
    "that's": 'ザッツ', "there's": 'ゼアズ', "here's": 'ヒアズ',
    "what's": 'ワッツ', "who's": 'フーズ', "let's": 'レッツ',

    # Conjunctions & prepositions
    'and': 'アンド', 'or': 'オア', 'but': 'バット', 'so': 'ソー',
    'because': 'ビコーズ', 'since': 'シンス', 'while': 'ワイル',
    'although': 'オールゾー', 'though': 'ゾー', 'unless': 'アンレス',
    'until': 'アンティル', 'before': 'ビフォー', 'after': 'アフター',
    'if': 'イフ', 'when': 'ウェン', 'where': 'ウェア',
    'for': 'フォー', 'with': 'ウィズ', 'without': 'ウィズアウト',
    'from': 'フロム', 'to': 'トゥー', 'into': 'イントゥー',
    'about': 'アバウト', 'between': 'ビトゥイーン',
    'through': 'スルー', 'during': 'デュアリング',
    'against': 'アゲインスト', 'toward': 'トワード', 'towards': 'トワーズ',
    'around': 'アラウンド', 'above': 'アバヴ', 'below': 'ビロウ',
    'under': 'アンダー', 'behind': 'ビハインド', 'beside': 'ビサイド',
    'along': 'アロング', 'across': 'アクロス',

    # Question words
    'what': 'ワット', 'which': 'ウィッチ', 'how': 'ハウ', 'why': 'ワイ',

    # Adverbs
    'yes': 'イエス', 'no': 'ノー', 'not': 'ノット',
    'just': 'ジャスト', 'very': 'ベリー', 'really': 'リアリー',
    'also': 'オールソー', 'too': 'トゥー', 'only': 'オンリー',
    'well': 'ウェル', 'even': 'イーブン', 'still': 'スティル',
    'already': 'オールレディ', 'never': 'ネバー', 'always': 'オールウェイズ',
    'sometimes': 'サムタイムズ', 'often': 'オフン', 'usually': 'ユージュアリー',
    'again': 'アゲイン', 'once': 'ワンス', 'twice': 'トワイス',
    'now': 'ナウ', 'then': 'ゼン', 'here': 'ヒア', 'there': 'ゼア',
    'today': 'トゥデイ', 'tomorrow': 'トゥモロー', 'yesterday': 'イエスタデイ',
    'maybe': 'メイビー', 'perhaps': 'パハプス',
    'together': 'トゥゲザー', 'away': 'アウェイ', 'ago': 'アゴー',
    'almost': 'オールモスト', 'enough': 'イナフ', 'quite': 'クワイト',
    'pretty': 'プリティ', 'especially': 'エスペシャリー',
    'actually': 'アクチュアリー', 'exactly': 'イグザクトリー',
    'probably': 'プロバブリー', 'definitely': 'デフィニトリー',
    'certainly': 'サートゥンリー', 'absolutely': 'アブソルートリー',

    # Adjectives
    'good': 'グッド', 'great': 'グレート', 'nice': 'ナイス',
    'bad': 'バッド', 'better': 'ベター', 'best': 'ベスト',
    'worse': 'ワース', 'worst': 'ワースト',
    'happy': 'ハッピー', 'sad': 'サッド', 'angry': 'アングリー',
    'beautiful': 'ビューティフル', 'cute': 'キュート', 'cool': 'クール',
    'hot': 'ホット', 'cold': 'コールド', 'warm': 'ウォーム',
    'big': 'ビッグ', 'small': 'スモール', 'large': 'ラージ',
    'little': 'リトル', 'long': 'ロング', 'short': 'ショート',
    'tall': 'トール', 'high': 'ハイ', 'low': 'ロー',
    'fast': 'ファースト', 'slow': 'スロー', 'quick': 'クイック',
    'new': 'ニュー', 'old': 'オールド', 'young': 'ヤング',
    'easy': 'イージー', 'hard': 'ハード', 'difficult': 'ディフィカルト',
    'simple': 'シンプル', 'important': 'インポータント',
    'different': 'ディファレント', 'same': 'セイム',
    'true': 'トゥルー', 'false': 'フォールス',
    'strong': 'ストロング', 'weak': 'ウィーク',
    'full': 'フル', 'empty': 'エンプティ',
    'dark': 'ダーク', 'light': 'ライト', 'bright': 'ブライト',
    'white': 'ホワイト', 'black': 'ブラック', 'red': 'レッド',
    'blue': 'ブルー', 'green': 'グリーン', 'yellow': 'イエロー',
    'purple': 'パープル', 'pink': 'ピンク', 'orange': 'オレンジ',
    'free': 'フリー', 'ready': 'レディ', 'sure': 'シュア',
    'wrong': 'ロング', 'right': 'ライト',
    'safe': 'セーフ', 'dangerous': 'デインジャラス',
    'possible': 'ポッシブル', 'impossible': 'インポッシブル',
    'special': 'スペシャル', 'real': 'リアル',
    'clear': 'クリア', 'perfect': 'パーフェクト',
    'strange': 'ストレンジ', 'crazy': 'クレイジー',
    'funny': 'ファニー', 'serious': 'シリアス',
    'favorite': 'フェイバリット', 'favourite': 'フェイバリット',
    'amazing': 'アメイジング', 'awesome': 'オーサム',
    'terrible': 'テリブル', 'wonderful': 'ワンダフル',
    'interesting': 'インタレスティング', 'boring': 'ボーリング',
    'tired': 'タイアド', 'hungry': 'ハングリー', 'thirsty': 'サースティ',

    # Numbers
    'zero': 'ゼロ', 'one': 'ワン', 'two': 'トゥー', 'three': 'スリー',
    'four': 'フォー', 'five': 'ファイヴ', 'six': 'シックス',
    'seven': 'セブン', 'eight': 'エイト', 'nine': 'ナイン', 'ten': 'テン',
    'eleven': 'イレブン', 'twelve': 'トゥエルヴ',
    'thirteen': 'サーティーン', 'fourteen': 'フォーティーン',
    'fifteen': 'フィフティーン', 'sixteen': 'シックスティーン',
    'seventeen': 'セブンティーン', 'eighteen': 'エイティーン',
    'nineteen': 'ナインティーン', 'twenty': 'トゥエンティ',
    'thirty': 'サーティ', 'forty': 'フォーティ', 'fifty': 'フィフティ',
    'hundred': 'ハンドレッド', 'thousand': 'サウザンド', 'million': 'ミリオン',

    # Nouns — people & body
    'man': 'マン', 'woman': 'ウーマン', 'child': 'チャイルド',
    'children': 'チルドレン', 'boy': 'ボーイ', 'girl': 'ガール',
    'baby': 'ベイビー', 'friend': 'フレンド', 'family': 'ファミリー',
    'mother': 'マザー', 'father': 'ファザー', 'brother': 'ブラザー',
    'sister': 'シスター', 'parent': 'ペアレント',
    'people': 'ピープル', 'person': 'パーソン',
    'hand': 'ハンド', 'head': 'ヘッド', 'face': 'フェイス',
    'eye': 'アイ', 'eyes': 'アイズ', 'heart': 'ハート',
    'voice': 'ヴォイス', 'body': 'ボディ',

    # Nouns — places & things
    'world': 'ワールド', 'country': 'カントリー', 'city': 'シティ',
    'place': 'プレイス', 'home': 'ホーム', 'house': 'ハウス',
    'room': 'ルーム', 'door': 'ドア', 'window': 'ウィンドウ',
    'school': 'スクール', 'office': 'オフィス', 'store': 'ストア',
    'water': 'ウォーター', 'food': 'フード', 'coffee': 'コーヒー',
    'money': 'マネー', 'car': 'カー', 'phone': 'フォン',
    'book': 'ブック', 'table': 'テーブル', 'chair': 'チェア',
    'life': 'ライフ', 'death': 'デス', 'power': 'パワー',
    'time': 'タイム', 'day': 'デイ', 'night': 'ナイト',
    'week': 'ウィーク', 'month': 'マンス', 'year': 'イヤー',
    'way': 'ウェイ', 'side': 'サイド', 'part': 'パート',
    'story': 'ストーリー', 'problem': 'プロブレム',
    'idea': 'アイディア', 'reason': 'リーズン',
    'thing': 'シング', 'word': 'ワード',
    'music': 'ミュージック', 'game': 'ゲーム', 'movie': 'ムービー',
    'name': 'ネーム', 'number': 'ナンバー',
    'point': 'ポイント', 'group': 'グループ', 'team': 'チーム',

    # Nouns — nature
    'sun': 'サン', 'moon': 'ムーン', 'star': 'スター', 'sky': 'スカイ',
    'fire': 'ファイア', 'air': 'エア', 'earth': 'アース',
    'flower': 'フラワー', 'tree': 'トゥリー',
    'rain': 'レイン', 'snow': 'スノー', 'wind': 'ウィンド',

    # Tech & internet
    'computer': 'コンピューター', 'internet': 'インターネット',
    'system': 'システム', 'server': 'サーバー', 'network': 'ネットワーク',
    'message': 'メッセージ', 'data': 'データ', 'file': 'ファイル',
    'app': 'アプリ', 'application': 'アプリケーション',
    'error': 'エラー', 'user': 'ユーザー', 'password': 'パスワード',
    'website': 'ウェブサイト', 'email': 'イーメール',
    'online': 'オンライン', 'offline': 'オフライン',
    'download': 'ダウンロード', 'upload': 'アップロード',
    'search': 'サーチ', 'click': 'クリック',
    'software': 'ソフトウェア', 'hardware': 'ハードウェア',
    'program': 'プログラム', 'screen': 'スクリーン',
    'video': 'ビデオ', 'audio': 'オーディオ',
    'camera': 'カメラ', 'image': 'イメージ',
    'button': 'ボタン', 'menu': 'メニュー',
    'channel': 'チャンネル', 'stream': 'ストリーム',
    'avatar': 'アバター', 'profile': 'プロファイル',
    'setting': 'セッティング', 'settings': 'セッティングズ',
    'update': 'アップデート', 'version': 'バージョン',
    'voice': 'ヴォイス', 'microphone': 'マイクロフォン',
    'speaker': 'スピーカー', 'headset': 'ヘッドセット',

    # VRChat / gaming
    'vrchat': 'ヴイアールチャット', 'virtual': 'バーチャル',
    'reality': 'リアリティ', 'character': 'キャラクター',
    'player': 'プレイヤー', 'level': 'レベル', 'item': 'アイテム',
    'world': 'ワールド', 'lobby': 'ロビー', 'chat': 'チャット',
    'anime': 'アニメ', 'manga': 'マンガ',

    # Expressions
    'thank': 'サンク', 'thanks': 'サンクス',
    'please': 'プリーズ', 'sorry': 'ソーリー', 'excuse': 'エクスキューズ',
    'okay': 'オーケー', 'ok': 'オーケー', 'sure': 'シュア',
    'yeah': 'イェア', 'yep': 'イェプ', 'nope': 'ノープ',
    'oh': 'オー', 'wow': 'ワウ', 'nice': 'ナイス',
    'lol': 'エルオーエル', 'haha': 'ハハ',

    # Common misspellings / casual
    'gonna': 'ゴナ', 'wanna': 'ワナ', 'gotta': 'ガッタ',
    'kinda': 'カインダ', 'sorta': 'ソータ',
    'dunno': 'ダノ', 'lemme': 'レミー', 'gimme': 'ギミー',

    # More common words
    'something': 'サムシング', 'anything': 'エニシング',
    'everything': 'エブリシング', 'nothing': 'ナッシング',
    'somewhere': 'サムウェア', 'anywhere': 'エニウェア',
    'everywhere': 'エブリウェア', 'nowhere': 'ノーウェア',
    'however': 'ハウエバー', 'whatever': 'ワットエバー',
    'whenever': 'ウェンエバー', 'wherever': 'ウェアエバー',
    'more': 'モア', 'most': 'モースト', 'less': 'レス', 'least': 'リースト',
    'over': 'オーバー', 'down': 'ダウン', 'up': 'アップ',
    'back': 'バック', 'off': 'オフ', 'out': 'アウト',
    'own': 'オウン', 'same': 'セイム',
    'first': 'ファースト', 'second': 'セカンド', 'third': 'サード',
    'last': 'ラスト', 'next': 'ネクスト',
    'able': 'エイブル', 'kind': 'カインド',
    'example': 'イグザンプル', 'question': 'クエスチョン', 'answer': 'アンサー',
    'minute': 'ミニット', 'hour': 'アワー',
    'English': 'イングリッシュ', 'Japanese': 'ジャパニーズ',
    'language': 'ランゲージ', 'translate': 'トランスレイト',
    'speech': 'スピーチ', 'text': 'テキスト',
}

# ============================================================
# Suffix rules — applied BEFORE character-by-character conversion
# Order matters: longer suffixes first
# ============================================================
SUFFIX_RULES = [
    # -tion / -sion / -ssion
    ('tion', 'ション'),
    ('sion', 'ジョン'),
    ('ssion', 'ッション'),

    # -ight patterns
    ('ight', 'アイト'),

    # -ould patterns
    ('ould', 'ッド'),

    # -ough patterns
    ('ough', 'オー'),

    # -ness
    ('ness', 'ネス'),

    # -ment
    ('ment', 'メント'),

    # -ble
    ('able', 'エイブル'),
    ('ible', 'イブル'),

    # -ful / -less
    ('ful', 'フル'),
    ('less', 'レス'),

    # -ly (adverbs)
    ('ly', 'リー'),

    # -ing
    ('ing', 'イング'),

    # -er / -or (agent nouns)
    ('ture', 'チャー'),
    ('ure', 'ュア'),

    # -ous
    ('ious', 'イアス'),
    ('eous', 'イアス'),
    ('ous', 'アス'),

    # -ive
    ('tive', 'ティヴ'),
    ('sive', 'シヴ'),

    # -ence / -ance
    ('ence', 'エンス'),
    ('ance', 'アンス'),

    # -ity
    ('ity', 'イティ'),

    # -ism
    ('ism', 'イズム'),

    # -ist
    ('ist', 'イスト'),

    # -ed (past tense, pronounced as ド/ト/イド depending on context)
    ('ted', 'テッド'),
    ('ded', 'デッド'),
    ('sed', 'ズド'),
    ('ced', 'スト'),
    ('ked', 'クト'),
    ('ped', 'プト'),
    ('ed', 'ド'),

    # -es / -s (plural)
    ('ches', 'チーズ'),
    ('shes', 'シーズ'),
    ('ses', 'セズ'),
    ('zes', 'ゼズ'),
    ('xes', 'クセズ'),
]

# ============================================================
# English phoneme clusters -> Katakana mapping
# ============================================================
CONSONANT_VOWEL_MAP = {
    # Direct vowels
    'a': 'ア', 'i': 'イ', 'u': 'ウ', 'e': 'エ', 'o': 'オ',

    # K-row
    'ka': 'カ', 'ki': 'キ', 'ku': 'ク', 'ke': 'ケ', 'ko': 'コ',
    'ca': 'カ', 'ci': 'シ', 'cu': 'ク', 'ce': 'セ', 'co': 'コ',

    # S-row
    'sa': 'サ', 'si': 'シ', 'su': 'ス', 'se': 'セ', 'so': 'ソ',
    'sha': 'シャ', 'shi': 'シ', 'shu': 'シュ', 'she': 'シェ', 'sho': 'ショ',

    # T-row
    'ta': 'タ', 'ti': 'チ', 'tu': 'ツ', 'te': 'テ', 'to': 'ト',
    'chi': 'チ', 'cha': 'チャ', 'chu': 'チュ', 'che': 'チェ', 'cho': 'チョ',
    'thi': 'シ', 'tha': 'サ', 'thu': 'ス', 'the': 'ザ', 'tho': 'ソ',
    'tsu': 'ツ', 'tsa': 'ツァ',

    # N-row
    'na': 'ナ', 'ni': 'ニ', 'nu': 'ヌ', 'ne': 'ネ', 'no': 'ノ',

    # H-row
    'ha': 'ハ', 'hi': 'ヒ', 'hu': 'フ', 'he': 'ヘ', 'ho': 'ホ',

    # F-row
    'fa': 'ファ', 'fi': 'フィ', 'fu': 'フ', 'fe': 'フェ', 'fo': 'フォ',

    # M-row
    'ma': 'マ', 'mi': 'ミ', 'mu': 'ム', 'me': 'メ', 'mo': 'モ',

    # Y-row
    'ya': 'ヤ', 'yi': 'イ', 'yu': 'ユ', 'ye': 'イェ', 'yo': 'ヨ',

    # R-row (L and R both map here)
    'ra': 'ラ', 'ri': 'リ', 'ru': 'ル', 're': 'レ', 'ro': 'ロ',
    'la': 'ラ', 'li': 'リ', 'lu': 'ル', 'le': 'レ', 'lo': 'ロ',

    # W-row
    'wa': 'ワ', 'wi': 'ウィ', 'wu': 'ウ', 'we': 'ウェ', 'wo': 'ヲ',

    # G-row
    'ga': 'ガ', 'gi': 'ギ', 'gu': 'グ', 'ge': 'ゲ', 'go': 'ゴ',

    # Z-row
    'za': 'ザ', 'zi': 'ジ', 'zu': 'ズ', 'ze': 'ゼ', 'zo': 'ゾ',

    # D-row
    'da': 'ダ', 'di': 'ディ', 'du': 'ドゥ', 'de': 'デ', 'do': 'ド',

    # B-row
    'ba': 'バ', 'bi': 'ビ', 'bu': 'ブ', 'be': 'ベ', 'bo': 'ボ',

    # P-row
    'pa': 'パ', 'pi': 'ピ', 'pu': 'プ', 'pe': 'ペ', 'po': 'ポ',

    # J-row
    'ja': 'ジャ', 'ji': 'ジ', 'ju': 'ジュ', 'je': 'ジェ', 'jo': 'ジョ',

    # V-row
    'va': 'ヴァ', 'vi': 'ヴィ', 'vu': 'ヴ', 've': 'ヴェ', 'vo': 'ヴォ',

    # Combinations
    'kya': 'キャ', 'kyu': 'キュ', 'kyo': 'キョ',
    'gya': 'ギャ', 'gyu': 'ギュ', 'gyo': 'ギョ',
    'nya': 'ニャ', 'nyu': 'ニュ', 'nyo': 'ニョ',
    'hya': 'ヒャ', 'hyu': 'ヒュ', 'hyo': 'ヒョ',
    'bya': 'ビャ', 'byu': 'ビュ', 'byo': 'ビョ',
    'pya': 'ピャ', 'pyu': 'ピュ', 'pyo': 'ピョ',
    'mya': 'ミャ', 'myu': 'ミュ', 'myo': 'ミョ',
    'rya': 'リャ', 'ryu': 'リュ', 'ryo': 'リョ',

    # Special English sounds
    'qua': 'クワ', 'qui': 'クイ', 'que': 'ケ', 'quo': 'クオ',
    'wha': 'ワ', 'whi': 'ウィ', 'who': 'フー',

    # Digraphs
    'ph': 'フ',
    'th': 'ス',
}

# Trailing consonants (no following vowel) -> katakana with implied 'u' or special
TRAILING_CONSONANT = {
    'k': 'ク', 'g': 'グ', 's': 'ス', 'z': 'ズ',
    't': 'ト', 'd': 'ド', 'n': 'ン', 'b': 'ブ',
    'p': 'プ', 'm': 'ム', 'r': 'ル', 'l': 'ル',
    'f': 'フ', 'v': 'ヴ', 'x': 'クス',
    'sh': 'シュ', 'ch': 'チ', 'th': 'ス', 'ng': 'ング',
    'ck': 'ック', 'tch': 'ッチ',
}

# English vowel digraphs
VOWEL_DIGRAPHS = {
    'ee': 'イー', 'ea': 'イー', 'oo': 'ウー', 'ou': 'アウ',
    'ow': 'アウ', 'oi': 'オイ', 'oy': 'オイ', 'ai': 'エイ',
    'ay': 'エイ', 'au': 'オー', 'aw': 'オー', 'ei': 'エイ',
    'ey': 'エイ', 'ie': 'イー', 'ue': 'ウー',
}


def _apply_suffix_rules(word: str) -> tuple:
    """Try to decompose a word into stem + known suffix.

    Returns:
        (stem, katakana_suffix) if a suffix matched, else (word, None)
    """
    lower = word.lower()
    for suffix, katakana in SUFFIX_RULES:
        if lower.endswith(suffix) and len(lower) > len(suffix):
            stem = lower[:-len(suffix)]
            # Make sure the stem isn't empty or too short
            if len(stem) >= 1:
                return stem, katakana
    return lower, None


def _convert_chars(text: str) -> str:
    """Convert a string character-by-character using phoneme maps."""
    result = []
    i = 0
    length = len(text)

    while i < length:
        matched = False

        # Try longest match first (4, 3, 2, 1 chars)
        for span in (4, 3, 2, 1):
            if i + span > length:
                continue
            chunk = text[i:i + span]

            # Check consonant+vowel map
            if chunk in CONSONANT_VOWEL_MAP:
                result.append(CONSONANT_VOWEL_MAP[chunk])
                i += span
                matched = True
                break

            # Check vowel digraphs
            if span <= 2 and chunk in VOWEL_DIGRAPHS:
                result.append(VOWEL_DIGRAPHS[chunk])
                i += span
                matched = True
                break

        if matched:
            continue

        # Handle trailing/standalone consonants
        for span in (3, 2, 1):
            if i + span > length:
                continue
            chunk = text[i:i + span]
            if chunk in TRAILING_CONSONANT:
                next_pos = i + span
                if next_pos < length and text[next_pos] in 'aiueo':
                    break
                result.append(TRAILING_CONSONANT[chunk])
                i += span
                matched = True
                break

        if matched:
            continue

        # Handle double consonants (gemination -> ッ)
        if i + 1 < length and text[i] == text[i + 1] and text[i] not in 'aiueo':
            result.append('ッ')
            i += 1
            continue

        # Fallback
        char = text[i]
        if char in 'aiueo':
            vowel_map = {'a': 'ア', 'i': 'イ', 'u': 'ウ', 'e': 'エ', 'o': 'オ'}
            result.append(vowel_map[char])
        elif char == 'n' and (i + 1 >= length or text[i + 1] not in 'aiueoy'):
            result.append('ン')
        elif char.isalpha():
            if char in TRAILING_CONSONANT:
                result.append(TRAILING_CONSONANT[char])
            else:
                result.append('ウ')
        i += 1

    return ''.join(result)


def _convert_word(word: str) -> str:
    """Convert a single English word to katakana approximation."""
    lower = word.lower().strip()

    # Strip apostrophe-containing forms for dict lookup
    if lower in WORD_DICT:
        return WORD_DICT[lower]

    # Handle silent 'e' at end (like "cake" -> "keik" not "kake")
    # Remove trailing silent 'e' before conversion if word has a vowel before consonant+e
    process_word = lower

    # Try suffix decomposition
    stem, suffix_katakana = _apply_suffix_rules(process_word)
    if suffix_katakana:
        # Check if the stem itself is in the dictionary
        if stem in WORD_DICT:
            return WORD_DICT[stem] + suffix_katakana
        # Convert stem + append suffix
        return _convert_chars(stem) + suffix_katakana

    # Handle trailing silent 'e': remove it for conversion if preceded by consonant
    if (len(process_word) > 2
            and process_word.endswith('e')
            and process_word[-2] not in 'aiueo'
            and any(c in 'aiueo' for c in process_word[:-1])):
        process_word = process_word[:-1]

    return _convert_chars(process_word)


def english_to_katakana(text: str) -> str:
    """Convert English text to katakana phonetic approximation.

    Args:
        text: English text

    Returns:
        Katakana string suitable for VOICEVOX synthesis
    """
    if not text.strip():
        return text

    # Check if text is already Japanese (contains hiragana/katakana/kanji)
    if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text):
        return text  # Already Japanese, pass through

    # Split into words and punctuation, preserving apostrophes within words
    tokens = re.findall(r"[a-zA-Z']+|[^a-zA-Z']+", text)

    result = []
    for token in tokens:
        if re.match(r"[a-zA-Z']+", token):
            result.append(_convert_word(token))
        else:
            # Keep punctuation, map some to Japanese equivalents
            mapped = token
            mapped = mapped.replace('.', '。')
            mapped = mapped.replace(',', '、')
            mapped = mapped.replace('!', '！')
            mapped = mapped.replace('?', '？')
            mapped = mapped.replace(' ', '')  # Remove spaces
            result.append(mapped)

    return ''.join(result)
