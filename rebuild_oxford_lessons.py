# -*- coding: utf-8 -*-
"""
重建 Reading牛津阅读 7 个级别（REL1/3/4/6/7/8/9）的「按课」结构。

源：各级别「复习打印版.pdf」末尾的「详细课程大纲」表（当初 parse_oxford_review.py 跳过了）。
该表含每课：课次 / 英文课题 / 中文主题 / 体裁(或核心内容)。

逻辑：
1. 解析大纲 -> 每课 {num, unit_idx, en, tail}
2. 读取 reading_all.json 中该级别的单元 vocab/sentences（单元级，真实存在）
3. 把单元 vocab/sentences 挂载到该单元下每一课（源只有单元级词表，无分课词表，如实标注）
4. 每课的 story(课文) = 英文课题 + 中文主题 + 体裁/核心内容（真实每课内容）
5. 写回 reading_all.json（覆盖这 7 个级别的 units 结构，REL2/REL5 不动）
"""
import json, re, os, subprocess
from pypdf import PdfReader

BASE = r'd:/好约课外教课会员管理/少儿学习资料网站'
PDF_BASE = r'd:/外教课/学生复习资料/11-Reading牛津阅读'
SRC_JSON = os.path.join(BASE, 'reading_all.json')
LEVELS = ['REL1', 'REL3', 'REL4', 'REL6', 'REL7', 'REL8', 'REL9']
CJK = r'[一-鿿]'

def find_pdf(L):
    for root, _, fs in os.walk(os.path.join(PDF_BASE, L)):
        for f in fs:
            if '打印版' in f and f.endswith('.pdf'):
                return os.path.join(root, f)
    return None

def extract_outline_text(L):
    p = find_pdf(L)
    if not p:
        return ''
    return "".join(pg.extract_text() or "" for pg in PdfReader(p).pages)

def seg_text(txt):
    """截取「详细课程大纲」段并去换行（PDF 折行导致课次与单元名粘连，整段匹配更稳）。"""
    i = txt.find('详细课程大纲')
    if i < 0:
        i = txt.find('课程大纲')
    if i < 0:
        return ''
    seg = txt[i:]
    seg = seg.replace('\n', ' ').replace('\r', ' ')
    # 只去掉列头行（不含课序号，避免吞掉第1课编号）
    seg = re.sub(r'课\s*次.*?核心内容', ' ', seg)
    seg = re.sub(r'#\s*课名.*?体裁', ' ', seg)
    seg = re.sub(r'课\s*题.*?体\s*裁', ' ', seg)
    return seg

def split_en_tail(s):
    """从字符串切出英文课题（到首个中文字）与剩余（中文主题+体裁）。"""
    m = re.search(CJK, s)
    if not m:
        return s.strip(), ''
    idx = m.start()
    return s[:idx].strip(), s[idx:].strip()

# 英文课题（容忍空格/撇号/连字符/括号）
EN = r"[A-Za-z][A-Za-z\s'’.\-()]*?"
# 中文主题+体裁（容忍中英文混排、斜杠、括号、数字）
ZH = r"[一-鿿][一-鿿\s/，、（）()a-zA-Z0-9.\-]*"

def parse_outline(L):
    """锚点切分法：先定位每课起始位置，按锚点切 chunk 解析，避免跨课吞噬。"""
    txt = extract_outline_text(L)
    seg = seg_text(txt)
    # 检测格式
    if re.search(r'\d{1,2}\s+Unit\s+\d+', seg):
        fmt = 'A'
    elif re.search(r'L\d{1,2}', seg):
        fmt = 'C'
    else:
        fmt = 'B'
    if fmt == 'A':
        anchors = [(m.start(), int(m.group(1)), int(m.group(2)) - 1)
                   for m in re.finditer(r'(\d{1,2})\s+Unit\s+(\d+)', seg)]
        prefix = r'^\d{1,2}\s+Unit\s+\d+\s+' + CJK + r'[一-鿿\s]*\s+(?=[A-Za-z])'
    elif fmt == 'C':
        anchors = [(m.start(), int(m.group(1)), 0)
                   for m in re.finditer(r'L(\d{1,2})\s+(?=[A-Za-z])', seg)]
        prefix = r'^L\d{1,2}\s+'
    else:
        unit_headers = [(m.start(), int(m.group(1)) - 1)
                        for m in re.finditer(r'Unit\s+(\d+)\s+' + CJK, seg)]
        def unit_at(pos):
            u = 0
            for hp, hu in unit_headers:
                if hp <= pos:
                    u = hu
            return u
        anchors = [(m.start(), int(m.group(1)), unit_at(m.start()))
                   for m in re.finditer(r'(\d{1,2})\s+(?=[A-Za-z])', seg)]
        prefix = r'^\d{1,2}\s+'
    lessons = []
    for i, (pos, num, unit) in enumerate(anchors):
        end = anchors[i + 1][0] if i + 1 < len(anchors) else len(seg)
        chunk = seg[pos:end].strip()
        chunk = re.sub(prefix, '', chunk)
        en, tail = split_en_tail(chunk)
        lessons.append({'num': num, 'unit': unit, 'en': en, 'tail': tail})
    return lessons

AUDIO_ROOT = r'd:/好约课外教课会员管理/少儿学习资料网站/reading_audio'

def rebuild_all():
    """重建 7 个级别的按课结构并写回 reading_all.json；收集待生成课文音频。"""
    data = json.load(open(SRC_JSON, encoding='utf-8'))
    story_tasks = []  # (text_en, abs_mp3_path)
    total_lessons = 0
    for L in LEVELS:
        lessons = parse_outline(L)
        key = 'oxford/' + L
        old = data[key]
        vocab_units = old['units']
        from collections import defaultdict
        by_unit = defaultdict(list)
        for le in lessons:
            by_unit[le['unit']].append(le)
        new_units = []
        for ui, vu in enumerate(vocab_units):
            unit_lessons = sorted(by_unit.get(ui, []), key=lambda x: x['num'])
            base_lesson = vu.get('lessons', [{}])[0]
            base_audio = base_lesson.get('audio', {}) or {}
            new_lessons = []
            for li, le in enumerate(unit_lessons, 1):  # li = 单元内课序号(1-based)
                story = (le['en'] + '\n' + le['tail']).strip() if le['tail'] else le['en']
                story_mp3 = os.path.join(AUDIO_ROOT, 'oxford', L, f'U{ui+1}', f'L{li}', 'story.mp3')
                # 复用单元级 vocab/sentences 音频（已存在于 Uy/L1）
                new_lessons.append({
                    'title': f"L{le['num']} {le['en']}",
                    'vocab': base_lesson.get('vocab', []),
                    'sentences': base_lesson.get('sentences', []),
                    'story': story,
                    'audio': {
                        'vocab': base_audio.get('vocab', []),
                        'sentences': base_audio.get('sentences', []),
                        'story': story_mp3,
                        'lesson': story_mp3,
                    },
                })
                # 课文音频：用英文课题名朗读（干净音质）；仅当缺失时生成
                if not (os.path.exists(story_mp3) and os.path.getsize(story_mp3) > 0):
                    story_tasks.append((le['en'], story_mp3))
                total_lessons += 1
            new_units.append({'name': vu['name'], 'lessons': new_lessons})
        data[key]['units'] = new_units
    json.dump(data, open(SRC_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'已写回 reading_all.json：{len(LEVELS)} 级别 / {total_lessons} 课，待生成课文音频 {len(story_tasks)} 条')
    return story_tasks

# ---------- 课文音频生成（复用 Kokoro 管线）----------
ESPEAK_DATA = r'D:/espeak_ng_data'
MODEL = os.path.join(BASE, 'kokoro_models', 'kokoro-v1.0.onnx')
VOICES = os.path.join(BASE, 'kokoro_models', 'voices-v1.0.bin')
FFMPEG = r'E:/迅雷下载/ffmpeg-8.1-full_build/ffmpeg-8.1-full_build/bin/ffmpeg.exe'
VOICE = 'bf_emma'
WORKERS = 3

def worker_init():
    import locale
    try: locale.setlocale(locale.LC_ALL, 'English_United States.65001')
    except Exception: pass
    os.environ['ESPEAK_DATA_PATH'] = ESPEAK_DATA
    global KOKO
    import espeakng_loader
    from kokoro_onnx import Kokoro
    from kokoro_onnx.config import EspeakConfig
    cfg = EspeakConfig(lib_path=espeakng_loader.get_library_path(), data_path=ESPEAK_DATA)
    KOKO = Kokoro(MODEL, VOICES, espeak_config=cfg)

def _gen_safe(text, voice, speed, depth=0):
    import numpy as np
    try:
        return KOKO.create(text, voice=voice, speed=speed)
    except Exception:
        if depth > 4:
            return np.zeros(int(24000 * 0.3), dtype=np.float32), 24000
        parts = text.split(' ')
        if len(parts) < 2:
            return np.zeros(int(24000 * 0.3), dtype=np.float32), 24000
        mid = len(parts) // 2
        a1, sr = _gen_safe(' '.join(parts[:mid]), voice, speed, depth + 1)
        a2, _ = _gen_safe(' '.join(parts[mid:]), voice, speed, depth + 1)
        return np.concatenate([a1, a2]), sr

def gen_one(args):
    import numpy as np, wave
    text, wav_path, mp3_path, voice = args
    audio, sr = _gen_safe(text, voice, 0.95)
    os.makedirs(os.path.dirname(wav_path), exist_ok=True)
    with wave.open(wav_path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    subprocess.run([FFMPEG, '-y', '-i', wav_path, '-codec:a', 'libmp3lame', '-b:a', '64k', mp3_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return mp3_path

def gen_story_audio(tasks):
    """批量生成（必须在独立 .py 中调用：Windows spawn 子进程会重新 import __main__）。
    注意：subprocess 已在模块级 import，worker 进程无需额外注入。"""
    if not tasks:
        print('课文音频均已存在，跳过生成')
        return 0
    jobs = []
    for text, mp3 in tasks:
        wav = mp3[:-4] + '.wav'
        jobs.append((text, wav, mp3, VOICE))
    print(f'生成课文音频 {len(jobs)} 条 (workers={WORKERS}) ...')
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=WORKERS, initializer=worker_init) as ex:
        done = list(ex.map(gen_one, jobs))
    print(f'课文音频生成完成: {len(done)}')
    return len(done)

if __name__ == '__main__':
    import subprocess as _sp
    story_tasks = rebuild_all()
    n = gen_story_audio(story_tasks)
    print('DONE story_audio=%d' % n)
