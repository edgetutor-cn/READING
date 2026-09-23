# -*- coding: utf-8 -*-
"""
为 Reading牛津阅读 独立站点生成相对路径的 INLINE_DATA：
1) 读取 reading_all.json（绝对路径）
2) 过滤仅 oxford/（Reading牛津阅读）系列
3) 音频路径 d:/.../少儿学习资料网站/reading_audio/... -> reading_audio/...（相对）
4) 注入 deploy/index.html 的 INLINE_DATA 块
"""
import os, json

SRC_JSON = r'd:/好约课外教课会员管理/少儿学习资料网站/reading_all.json'
SRC_BASE = r'd:/好约课外教课会员管理/少儿学习资料网站'
HTML = r'd:/好约课外教课会员管理/reading-oxford-deploy/index.html'
KEEP_SERIES = 'oxford'  # 仅 Reading牛津阅读

def to_rel(p):
    if not p:
        return p
    p = p.replace('\\', '/')
    p = p.replace(SRC_BASE + '/', '')
    return p  # reading_audio/oxford/...

def walk(val):
    if isinstance(val, list):
        return [walk(v) for v in val]
    if isinstance(val, dict):
        return {k: walk(v) for k, v in val.items()}
    if isinstance(val, str):
        # 仅处理音频路径（含 reading_audio）
        if 'reading_audio' in val:
            return to_rel(val)
        return val
    return val

def normalize(ox):
    """补齐字段，避免前端渲染崩溃：
    - lesson.title 缺失 -> 单课单元用单元名，多课单元用 L1/L2...
    - vocab 中文键 zh -> cn（前端统一读 cn）
    - unit.name 缺失 -> Unit N
    """
    fixed_title = fixed_cn = 0
    for key, lvl in ox.items():
        for ui, unit in enumerate(lvl.get('units') or []):
            uname = (unit.get('name') or '').strip() or ('Unit %d' % (ui + 1))
            unit['name'] = uname
            lessons = unit.get('lessons') or []
            for li, les in enumerate(lessons):
                if not (les.get('title') or '').strip():
                    les['title'] = uname if len(lessons) == 1 else ('L%d' % (li + 1))
                    fixed_title += 1
                for w in (les.get('vocab') or []):
                    if not w.get('cn') and w.get('zh'):
                        w['cn'] = w['zh']
                        fixed_cn += 1
                    w.pop('zh', None)
            # 判断该单元是否为「共用词表」：多课且各课 vocab/sentences 完全一致
            unit['shared_scope'] = detect_shared(lessons)
    print('补齐 lesson.title:', fixed_title, ' 归一化 vocab.cn:', fixed_cn)
    return ox

def _sig(les):
    v = [(w.get('en') or '', w.get('cn') or '') for w in (les.get('vocab') or [])]
    s = list(les.get('sentences') or [])
    return json.dumps({'v': v, 's': s}, ensure_ascii=False, sort_keys=True)

def detect_shared(lessons):
    """源资料按「单元」编排词汇句型时，同一单元下每课词表完全相同 → 标记共用。
    真实逐课数据的级别（如 REL2/REL5）各课词表不同，不会标记。"""
    if not lessons or len(lessons) < 2:
        return False
    first = _sig(lessons[0])
    return all(_sig(le) == first for le in lessons[1:])

# ============================================================
# 生词重排 + 核心/拓展 两档 + 每组 ≤10 分组
# 难度启发式（无真实词频元数据，用可解释代理）：
#   1) 极高频常用词（COMMON 种子集）→ 难度最低，归核心
#   2) 其余按单词长度升序（短词更易读/学）→ 由易到难
# 排序后前一半(ceil N/2) 为核心词汇，后一半为拓展词汇；
# 若总数 ≤10 则全部归核心、不生成拓展档。
# 音频路径按位置与单词同步重排并内嵌进 item，彻底杜绝"串音"。
# ============================================================
COMMON = set("""
the a an and is are was were be been being to of in on at by for with from
i you he she it we they me my your his her our their this that these those
go went see saw look come came eat ate drink drank run ran play played jump
big small red blue green yellow black white one two three four five six seven eight nine ten
cat dog bird fish sun moon star tree house car bus book pen bag ball happy sad
mother father family baby friend school teacher water milk food apple
""".split())

SPLIT_RATIO = 0.5   # 前 50% 难度较低的词归核心词汇
CHUNK = 10          # 每个可点击选项最多 10 个词

def _sort_key(en):
    w = (en or '').strip().lower()
    return (0 if w in COMMON else 1, len(w), w)

def _chunk(pairs, size=CHUNK):
    out = []
    for i in range(0, len(pairs), size):
        out.append([{'en': p[0].get('en', ''), 'cn': p[0].get('cn') or p[0].get('zh') or '',
                     'audio': p[1]} for p in pairs[i:i + size]])
    return out

def reclassify_vocab(ox):
    """对每课生词：排序 → 分核心/拓展 → 每组 ≤10；音频随单词同步重排。"""
    done = 0
    for key, lvl in ox.items():
        for unit in lvl.get('units') or []:
            for les in (unit.get('lessons') or []):
                vocab = les.get('vocab') or []
                if not vocab:
                    les['vocab_core'] = []
                    les['vocab_ext'] = []
                    continue
                a = les.get('audio') or {}
                auds = a.get('vocab') or []
                # 配对（按位置对齐，缺音频补 None）
                pairs = [(w, auds[i] if i < len(auds) else None) for i, w in enumerate(vocab)]
                # 由易到难排序（常用词优先，短词优先）
                pairs.sort(key=lambda pr: _sort_key(pr[0].get('en', '')))
                n = len(pairs)
                if n <= CHUNK:
                    core, ext = pairs, []
                else:
                    k = max(CHUNK, int(round(n * SPLIT_RATIO)))
                    k = min(k, n - 1)  # 至少留 1 个给拓展档
                    core, ext = pairs[:k], pairs[k:]
                les['vocab_core'] = _chunk(core)
                les['vocab_ext'] = _chunk(ext) if ext else []
                # 核心/拓展已内嵌 en/cn/audio，删掉冗余的 vocab / audio.vocab 并行数组
                les.pop('vocab', None)
                if isinstance(les.get('audio'), dict):
                    les['audio'].pop('vocab', None)
                done += 1
    print('重排/分档课数:', done)
    return ox

def main():
    data = json.load(open(SRC_JSON, encoding='utf-8'))
    # 过滤 oxford
    ox = {k: v for k, v in data.items() if k.startswith(KEEP_SERIES + '/')}
    print('过滤后键数:', len(ox), '示例键:', list(ox.keys())[:3])

    # 字段归一化（必须在路径转换前，逻辑无关顺序但统一在此）
    ox = normalize(ox)

    # 生词重排：核心/拓展两档 + 每组 ≤10（音频随单词同步重排，杜绝串音）
    ox = reclassify_vocab(ox)

    # 转换音频路径为相对
    ox = walk(ox)

    # 统计音频引用
    total = 0
    for key, lvl in ox.items():
        for unit in lvl['units']:
            for les in unit['lessons']:
                a = les.get('audio') or {}
                for kind in ('vocab', 'sentences', 'story', 'lesson'):
                    val = a.get(kind)
                    if val is None:
                        continue
                    paths = val if isinstance(val, list) else [val]
                    for p in paths:
                        if p:
                            total += 1
    print('音频引用总数:', total)

    compact = json.dumps(ox, ensure_ascii=False, separators=(',', ':'))
    html = open(HTML, encoding='utf-8').read()
    mark = 'const INLINE_DATA = '
    mi = html.find(mark)
    assert mi != -1, '未找到 INLINE_DATA 标记'
    li = html.find('let DATA', mi)
    assert li != -1, '未找到结束锚点 let DATA'
    block = compact + ';\n\n'
    new = html[:mi + len(mark)] + block + html[li:]
    open(HTML, 'w', encoding='utf-8').write(new)
    print('INLINE_DATA 已重写（相对路径），字符数:', len(block))

if __name__ == '__main__':
    main()
