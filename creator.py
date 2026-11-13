#!/usr/bin/env python3
"""Local Creator model and video-editing entry point. No third-party Python deps."""
import argparse
import json
import os
import sys
from pathlib import Path
from creator_tools import models

ROOT = Path(__file__).resolve().parent


def write_json_new(path, data):
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n')
    return str(p)


def load_dotenv(path=None):
    """Load KEY=VALUE lines from the repo .env without overriding the real environment."""
    p = Path(path) if path else ROOT / '.env'
    if not p.is_file():
        return []
    loaded = []
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.removeprefix('export ').partition('=')
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(description='Creator: explicit model calls, reviewable edit plans, local FFmpeg rendering. No automatic uploads.')
    parser.add_argument('--inventory', default=str(ROOT/'local'/'azure-inventory.json'), help='Local Azure deployment inventory JSON')
    sub = parser.add_subparsers(dest='command', required=True)
    motion = sub.add_parser('motion', help='Offline GSAP motion compositions, code-authored and seekable')
    motion_sub = motion.add_subparsers(dest='motion_action', required=True)
    motion_sub.add_parser('doctor', help='Verify the checksum-pinned local GSAP runtime')
    motion_create = motion_sub.add_parser('create', help='Create a new standalone HTML composition directory')
    motion_create.add_argument('--output', required=True, help='New directory; refuses to overwrite')
    motion_create.add_argument('--title', required=True, help='Single-line headline, maximum 120 characters')
    motion_create.add_argument('--subtitle', default='One timeline. Every frame in its place.', help='Single-line subtitle, maximum 240 characters')
    diagram = sub.add_parser('diagram', help='Pinned local Archify diagrams; standalone HTML, not video')
    diagram_sub = diagram.add_subparsers(dest='diagram_action', required=True)
    di = diagram_sub.add_parser('install', help='Install the checksum-pinned local release ZIP; never overwrite')
    di.add_argument('--archive', required=True)
    diagram_sub.add_parser('doctor', help='Check installed package integrity and runtime')
    for action in ('validate', 'render'):
        dc = diagram_sub.add_parser(action)
        dc.add_argument('--input', required=True, help='Archify typed diagram JSON')
        dc.add_argument('--quality', choices=['standard', 'showcase'], default='showcase')
        if action == 'render':
            dc.add_argument('--output', required=True, help='New standalone .html path')
            dc.add_argument('--showcase-bridge', action='store_true',
                            help='Inject deterministic __ready/__advance/__done hooks to step guided chapters with showcase')
            dc.add_argument('--chapter-dwell', type=float, default=2500.0,
                            help='Milliseconds per guided chapter when --showcase-bridge is enabled (default 2500)')
            dc.add_argument('--video', help='Optional new .mp4 path to record the bridged diagram via showcase')
            dc.add_argument('--template', choices=['full', 'presenter', 'story', 'embed', 'minimal'], default='full',
                            help='full = original Archify UI; presenter = chapters + detail panel; story = guided chapters + graph for embedding; '
                                 'embed = graph only for iframes; minimal = static graph')
            dc.add_argument('--hide', action='append', default=[], metavar='PART',
                            help='Hide a part (repeatable): toolbar header chapters cards nav zoom passport details')
            dc.add_argument('--show', action='append', default=[], metavar='PART',
                            help='Re-show a part the template hides (repeatable)')
            dc.add_argument('--details', help='JSON keyed by node id: {"id":{"what","why","example"}} for the detail panel')
            dc.add_argument('--embed-snippet', action='store_true', help='Also print an <iframe> snippet for the output')
    fabric = sub.add_parser('fabric', help='Local protected-static-hosting deployment kits; never uploads')
    fabric_sub = fabric.add_subparsers(dest='fabric_action', required=True)
    fabric_package = fabric_sub.add_parser('package', help='Package one explicitly trusted self-contained HTML; no install or cloud calls')
    fabric_package.add_argument('--input', required=True, help='Explicit self-contained .html file')
    fabric_package.add_argument('--output', required=True, help='New kit directory; parent must exist')
    fabric_package.add_argument('--name', default='creator-data-story', help='Lowercase alphanumeric/hyphen app slug')
    data_story = sub.add_parser('data-story', help='Validate or render an offline evidence-backed reading page')
    data_story_sub = data_story.add_subparsers(dest='data_story_action', required=True)
    for action in ('validate', 'render'):
        ds = data_story_sub.add_parser(action)
        ds.add_argument('--input', required=True, help='Evidence data-story JSON')
        if action == 'render':
            ds.add_argument('--output', required=True, help='New standalone .html path; never overwrite')
    studio = sub.add_parser('studio', help='Start the local non-destructive browser editor')
    studio.add_argument('--port', type=int, default=4318)
    studio.add_argument('--host',default='127.0.0.1',help='Specific private LAN IPv4 to share with trusted devices; no login. Default loopback.')
    studio.add_argument('--workspace', default=str(ROOT/'local'/'studio'))
    sc = sub.add_parser('showcase', help='Record a self-animating HTML page to a frame-exact MP4 (local Chrome + ffmpeg)')
    sc.add_argument('--input', required=True, help='HTML file or URL (query string allowed)')
    sc.add_argument('--output', required=True, help='New .mp4 path')
    sc.add_argument('--width', type=int, default=1920)
    sc.add_argument('--height', type=int, default=1080)
    sc.add_argument('--fps', type=int, default=30)
    sc.add_argument('--seconds', type=float, help='Fixed length; default runs until the page reports __done()')
    sc.add_argument('--scale', type=int, default=1, help='Device scale factor (2 = crisp 2x frames)')
    sc.add_argument('--realtime', action='store_true', help='Page has no __advance contract; wall-clock capture, not frame-exact')
    sc.add_argument('--poster', help='Also write the final frame as PNG')
    cr = sub.add_parser('crawl', help='Prompt-crawler: map a prompt/SKILL.md into decisions; HTML viewer and optional MP4')
    cr.add_argument('--input', required=True, help='Prompt or SKILL.md to crawl')
    cr.add_argument('--output', required=True, help='New directory for crawl.json, viewer.html (and crawl.mp4)')
    cr.add_argument('--video', action='store_true', help='Also record the crawl animation to MP4')
    cr.add_argument('--speed', type=float, default=3.0, help='Spider speed for video (higher = shorter)')
    cr.add_argument('--fps', type=int, default=30)
    cr.add_argument('--scorer', choices=['heuristic', 'azure'], default='heuristic',
                    help='azure = per-instruction logprob scoring with the highest gpt-*-mini deployment')
    cr.add_argument('--model', help='Override deployment ID (default: highest gpt-*-mini in inventory)')
    cr.add_argument('--no-cascade', action='store_true', help='Single tier only (no escalation to a stronger model)')
    cr.add_argument('--strong-model', help='Override tier-2 deployment ID (default: strongest GPT-5.x non-mini)')
    cr.add_argument('--allow-cloud', action='store_true', help='Consent to sending instruction text to Azure')
    bn = sub.add_parser('bundle', help='Write a per-production manifest.json inventorying artifacts and open decisions; never overwrites')
    bn.add_argument('--production', required=True, help='Production directory to inventory')
    bn.add_argument('--output', help='New manifest path (default: <production>/manifest.json); refuses to overwrite')
    nr = sub.add_parser('narrate', help='Synthesize multi-line narration (azure DragonHD, local f5 voice clone, or kokoro) and build zero-delta timeline.json + narration.wav')
    nr.add_argument('--script', required=True, help='SCRIPT.md (## Title (Frame N)) or JSON lines file')
    nr.add_argument('--output', required=True, help='New output directory for voice/*.wav, narration.wav, and timeline.json')
    nr.add_argument('--engine', choices=['azure', 'f5', 'kokoro', 'qwen3', 'chatterbox'], default='azure',
                    help='qwen3/chatterbox run locally (MLX); models in integrations/voice-models.json, auto-downloaded on first use')
    nr.add_argument('--speech-account', help='Specific SpeechServices account name from inventory (for --engine azure)')
    nr.add_argument('--voice', help='Default voice name (e.g. en-US-Andrew:DragonHDLatestNeural or af_heart)')
    nr.add_argument('--cast', help='JSON object or path mapping speaker names to voice IDs')
    nr.add_argument('--rate', default='-6%', help='SSML prosody rate for Azure Speech (default -6%%)')
    nr.add_argument('--dwell', type=float, default=0.6, help='Default pause in seconds after each line (default 0.6)')
    nr.add_argument('--ref', help='Reference WAV to clone (f5, qwen3, chatterbox)')
    nr.add_argument('--ref-text', help='Exact transcript of --ref (required for qwen3 cloning)')
    nr.add_argument('--lang', default='en', help='Language code for qwen3/chatterbox (e.g. en, he for chatterbox)')
    nr.add_argument('--instruct', help='qwen3 stock voices: style instruction, e.g. "Calm, warm, measured pace."')
    nr.add_argument('--offline', action='store_true', help='qwen3/chatterbox: never download; fail if weights are missing')
    vc = sub.add_parser('voices', help='Local voice models: list stock voices, status, or fetch (bootstrap runtime + weights)')
    vc.add_argument('voices_action', choices=['list', 'fetch'])
    vc.add_argument('--model', action='append', help='Registry key to fetch (default: all)')
    nr.add_argument('--speed', type=float, default=1.0, help='Speech speed for --engine f5 (default 1.0)')
    nr.add_argument('--allow-cloud', action='store_true', help='Consent to sending script text to Azure Speech')
    mc = sub.add_parser('mission-control', help='Render a domain-agnostic Mission Control orbital cockpit HTML (and optional MP4) from typed JSON')
    mc_sub = mc.add_subparsers(dest='mc_action', required=True)
    for action in ('validate', 'render'):
        mcc = mc_sub.add_parser(action)
        mcc.add_argument('--input', required=True, help='Mission Control typed JSON spec')
        if action == 'render':
            mcc.add_argument('--output', required=True, help='New standalone .html path')
            mcc.add_argument('--dwell', type=float, default=2200.0,
                             help='Milliseconds per choreography beat when recorded with showcase (default 2200)')
            mcc.add_argument('--video', help='Optional new .mp4 path to record the cockpit via showcase')
            mcc.add_argument('--style', help='DESIGN.md style name from `creator.py style list` (e.g. linear.app, stripe)')
            mcc.add_argument('--theme', choices=['dark', 'light'], help='Opening theme (default: spec, else style native mode)')
    mcs = mc_sub.add_parser('serve', help='Serve a rendered page on 127.0.0.1 with an Ask pane backed by GitHub Copilot CLI (+ WorkIQ)')
    mcs.add_argument('--page', required=True, help='Rendered Mission Control .html')
    mcs.add_argument('--spec', required=True, help='The spec JSON the page was rendered from (sent to the agent)')
    mcs.add_argument('--workdir', required=True, help='Repo root the agent may read (read-only)')
    mcs.add_argument('--context-dir', action='append', required=True, help='Folder inside --workdir the agent reads (repeatable)')
    mcs.add_argument('--context-file', action='append', default=[], help='Extra file inside --workdir (files the spec cites are added automatically)')
    mcs.add_argument('--port', type=int, default=0, help='Loopback port (default: random free port)')
    mcs.add_argument('--no-workiq', action='store_true', help='Do not attach WorkIQ (live M365) to the agent')
    mcs.add_argument('--model', help='Copilot model id (default: Copilot CLI default)')
    mcs.add_argument('--timeout', type=int, default=300, help='Seconds per question (default 300)')
    mcs.add_argument('--log', help='JSONL log of questions + tool calls (default: next to the page)')
    mcs.add_argument('--copilot', default='copilot', help='Copilot CLI path')
    pc = sub.add_parser('pipeline-control', help='Pipeline monitoring page (flow line + derived insight cards + agent gate) from a run log JSON')
    pc_sub = pc.add_subparsers(dest='pc_action', required=True)
    for action in ('validate', 'render'):
        pcc = pc_sub.add_parser(action)
        pcc.add_argument('--input', required=True, help='Pipeline Control JSON spec with a run log')
        if action == 'render':
            pcc.add_argument('--output', required=True, help='New standalone .html path')
            pcc.add_argument('--style', help='Style from `creator.py style list` (default: spec style, else claude)')
            pcc.add_argument('--theme', choices=['dark', 'light'])
            pcc.add_argument('--video', help='Optional new .mp4 path recorded via showcase')
    wl = sub.add_parser('wall', help='Living-wall hero: past work as drifting columns, pause on hover, lightbox (offline HTML)')
    wl.add_argument('--input', required=True, help='Directory of images/videos (>=3)')
    wl.add_argument('--output', required=True, help='New directory; refuses to overwrite')
    wl.add_argument('--title', required=True, help='One line; second half is dimmed')
    wl.add_argument('--subtitle', default='')
    wl.add_argument('--cta-label', default='')
    wl.add_argument('--cta-href', default='')
    wl.add_argument('--stat', action='append', default=None, metavar='VALUE:LABEL', help='Repeatable; default = derived tile count')
    wl.add_argument('--style', default='noir')
    wl.add_argument('--theme', choices=['dark', 'light'])
    wl.add_argument('--columns', type=int, default=4)
    st = sub.add_parser('style', help='DESIGN.md brand style library (vendored awesome-design-md) mapped to render palettes')
    st_sub = st.add_subparsers(dest='style_action', required=True)
    st_sub.add_parser('list')
    sts = st_sub.add_parser('show')
    sts.add_argument('--style', required=True)
    dc = sub.add_parser('design-check', help='Browser quality gate: contrast, overflow, offline, errors (floor) + AI-look tells (reflex)')
    dc.add_argument('--input', required=True, help='Local .html file')
    dc.add_argument('--report', help='Optional new JSON report path')
    dc.add_argument('--shots', help='Optional directory for desktop/mobile screenshots')
    d = sub.add_parser('discover', help='Read Azure AI accounts/deployments; no deployment changes')
    d.add_argument('--subscription',required=True)
    l = sub.add_parser('models',help='List discovered deployments; presence is not proof of inference access')
    l.add_argument('--capability', choices=['chat','image','transcription','embedding','video','realtime','unknown'])
    p = sub.add_parser('probe',help='Probe local media duration, dimensions, and audio (or --analyze for silence/scene/transcript cues)')
    p.add_argument('source')
    p.add_argument('--analyze', action='store_true', help='Also detect silence intervals and scene-cut timestamps via ffmpeg')
    p.add_argument('--srt', help='Optional local .srt/.vtt file to parse and attach to the probe output')
    e = sub.add_parser('edit',help='Render a reviewed local edit-plan JSON into a new MP4')
    e.add_argument('--plan',required=True)
    e.add_argument('--output',required=True)
    e.add_argument('--profile',choices=['draft','final'],default='final')
    v = sub.add_parser('validate',help='Validate an edit plan against source media without rendering')
    v.add_argument('--plan',required=True)
    dr=sub.add_parser('design-review',help='UX/UI designer agent: reviews explicit screenshots and brief, never edits applications')
    dr.add_argument('--model',required=True)
    dr.add_argument('--brief',required=True,help='Local brief text file')
    dr.add_argument('--images',required=True,nargs='+',help='One to three explicit local PNG/JPEG screenshots')
    dr.add_argument('--output',required=True)
    dr.add_argument('--allow-cloud',action='store_true',help='Consent to screenshot/brief upload to the selected Azure model')
    for name, help_text in [('chat','Invoke a selected Azure chat model'),
                            ('plan','Generate a reviewable edit plan from instructions and technical metadata, NOT visual scene analysis'),
                            ('image','Generate one PNG through a selected GPT Image deployment'),
                            ('transcribe','Upload local audio/video to Whisper and write SRT captions')]:
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument('--model',required=True,help='Exact account/deployment ID from models')
        cmd.add_argument('--allow-cloud',action='store_true',help='Consent to sending this input to Azure and incurring inference usage')
        if name in ('chat','plan','image'):
            cmd.add_argument('--prompt',required=True)
        if name in ('plan','image','transcribe'):
            cmd.add_argument('--output',required=True)
        if name == 'plan':
            cmd.add_argument('--input',required=True,nargs='+',help='Only these local sources may appear in the generated plan')
            cmd.add_argument('--analyze', action='store_true',
                             help='Include local ffmpeg silence intervals and scene-cut timestamps in source_metadata')
            cmd.add_argument('--srt', nargs='*',
                             help='Optional local .srt/.vtt files (matched by order or stem to --input) to include transcript cues')
        if name == 'transcribe':
            cmd.add_argument('--input',required=True)
        if name == 'image':
            cmd.add_argument('--size',default='1024x1024',choices=['1024x1024','1536x1024','1024x1536'])
            cmd.add_argument('--quality',default='low',choices=['low','medium','high'])
    args = parser.parse_args(argv)
    try:
        if args.command == 'fabric':
            from creator_tools import fabric_export
            result = fabric_export.package_site(args.input, args.output, args.name)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command == 'data-story':
            from creator_tools import data_story
            result = data_story.run(args.data_story_action, args.input, getattr(args, 'output', None))
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command == 'motion':
            from creator_tools import motion
            result = motion.doctor() if args.motion_action == 'doctor' else motion.create(args.output, args.title, args.subtitle)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command == 'diagram':
            from creator_tools import diagrams
            if args.diagram_action == 'install':
                result = diagrams.install(args.archive)
            else:
                video_out = getattr(args, 'video', None)
                bridge = bool(getattr(args, 'showcase_bridge', False) or video_out)
                dwell = getattr(args, 'chapter_dwell', 2500.0)
                result = diagrams.run(args.diagram_action, getattr(args, 'input', None),
                                      getattr(args, 'output', None), getattr(args, 'quality', 'showcase'),
                                      showcase_bridge=bridge, chapter_dwell_ms=dwell,
                                      template=getattr(args, 'template', 'full'),
                                      hide=getattr(args, 'hide', None), show=getattr(args, 'show', None),
                                      details=getattr(args, 'details', None))
                if getattr(args, 'embed_snippet', False) and args.diagram_action == 'render':
                    from creator_tools import diagram_templates
                    result['embed_snippet'] = diagram_templates.embed_snippet(Path(result['output']).name)
                if video_out and args.diagram_action == 'render':
                    from creator_tools import showcase
                    result['video'] = showcase.record(result['output'], video_out,
                                                      log=lambda m: print(m, file=sys.stderr))
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command == 'studio':
            from creator_tools.studio import serve
            serve(args.workspace,args.port,args.host)
            return 0
        if args.command == 'showcase':
            from creator_tools import showcase
            result = showcase.record(args.input, args.output, width=args.width, height=args.height, fps=args.fps,
                                     seconds=args.seconds, scale=args.scale, realtime=args.realtime,
                                     log=lambda m: print(m, file=sys.stderr))
            if args.poster:
                result['poster'] = showcase.poster(args.output, args.poster)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command == 'crawl':
            from creator_tools import crawler
            inv = None
            if args.scorer == 'azure':
                if not args.allow_cloud:
                    raise ValueError('--scorer azure sends instruction text to Azure; add --allow-cloud')
                inv = json.loads(Path(args.inventory).expanduser().read_text())
            result = crawler.run(args.input, args.output, video=args.video, speed=args.speed, fps=args.fps,
                                 log=lambda m: print(m, file=sys.stderr), scorer=args.scorer,
                                 inventory=inv, model_id=args.model, cascade=not args.no_cascade,
                                 strong_id=args.strong_model)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command == 'bundle':
            from creator_tools import bundle
            path = bundle.write_manifest(args.production, args.output)
            data = json.loads(Path(path).read_text())
            print(json.dumps({'manifest': path, 'artifacts': len(data['artifacts']),
                              'videos': len(data['videos']), 'cover': data['cover'],
                              'open_decisions': len(data['open_decisions'])}, indent=2))
            return 0
        if args.command == 'voices':
            from creator_tools import local_tts
            if args.voices_action == 'list':
                print(json.dumps(local_tts.status(), indent=2))
            else:
                print(json.dumps(local_tts.fetch(args.model), indent=2))
            return 0
        if args.command == 'narrate':
            from creator_tools import narrate
            if args.engine == 'azure' and not args.allow_cloud:
                raise ValueError('narrate --engine azure sends script text to Azure Speech; add --allow-cloud')
            inv = None
            if args.engine == 'azure' and not (os.environ.get('AZURE_SPEECH_KEY') and os.environ.get('AZURE_SPEECH_REGION')):
                inv = json.loads(Path(args.inventory).expanduser().read_text())
            cast = None
            if args.cast:
                cp = Path(args.cast).expanduser()
                cast = json.loads(cp.read_text() if cp.is_file() else args.cast)
            result = narrate.run(args.script, args.output, engine=args.engine, inventory=inv,
                                 speech_account_name=args.speech_account, cast=cast,
                                 default_voice=args.voice, rate=args.rate, dwell=args.dwell,
                                 ref_wav=args.ref, speed=args.speed, allow_cloud=args.allow_cloud,
                                 ref_text=args.ref_text, lang=args.lang, instruct=args.instruct,
                                 offline=args.offline)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command == 'pipeline-control':
            from creator_tools import pipeline_control
            result = pipeline_control.run(args.pc_action, args.input, getattr(args, 'output', None),
                                          style_name=getattr(args, 'style', None), theme=getattr(args, 'theme', None),
                                          video_output=getattr(args, 'video', None), log=lambda m: print(m, file=sys.stderr))
            print(json.dumps(result, indent=2))
            return 0
        if args.command == 'wall':
            from creator_tools import wall
            stats = None
            if args.stat:
                stats = []
                for s in args.stat:
                    v, sep, k = s.partition(':')
                    if not sep:
                        raise ValueError('--stat must be VALUE:LABEL')
                    stats.append((v, k))
            result = wall.render(args.input, args.output, args.title, args.subtitle, args.cta_label, args.cta_href,
                                 stats, args.style, args.theme, args.columns)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == 'style':
            from creator_tools import styles
            print(json.dumps(styles.run(args.style_action, getattr(args, 'style', None)), indent=2))
            return 0
        if args.command == 'design-check':
            from creator_tools import design_check
            result = design_check.run(args.input, report=args.report, shots=args.shots)
            print(json.dumps(result, indent=2))
            return 0 if result['ok'] else 1
        if args.command == 'mission-control' and args.mc_action == 'serve':
            from creator_tools import mission_ask
            page = Path(args.page).expanduser().resolve()
            cfg = mission_ask.AskConfig(
                args.page, args.spec, args.workdir, args.context_dir, args.context_file,
                copilot=args.copilot, model=args.model, timeout=args.timeout,
                log_path=args.log or page.with_name(page.stem + '.ask-log.jsonl'), use_workiq=not args.no_workiq)
            mission_ask.serve(cfg, port=args.port, log=lambda m: print(m, file=sys.stderr, flush=True))
            return 0
        if args.command == 'mission-control':
            from creator_tools import mission_control
            result = mission_control.run(
                args.mc_action, args.input, getattr(args, 'output', None),
                dwell_ms=getattr(args, 'dwell', 2200.0),
                video_output=getattr(args, 'video', None),
                style_name=getattr(args, 'style', None), theme=getattr(args, 'theme', None),
                log=lambda m: print(m, file=sys.stderr),
            )
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command in ('chat','plan','image','transcribe','design-review') and not args.allow_cloud:
            raise ValueError('Cloud operation requires --allow-cloud. Planning sends instructions and metadata; transcription uploads media; inference may incur charges.')
        if hasattr(args,'output'):
            out = Path(args.output).expanduser().resolve()
            if out.exists():
                raise FileExistsError('Output exists; select a new path')
        if args.command == 'discover':
            result = models.discover(args.subscription)
            path = Path(args.inventory).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(result,indent=2))
            tmp.replace(path)
            print(json.dumps({'inventory':str(path),'accounts':len(result['accounts']),
                              'deployments':len(models.model_rows(result)),
                              'errors':[a['account'] for a in result['accounts'] if a.get('inventory_error')]}))
            return 0
        if args.command in ('probe','edit','validate'):
            if args.command != 'probe':
                plan = models.parse_plan_json(Path(args.plan).expanduser().read_text())
            from creator_tools.editing import probe, analyze_clip, validate_plan, render
            if args.command == 'probe':
                if getattr(args, 'analyze', False) or getattr(args, 'srt', None):
                    result = analyze_clip(args.source, srt_path=getattr(args, 'srt', None))
                else:
                    result = probe(args.source)
            elif args.command == 'validate':
                result = validate_plan(plan)
            else:
                result = render(plan,args.output,profile=args.profile)
        else:
            inventory = json.loads(Path(args.inventory).expanduser().read_text())
            if args.command == 'models':
                result = models.model_rows(inventory)
                if args.capability:
                    result = [r for r in result if r['capability'] == args.capability]
            elif args.command == 'design-review':
                from creator_tools.designer import review
                result=review(inventory,args.model,Path(args.brief).expanduser().read_text(),args.images,args.output,args.allow_cloud)
            elif args.command == 'chat':
                result = {'model':args.model,'text':models.chat(inventory,args.model,[{'role':'user','content':args.prompt}]),'inference_verified':True}
            elif args.command == 'plan':
                from creator_tools.editing import probe, analyze_clip, validate_plan
                sources=[]
                srt_list = getattr(args, 'srt', None) or []
                do_analyze = bool(getattr(args, 'analyze', False) or srt_list)
                for idx, name in enumerate(args.input):
                    path = str(Path(name).expanduser().resolve())
                    srt_for_clip = srt_list[idx] if idx < len(srt_list) else None
                    if do_analyze:
                        sources.append({'path':path,**analyze_clip(path, srt_path=srt_for_clip)})
                    else:
                        sources.append({'path':path,**probe(path)})
                plan = models.make_plan(inventory,args.model,args.prompt,sources)
                validate_plan(plan)
                path = write_json_new(args.output,plan)
                op_kind = 'content-aware-edit-plan' if do_analyze else 'metadata-only-edit-plan'
                write_json_new(path+'.provenance.json',{'operation':op_kind,'model':args.model,
                                                       'prompt':args.prompt,'source_metadata':sources,
                                                       'rendered':False,'review_required':True})
                result = {'plan':path,'review_required':True,'rendered':False}
            elif args.command == 'image':
                from creator_tools.assets import generate_image
                result = generate_image(inventory,args.model,args.prompt,args.output,args.size,args.quality)
            elif args.command == 'transcribe':
                from creator_tools.assets import transcribe
                result = transcribe(inventory,args.model,args.input,args.output)
        print(json.dumps(result,indent=2,allow_nan=False))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print('Creator: '+str(exc),file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
