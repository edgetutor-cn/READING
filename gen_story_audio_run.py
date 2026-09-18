# -*- coding: utf-8 -*-
"""驱动脚本：批量生成 7 个级别「每课课文」音频（Kokoro bf_emma）。

设计要点：必须用独立 .py 文件运行——Windows 下 ProcessPoolExecutor 用 spawn，
子进程会重新 import __main__；若用 `python -c` 或 heredoc 会导致重复执行/崩溃。

用法：
  <kokoro_env>/Scripts/python.exe gen_story_audio_run.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rebuild_oxford_lessons as m

if __name__ == '__main__':
    tasks = m.rebuild_all()
    n = m.gen_story_audio(tasks)
    print('DONE story_audio=%d' % n)
