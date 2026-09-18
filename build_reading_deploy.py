# -*- coding: utf-8 -*-
"""
为 Reading牛津阅读 独立站点生成相对路径的 INLINE_DATA：
1) 读取 reading_all.json（绝对路径）
2) 过滤仅 oxford/（Reading牛津阅读）系列
3) 音频路径 d:/.../少儿学习资料网站\reading_audio\... -> reading_audio/...（相对）
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
    print('补齐 lesson.title:', fixed_title, ' 归一化 vocab.cn:', fixed_cn)
    return ox

def main():
    data = json.load(open(SRC_JSON, encoding='utf-8'))
    # 过滤 oxford
    ox = {k: v for k, v in data.items() if k.startswith(KEEP_SERIES + '/')}
    print('过滤后键数:', len(ox), '示例键:', list(ox.keys())[:3])

    # 字段归一化（必须在路径转换前，逻辑无关顺序但统一在此）
    ox = normalize(ox)

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
