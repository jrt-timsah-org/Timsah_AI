"""Local, configuration-driven YOLO detection workspace."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter
from datetime import datetime
from zipfile import ZipFile

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
DATASETS_DIR = WORKSPACE / 'datasets' / 'yolo_lab'
MODELS_DIR = WORKSPACE / 'weights' / 'yolo_lab' / 'pretrained'
RUNS_DIR = WORKSPACE / 'outputs' / 'yolo_lab' / 'runs'
LOGS_DIR = WORKSPACE / 'outputs' / 'yolo_lab' / 'logs'
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff'}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')
    tmp.replace(path)


def slug(value):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', value):
        raise ValueError('Names must contain only letters, numbers, _ and -.')
    return value


def data_path(value):
    path = Path(value).expanduser()
    if path.exists():
        return (path / 'data.yaml' if path.is_dir() else path).resolve()
    path = DATASETS_DIR / value / 'data.yaml'
    if not path.exists():
        raise FileNotFoundError(f'Dataset not registered: {value}')
    return path.resolve()


def audit(data):
    from PIL import Image
    cfg = yaml.safe_load(data.read_text())
    names = cfg['names']
    names = [names[i] for i in sorted(names)] if isinstance(names, dict) else names
    if not names or cfg.get('nc', len(names)) != len(names):
        raise ValueError('nc and names are inconsistent')
    base = Path(cfg.get('path', data.parent))
    if not base.is_absolute():
        base = data.parent / base
    report = {'data': str(data), 'names': names, 'splits': {}, 'warnings': []}
    hashes = {}
    groups = {}
    errors = []
    for split in ('train', 'val', 'test'):
        if split not in cfg:
            continue
        location = cfg[split]
        if not isinstance(location, str):
            raise ValueError('The dataset importer requires a directory per split.')
        image_dir = (base / location).resolve()
        if image_dir.name != 'images':
            raise ValueError(f'{split}: expected an images directory: {image_dir}')
        label_dir = image_dir.parent / 'labels'
        images = sorted(p for p in image_dir.rglob('*') if p.suffix.lower() in IMAGE_SUFFIXES)
        counts = Counter()
        empty = 0
        shapes = Counter()
        split_hashes = set()
        split_groups = set()
        if not images:
            errors.append(f'{split}: no images')
        for image in images:
            try:
                with Image.open(image) as im:
                    shapes[f'{im.width}x{im.height}'] += 1
                    im.verify()
                split_hashes.add(hashlib.sha256(image.read_bytes()).hexdigest())
                split_groups.add(image.name.split('.rf.')[0])
                label = label_dir / image.relative_to(image_dir).with_suffix('.txt')
                rows = label.read_text().splitlines()
                if not any(row.strip() for row in rows):
                    empty += 1
                for line, row in enumerate(rows, 1):
                    if not row.strip():
                        continue
                    parts = [float(x) for x in row.split()]
                    if len(parts) != 5:
                        raise ValueError(f'{label.name}:{line}: expected class x y w h')
                    cls, x, y, w, h = parts
                    if not all(math.isfinite(v) for v in parts):
                        raise ValueError(f'{label.name}:{line}: non-finite label')
                    if cls != int(cls) or not 0 <= cls < len(names):
                        raise ValueError(f'{label.name}:{line}: invalid class {cls}')
                    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                        raise ValueError(f'{label.name}:{line}: invalid normalized box')
                    counts[int(cls)] += 1
            except Exception as exc:
                errors.append(f'{image.name}: {exc}')
        image_stems = {p.relative_to(image_dir).with_suffix('') for p in images}
        orphan_labels = [p for p in label_dir.rglob('*.txt') if p.relative_to(label_dir).with_suffix('') not in image_stems]
        if orphan_labels:
            errors.append(f'{split}: {len(orphan_labels)} labels without an image')
        report['splits'][split] = {
            'images': len(images), 'background_images': empty,
            'boxes_per_class': {str(i): counts[i] for i in range(len(names))},
            'image_sizes': dict(shapes),
            'exact_duplicate_images_within_split': len(images) - len(split_hashes),
            'source_groups': len(split_groups),
        }
        hashes[split] = split_hashes
        groups[split] = split_groups
    for first, second in (('train', 'val'), ('train', 'test'), ('val', 'test')):
        overlap = len(hashes.get(first, set()) & hashes.get(second, set()))
        source_overlap = len(groups.get(first, set()) & groups.get(second, set()))
        if overlap or source_overlap:
            report['warnings'].append(f'{first}/{second}: {overlap} identical images, {source_overlap} shared filename source groups; metrics may be optimistic.')
    for split, info in report['splits'].items():
        missing = [names[int(i)] for i, count in info['boxes_per_class'].items() if count == 0]
        if missing:
            report['warnings'].append(f'{split}: classes without boxes: {missing}')
    report['errors'] = errors[:30]
    report['error_count'] = len(errors)
    write_json(data.parent / 'audit.json', report)
    if errors:
        raise ValueError(f'Dataset audit failed with {len(errors)} errors; see {data.parent / "audit.json"}')
    return report


def normalize_detection_labels(root):
    """Convert YOLO polygon rows to enclosing boxes, retaining source files."""
    changes = []
    for split in ('train', 'valid', 'val', 'test'):
        for label in (root / split / 'labels').rglob('*.txt'):
            source = label.read_text()
            output = []
            polygons = 0
            for line, row in enumerate(source.splitlines(), 1):
                if not row.strip():
                    continue
                values = [float(x) for x in row.split()]
                if len(values) == 5:
                    output.append(row)
                    continue
                if len(values) < 7 or len(values) % 2 != 1:
                    raise ValueError(f'{label}:{line}: invalid YOLO polygon row')
                cls, coordinates = values[0], values[1:]
                if not all(math.isfinite(x) and 0 <= x <= 1 for x in coordinates):
                    raise ValueError(f'{label}:{line}: invalid normalized polygon coordinates')
                xs, ys = coordinates[::2], coordinates[1::2]
                x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
                if x1 == x2 or y1 == y2:
                    raise ValueError(f'{label}:{line}: degenerate polygon')
                output.append(' '.join(f'{x:.12g}' for x in (cls, (x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1)))
                polygons += 1
            if polygons:
                changes.append((label, source, '\n'.join(output) + '\n', polygons))
    # Parse the whole dataset before making any changes.
    for label, source, converted, _ in changes:
        backup = root / 'labels.source' / label.relative_to(root)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            backup.write_text(source)
        label.write_text(converted)
    report_path = root / 'label-conversion.json'
    report = {'task': 'detect', 'operation': 'YOLO polygon to enclosing bounding box', 'files_converted': len(changes), 'polygons_converted': sum(item[3] for item in changes), 'original_labels': str(root / 'labels.source')}
    if changes or not report_path.exists():
        write_json(report_path, report)
    return report


def import_dataset(args):
    name = slug(args.name)
    link = DATASETS_DIR / name
    target = (Path(args.storage).expanduser() / name).resolve() if args.storage else link
    if link.exists() or link.is_symlink() or target.exists():
        raise FileExistsError(f'Dataset already exists: {name}. Use a different version name.')
    archive = Path(args.zip).expanduser().resolve()
    with ZipFile(archive) as z:
        members = {}
        for info in z.infolist():
            rel = Path(info.filename)
            if rel.is_absolute() or '..' in rel.parts or '\\' in info.filename or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f'Unsafe archive entry: {info.filename}')
            if info.is_dir():
                continue
            if info.filename in members and (members[info.filename].CRC, members[info.filename].file_size) != (info.CRC, info.file_size):
                raise ValueError(f'Conflicting duplicate archive entry: {info.filename}')
            members[info.filename] = info
        yamls = [s for s in members if Path(s).name in ('data.yaml', 'data.yml')]
        if len(yamls) != 1:
            raise ValueError('Archive must contain exactly one data.yaml/data.yml')
        prefix = Path(yamls[0]).parent
        original = yaml.safe_load(z.read(members[yamls[0]]))
        target.mkdir(parents=True)
        for member, info in members.items():
            try:
                relative = Path(member).relative_to(prefix)
            except ValueError:
                continue
            out = target / relative
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as source, out.open('wb') as dest:
                import shutil
                shutil.copyfileobj(source, dest)
    (target / 'data.source.yaml').write_text(yaml.safe_dump(original, sort_keys=False))
    normalized = dict(original)
    normalized['path'] = str(target)
    for split, candidates in {'train': ('train',), 'val': ('valid', 'val'), 'test': ('test',)}.items():
        folder = next((s for s in candidates if (target / s / 'images').is_dir()), None)
        if folder:
            normalized[split] = f'{folder}/images'
        elif split in ('train', 'val'):
            raise ValueError(f'Missing required {split}/images directory')
        else:
            normalized.pop(split, None)
    normalized.pop('roboflow', None)
    (target / 'data.yaml').write_text(yaml.safe_dump(normalized, sort_keys=False, allow_unicode=True))
    normalize_detection_labels(target)
    report = audit(target / 'data.yaml')
    write_json(target / 'manifest.json', {'name': name, 'archive': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'imported_at': datetime.now().astimezone().isoformat(), 'storage': str(target)})
    if target != link:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target, target_is_directory=True)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def doctor():
    import torch
    import ultralytics
    print(json.dumps({'python': sys.version, 'torch': torch.__version__, 'ultralytics': ultralytics.__version__, 'cuda_runtime': torch.version.cuda, 'cuda_available': torch.cuda.is_available(), 'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, 'cpu_count': os.cpu_count()}, indent=2))
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU unavailable; GPU training is required by this workspace.')
    value = torch.ones(16, device='cuda') * 2
    torch.cuda.synchronize()
    assert value.sum().item() == 32


def train(args):
    from ultralytics import YOLO
    import torch
    name = slug(args.name or datetime.now().strftime('%Y%m%d-%H%M%S'))
    run = RUNS_DIR / name
    if run.exists() and not args.resume:
        raise FileExistsError(f'Run already exists: {run}')
    cfg = yaml.safe_load(Path(args.config).read_text())
    for item in args.set:
        key, value = item.split('=', 1)
        cfg[key] = yaml.safe_load(value)
    if not torch.cuda.is_available() and str(cfg.get('device')) != 'cpu':
        raise RuntimeError('CUDA is not available. Run ./yolo-lab doctor.')
    cfg['data'] = str(data_path(args.data))
    cfg.update(project=str(RUNS_DIR), name=name, exist_ok=True)
    model_name = cfg.pop('model')
    if not Path(str(model_name)).is_absolute():
        model_name = MODELS_DIR / model_name
    checkpoint = Path(args.resume).expanduser().resolve() if args.resume else model_name
    if args.resume and checkpoint.parent.parent != run:
        raise ValueError('--name must match the run containing the resume checkpoint')
    run.mkdir(parents=True, exist_ok=True)
    write_json(run / 'launch.json', {'arguments': cfg, 'model': str(checkpoint), 'started_at': datetime.now().astimezone().isoformat(), 'python': sys.executable, 'torch': torch.__version__})
    state = {'state': 'starting', 'pid': os.getpid(), 'name': name, 'run': str(run), 'started_at': datetime.now().astimezone().isoformat()}
    def update(**values):
        state.update(values, updated_at=datetime.now().astimezone().isoformat())
        write_json(run / 'status.json', state)
    update()
    try:
        model = YOLO(str(checkpoint))
        model.add_callback('on_train_start', lambda trainer: update(state='training', epochs=trainer.epochs, batch_size=trainer.batch_size))
        model.add_callback('on_train_epoch_start', lambda trainer: update(state='training', current_epoch=trainer.epoch + 1))
        def epoch_end(trainer):
            update(state='training', epoch=trainer.epoch + 1, epochs=trainer.epochs, metrics=trainer.metrics)
            print(f'\nLAB_EPOCH {trainer.epoch + 1}/{trainer.epochs} {trainer.metrics}', flush=True)
        model.add_callback('on_fit_epoch_end', epoch_end)
        if args.resume:
            model.train(resume=True, device=cfg['device'], workers=cfg['workers'])
        else:
            model.train(**cfg)
        best = run / 'weights' / 'best.pt'
        update(state='evaluating', best=str(best))
        if 'test' in yaml.safe_load(Path(cfg['data']).read_text()):
            result = YOLO(str(best)).val(data=cfg['data'], split='test', imgsz=cfg['imgsz'], batch=16, device=cfg['device'], workers=cfg['workers'], project=str(run), name='test', plots=True)
            write_json(run / 'test-metrics.json', result.results_dict)
        write_json(RUNS_DIR / 'latest.json', {'name': name, 'best': str(best), 'last': str(run / 'weights' / 'last.pt')})
        update(state='completed', completed_at=datetime.now().astimezone().isoformat())
    except KeyboardInterrupt:
        update(state='stopped', message='Interrupted. Resume from weights/last.pt when available.')
        raise
    except BaseException as exc:
        update(state='failed', error=str(exc), traceback=traceback.format_exc())
        raise


def start(args):
    name = slug(args.name or datetime.now().strftime('%Y%m%d-%H%M%S'))
    if (RUNS_DIR / name).exists() and not args.resume:
        raise FileExistsError(f'Run already exists: {name}')
    cmd = [str(ROOT / 'yolo-lab'), 'train', '--data', args.data, '--config', args.config, '--name', name]
    for item in args.set:
        cmd += ['--set', item]
    if args.resume:
        cmd += ['--resume', args.resume]
    logfile = LOGS_DIR / f'{name}-{datetime.now():%Y%m%d-%H%M%S}.log'
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open('ab') as log:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    write_json(LOGS_DIR / f'{name}.json', {'pid': proc.pid, 'name': name, 'log': str(logfile), 'command': cmd})
    time.sleep(2)
    if proc.poll() is not None:
        raise RuntimeError(f'Training exited immediately ({proc.returncode}); see {logfile}')
    print(json.dumps({'pid': proc.pid, 'name': name, 'log': str(logfile)}, indent=2))


def status(args):
    launch = json.loads((LOGS_DIR / f'{slug(args.name)}.json').read_text())
    path = RUNS_DIR / args.name / 'status.json'
    state = json.loads(path.read_text()) if path.exists() else {'state': 'launching'}
    state['process_alive'] = False
    if launch.get('pid') is not None:
        try:
            command = Path(f"/proc/{launch['pid']}/cmdline").read_bytes()
            state['process_alive'] = str(ROOT / 'scripts' / 'lab.py').encode() in command
        except (FileNotFoundError, ProcessLookupError):
            pass
    state['log'] = launch['log']
    results = RUNS_DIR / args.name / 'results.csv'
    if results.exists():
        with results.open() as f:
            rows = list(csv.DictReader(f))
        if rows:
            state['last_results'] = {k.strip(): v.strip() for k, v in rows[-1].items()}
    print(json.dumps(state, indent=2, ensure_ascii=False))


def stop(args):
    meta = json.loads((LOGS_DIR / f'{slug(args.name)}.json').read_text())
    pid = meta.get('pid')
    if pid is None:
        raise RuntimeError('This is an imported run snapshot, not a process started here.')
    # Guard against a recycled PID before sending a signal to its process group.
    command = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\x00', b' ').decode()
    if str(ROOT / 'scripts' / 'lab.py') not in command or args.name not in command:
        raise RuntimeError('PID no longer belongs to this training run')
    os.kill(pid, signal.SIGINT)
    print('Stop requested. Use the latest saved weights/last.pt to resume.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    p = sub.add_parser('import')
    p.add_argument('zip'); p.add_argument('--name', required=True)
    p.add_argument('--storage', help='Optional fast disk parent; workspace gets a symlink')
    p = sub.add_parser('audit'); p.add_argument('--data', required=True)
    p = sub.add_parser('normalize'); p.add_argument('--data', required=True)
    for command in ('train', 'start'):
        p = sub.add_parser(command)
        p.add_argument('--data', required=True); p.add_argument('--name')
        p.add_argument('--config', default=str(ROOT / 'configs' / 'default.yaml'))
        p.add_argument('--set', action='append', default=[], metavar='KEY=VALUE')
        p.add_argument('--resume', help='Path to interrupted weights/last.pt')
    for command in ('status', 'stop'):
        p = sub.add_parser(command); p.add_argument('name')
    p = sub.add_parser('predict'); p.add_argument('--weights', required=True)
    p.add_argument('--source', required=True); p.add_argument('--conf', type=float, default=0.25)
    p = sub.add_parser('export'); p.add_argument('--weights', required=True)
    p.add_argument('--format', default='onnx'); p.add_argument('--imgsz', type=int, default=512)
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == 'doctor': doctor()
    elif args.command == 'import': import_dataset(args)
    elif args.command == 'audit': print(json.dumps(audit(data_path(args.data)), indent=2, ensure_ascii=False))
    elif args.command == 'normalize': print(json.dumps(normalize_detection_labels(data_path(args.data).parent), indent=2, ensure_ascii=False))
    elif args.command == 'train': train(args)
    elif args.command == 'start': start(args)
    elif args.command == 'status': status(args)
    elif args.command == 'stop': stop(args)
    elif args.command == 'predict':
        from ultralytics import YOLO
        YOLO(args.weights).predict(source=args.source, conf=args.conf, save=True, project=str(RUNS_DIR / 'predict'))
    elif args.command == 'export':
        from ultralytics import YOLO
        YOLO(args.weights).export(format=args.format, imgsz=args.imgsz)


if __name__ == '__main__':
    main()
