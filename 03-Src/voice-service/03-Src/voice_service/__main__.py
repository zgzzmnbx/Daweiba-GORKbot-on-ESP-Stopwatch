import argparse
import json
import sys
from pathlib import Path

from .config import load_settings


def main():
    parser = argparse.ArgumentParser(description="智算语音桥")
    parser.add_argument("command", choices=["serve", "asr", "tts"])
    parser.add_argument("--config")
    parser.add_argument("--input")
    parser.add_argument("--text")
    parser.add_argument("--output", default="Codex-Temp/cli-output.wav")
    parser.add_argument("--speaker", type=int, default=3)
    args = parser.parse_args()
    config = load_settings(args.config)
    if args.command == "serve":
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(config), host=config.host, port=config.port, access_log=False)
        return
    from .engines import LocalEngines
    engines = LocalEngines(config)
    if args.command == "asr":
        if not args.input:
            parser.error("asr requires --input WAV")
        if Path(args.input).stat().st_size > config.max_upload:
            parser.error("WAV exceeds configured size")
        result = engines.run("asr", {"audio": Path(args.input).read_bytes()})
    else:
        if not args.text or len(args.text) > config.max_text or not 3 <= args.speaker <= 102:
            parser.error("tts requires 1-300 characters and a Chinese speaker 3..102")
        result = engines.run("tts", {"text": args.text, "speaker_id": args.speaker, "speed": 1.0, "sample_rate": 24000})
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(result["result"].pop("audio"))
        result["output"] = str(output)
    print(json.dumps({"engines": engines.status, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
