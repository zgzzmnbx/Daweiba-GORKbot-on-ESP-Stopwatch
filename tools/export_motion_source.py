"""Provide the complete corresponding local motion integration source, excluding private state."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'03-Src/stopwatch-voice-companion/static/motion/source.zip'
ALLOWED={'.js','.mjs','.cjs','.py','.cpp','.cc','.c','.h','.hpp','.inc','.html','.css','.json','.md','.toml','.ini','.svg','.txt','.yaml','.yml'}

def files():
    for directory in ('03-Src/stopwatch-voice-companion','03-Src/gork-desktop','03-Src/stopwatch-grok-avatar','03-Src/voice-service'):
        for f in (ROOT/directory).rglob('*'):
            if not f.is_file() or any(p in {'.git','.pio','node_modules','__pycache__','.pytest_cache'} or p.startswith('.venv') for p in f.relative_to(ROOT).parts):continue
            if '.local.' in f.name or f.suffix=='.bak' or f.name.startswith('.env'):continue
            connection_wav = f.parent == ROOT/'03-Src/stopwatch-grok-avatar/assets/connection-voice' and f.name in {'wifi.wav','ble.wav'}
            if f.suffix in ALLOWED or f.name.startswith('LICENSE') or connection_wav:yield f
    for name in ('convert_gork_motion.py','export_watch_expressions.py','test_watch_firmware.py','generate_connection_voice.py','test_connection_announcements.py','export_desktop_avatar.py','export_motion_source.py','test_motion_native.py','test_motion_refresh.py','run_motion_preview.py','verify_motion_electron.cjs','verify_custom_expression_electron.cjs','verify_custom_motion_playback.cjs','verify_motion_ranges.cjs','integrate_motion_assets.py','verify_external_ui.cjs','run_external_fixture.py','stopwatch_audio.py','test_stopwatch_audio.py','test_audio_capture_pipeline.py'):
        f=ROOT/'tools'/name
        if f.exists():yield f
    for name in ('README.md','AGENTS.md','CHANGELOG.md',
                 '00-docs/00-PRD/40-固定提示语音缓存与动态数字即时合成.md',
                 '04-output/v0.20.30/固定语音缓存验收.md',
                 '04-output/v0.20.31/相同数字语音复用验收.md',
                 '00-docs/接口/Gork机器人通用输出接口-v1.0.0-【codex】.md',
                 '00-docs/接口/Gork通知请求-schema-v1.0.0-【codex】.json',
                 '00-docs/00-PRD/39-Gork通用输出接口与阶段联动-【codex】.md',
                 '04-output/v0.20.28/通用输出接口与哨兵实施验收-【codex】.md',
                 '04-output/v0.20.29/调试未响应原因与接入提示修复-【codex】.md',
                 '00-docs/00-PRD/38-Astra完成金额播报与验收-【codex】.md',
                 '04-output/v0.20.27/金额播报实施与交接-【codex】.md',
                 '00-docs/00-PRD/32-v0.19.0-动效编辑器接入与Watch映射-【codex】.md',
                 '04-output/v0.19.0/动效编辑器实施与验收-【codex】.md',
                 '00-docs/00-PRD/33-v0.19.2-自定义表情库与编辑保存-【codex】.md',
                 '04-output/v0.19.2/自定义表情编辑与默认动画恢复验收-【codex】.md',
                 '04-output/v0.19.3/自定义表情播放与多副本保存验收-【codex】.md',
                 '04-output/v0.19.4/书写自定义范围扩大验收-【codex】.md'):
        f=ROOT/name
        if f.exists():yield f

if __name__=='__main__':
    with zipfile.ZipFile(DEST,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files()):z.write(f,str(f.relative_to(ROOT)).replace('\\','/'))
    print(f'Corresponding source archive created: {DEST.name}')
