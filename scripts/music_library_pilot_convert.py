#!/usr/bin/env python3
"""Bound, private, no-clobber codec construction. No models or verdicts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

FFMPEG = Path('/opt/homebrew/bin/ffmpeg')
FFPROBE = Path('/opt/homebrew/bin/ffprobe')
ROOT = Path('.tmp/music-verdict-v1')
CASES = [('mp3', n) for n in (128,192,320)] + [('aac', n) for n in (128,192,256)]
MAX_EXTRA_FRAMES = 2048


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def save(path, obj):
    with path.open('x') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')


def run(args, data=None):
    env = {k:v for k,v in os.environ.items() if not k.startswith('DYLD_')}
    env['LC_ALL'] = 'C'
    r = subprocess.run([str(a) for a in args], input=data, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=180, env=env)
    if r.returncode:
        raise RuntimeError(r.stderr.decode(errors='replace')[-2000:])
    return r.stdout


def ff(args, data=None):
    return run([FFMPEG,'-hide_banner','-nostdin','-v','error','-n',
                '-filter_threads','1',*args], data)


def probe(path):
    d = json.loads(run([FFPROBE,'-v','error','-select_streams','a','-show_entries',
                       'stream=codec_name,sample_rate,channels,bits_per_sample,bits_per_raw_sample,bit_rate,duration:format=duration,size,bit_rate',
                       '-of','json',path]))
    if len(d.get('streams',[])) != 1:
        raise ValueError('one audio stream required')
    return d


def pcm_stride(bits, channels):
    if type(bits) is not int or bits not in (16, 24) or type(channels) is not int or channels not in (1, 2):
        raise ValueError('expected native mono/stereo 16/24-bit PCM')
    return channels * (bits // 8)


def validate_stream(path, rate, codec=None, *, channels=2):
    p = probe(path); s = p['streams'][0]
    if (type(channels) is not int or channels not in (1, 2)
            or int(s['sample_rate']) != rate or s['channels'] != channels):
        raise ValueError('native rate/channel mismatch')
    if codec is not None and s['codec_name'] != codec:
        raise ValueError('codec mismatch')
    return p


def decode(path, bits, *, container=None):
    if bits not in (16,24):
        raise ValueError('unsupported depth')
    if container not in (None, 'wav', 'flac'):
        raise ValueError('unexpected PCM demuxer')
    demux = ['-f', container] if container is not None else []
    return ff([*demux, '-i',path,'-map','0:a:0','-vn','-threads','1',
               '-c:a',f'pcm_s{bits}le','-f',f's{bits}le','pipe:1'])


def trim(raw, bits, frames, *, channels=2):
    stride = pcm_stride(bits, channels)
    if len(raw) % stride:
        raise ValueError('partial decoded frame')
    actual = len(raw)//stride
    if not frames <= actual <= frames + MAX_EXTRA_FRAMES:
        raise ValueError('decoded frame count outside fixed padding allowance')
    return raw[:frames*stride], actual-frames


def from_pcm(raw, path, rate, bits, flac=False, *, channels=2):
    if len(raw) % pcm_stride(bits, channels):
        raise ValueError('partial input frame')
    codec = ['-c:a','flac','-compression_level','5'] if flac else ['-c:a',f'pcm_s{bits}le']
    ff(['-f',f's{bits}le','-ar',str(rate),'-ac',str(channels),'-i','pipe:0',
        '-map_metadata','-1','-threads','1','-fflags','+bitexact',
        '-flags:a','+bitexact',*codec,path], raw)


def encode(source, output, family, bitrate, *, known_wav=False):
    if (family,bitrate) not in CASES:
        raise ValueError('unplanned codec setting')
    opts = (['-c:a','libmp3lame','-abr','0','-reservoir','1','-joint_stereo','1',
             '-compression_level','2','-write_xing','1','-id3v2_version','0']
            if family == 'mp3' else
            ['-c:a','aac','-profile:a','aac_low','-aac_coder','twoloop',
             '-aac_is','1','-aac_pns','1','-aac_tns','1'])
    demux = ['-f', 'wav'] if known_wav else []
    ff([*demux, '-i',source,'-map','0:a:0','-vn','-map_metadata','-1','-threads','1',
        '-fflags','+bitexact','-flags:a','+bitexact',*opts,'-b:a',f'{bitrate}k',output])


def toolchain():
    pending = [FFMPEG, FFPROBE]; seen = {}; system = set()
    while pending:
        p = pending.pop().resolve()
        if str(p) in seen:
            continue
        output = run(['/usr/bin/otool','-L',p]).decode()
        seen[str(p)] = sha(p)
        for line in output.splitlines()[1:]:
            dep = line.strip().split(' (',1)[0]
            if dep.startswith(('/usr/lib/','/System/Library/')):
                system.add(line.strip())
            elif dep.startswith('/opt/homebrew/'):
                pending.append(Path(dep))
            else:
                raise ValueError('unresolved non-system shared-library dependency')
    return {'files':dict(sorted(seen.items())), 'system_dependencies':sorted(system),
            'os':run(['/usr/bin/sw_vers']).decode(),
            'architecture':run(['/usr/bin/uname','-m']).decode().strip(),
            'ffmpeg_version':run([FFMPEG,'-version']).decode(),
            'ffprobe_version':run([FFPROBE,'-version']).decode()}


def verify_toolchain(binding):
    if toolchain() != binding:
        raise ValueError('conversion toolchain changed')


def private_output(path):
    if not path.resolve().is_relative_to(ROOT.resolve()) or path.resolve()==ROOT.resolve():
        raise ValueError('new output must be inside private pilot storage')
    path.mkdir(exist_ok=False)


def storage_guard(reserve=128*1024**2):
    used = sum(p.stat().st_size for d in ROOT.glob('library-*') if d.is_dir()
               for p in d.rglob('*') if p.is_file())
    if used+reserve > 10*1024**3 or shutil.disk_usage(ROOT).free-reserve < 100*1024**3:
        raise ValueError('pilot generated-size or filesystem free-space limit')


def smoke(output):
    import numpy as np
    private_output(output)
    binding = toolchain(); save(output/'toolchain.json',binding)
    records = []
    for rate in (44100,48000):
        for bits in (16,24):
            frames = rate*3
            points = [round(rate*t) for t in (0.3,1.3,2.5)]
            x = np.zeros((frames,2),dtype=np.int32)
            for i,point in enumerate(points):
                x[point] = [2**(bits-2),(-1)**i*2**(bits-2)]
            if bits==16:
                raw=x.astype('<i2').tobytes()
            else:
                raw=x.astype('<i4').view(np.uint8).reshape(-1,4)[:,:3].copy().tobytes()
            stem=f'{rate}-{bits}'
            wav=output/f'{stem}.wav'; lossless=output/f'{stem}.flac'
            from_pcm(raw,wav,rate,bits);from_pcm(raw,lossless,rate,bits,True)
            assert decode(wav,bits)==raw and decode(lossless,bits)==raw
            for family,bitrate in CASES:
                encoded=output/f'{stem}-{family}-{bitrate}.{"mp3" if family=="mp3" else "m4a"}'
                encode(wav,encoded,family,bitrate)
                p=validate_stream(encoded,rate,family)
                decoded,extra=trim(decode(encoded,bits),bits,frames)
                if bits==16:
                    samples=np.frombuffer(decoded,dtype='<i2').reshape(-1,2).astype(np.int32)
                else:
                    b=np.frombuffer(decoded,dtype=np.uint8).reshape(-1,3).astype(np.int32)
                    samples=(b[:,0]|b[:,1]<<8|b[:,2]<<16)
                    samples=((samples ^ 0x800000)-0x800000).reshape(-1,2)
                offsets=[]
                for point in points:
                    for channel in (0,1):
                        offset=int(np.argmax(np.abs(samples[point-64:point+65,channel])))-64
                        if abs(offset)>2:
                            raise ValueError('impulse timing exceeds prespecified two-sample tolerance')
                        offsets.append(offset)
                records.append({'rate':rate,'bits':bits,'family':family,'bitrate':bitrate,
                                'trailing_frames_removed':extra,'peak_offsets_samples':offsets,
                                'encoded_sha256':sha(encoded),'probe':p})
    verify_toolchain(binding)
    save(output/'smoke.json',{'passed':True,'cases':records,'wrapper_pairs':4,
         'time_origin':'FFmpeg automatic container/skip-sample delay handling; no leading crop',
         'trailing_policy':'truncate only excess tail frames; never pad short output',
         'peak_tolerance_samples':2,'runner_sha256':sha(Path(__file__)),
         'toolchain_sha256':sha(output/'toolchain.json')})
    print(json.dumps({'smoke_cases_passed':len(records),'wrapper_pairs_exact':4}))


def construct(execution, output):
    record=json.loads(execution.read_text())
    if record['runner_sha256'] != sha(Path(__file__)):
        raise ValueError('runner binding mismatch')
    for item in record['bound_files']:
        if sha(item['path']) != item['sha256']:
            raise ValueError('input/control record changed')
    binding=json.loads(Path(record['toolchain']).read_text());verify_toolchain(binding)
    check=json.loads(Path(record['smoke']).read_text())
    if not check['passed'] or check['runner_sha256'] != sha(Path(__file__)):
        raise ValueError('matching technical preflight required')
    library=json.loads(Path(record['technical_report']).read_text())['rows']
    synthroot=Path(record['synthetic_directory'])
    synth=json.loads((synthroot/'manifest.json').read_text())['records']
    inputs=[]
    for i,r in enumerate(library):
        s=r['header']['streams'][0]
        inputs.append({'id':f'library-{i:02}','path':r['path'],'sha256':r['input_sha256'],
                       'rate':int(s['sample_rate']),'bits':int(s['bits_per_sample']),
                       'origin':'unknown_history','component':r['metadata_component_id']})
    for i,r in enumerate(synth):
        inputs.append({'id':f'synthetic-{i:02}','path':str(synthroot/r['file']),
                       'sha256':r['file_sha256'],'rate':r['parameters']['sample_rate'],
                       'bits':16,'origin':'controlled_synthesis_no_lossy_stage',
                       'component':f'synthetic-family-{r["parameters"]["family_index"]}'})
    if len(library)!=24 or len(synth)!=24:
        raise ValueError('exact fixed input counts required')
    storage_guard();private_output(output)
    save(output/'execution-inputs.json',{'execution_sha256':sha(execution),'inputs':inputs})
    completed=[]
    for source in inputs:
        original=Path(source['path'])
        if sha(original)!=source['sha256']:
            raise ValueError('source hash changed')
        rate,bits=source['rate'],source['bits'];frames=120*rate
        validate_stream(original,rate,f'pcm_s{bits}le')
        directory=output/source['id'];directory.mkdir()
        storage_guard()
        # Uniform PCM extraction path for both origins, no normalization/resampling.
        raw=ff(['-i',original,'-map','0:a:0','-vn','-af',f'atrim=end_sample={frames},asetpts=N/SR/TB',
                '-threads','1','-c:a',f'pcm_s{bits}le','-f',f's{bits}le','pipe:1'])
        if len(raw)!=frames*2*(bits//8):
            raise ValueError('source shorter than fixed excerpt')
        baseline=directory/'baseline.wav';control=directory/'baseline.flac'
        from_pcm(raw,baseline,rate,bits);from_pcm(raw,control,rate,bits,True)
        if decode(baseline,bits)!=raw or decode(control,bits)!=raw:
            raise ValueError('baseline WAV/FLAC PCM inequality')
        entries=[{'case':'baseline','history':source['origin'],'files':[
            {'file':p.name,'sha256':sha(p)} for p in (baseline,control)],
            'pcm_sha256':hashlib.sha256(raw).hexdigest()}]
        for family,bitrate in CASES:
            storage_guard()
            stem=f'{family}-{bitrate}'
            encoded=directory/f'{stem}.{ "mp3" if family=="mp3" else "m4a"}'
            decoded_path=directory/f'{stem}.flac'
            encode(baseline,encoded,family,bitrate)
            p=validate_stream(encoded,rate,family)
            decoded,extra=trim(decode(encoded,bits),bits,frames)
            from_pcm(decoded,decoded_path,rate,bits,True)
            if decode(decoded_path,bits)!=decoded:
                raise ValueError('decoded FLAC does not preserve PCM')
            entries.append({'case':stem,'history':'known_added_lossy_stage',
                'prior_history':source['origin'],'trailing_frames_removed':extra,
                'frames':frames,'bits':bits,'encoded_probe':p,
                'container_inclusive_bitrate_bps':encoded.stat().st_size*8/120,
                'encoded_file':encoded.name,'encoded_sha256':sha(encoded),
                'decoded_file':decoded_path.name,'decoded_sha256':sha(decoded_path),
                'pcm_sha256':hashlib.sha256(decoded).hexdigest()})
        if sha(original)!=source['sha256']:
            raise ValueError('source preservation failed')
        save(directory/'manifest.json',{'source':source,'interval_seconds':[0,120],
             'cases':entries,'source_preserved':True})
        completed.append({'id':source['id'],'manifest_sha256':sha(directory/'manifest.json')})
        print(json.dumps({'completed_sources':len(completed),'target':48}),flush=True)
    verify_toolchain(binding);storage_guard(0)
    save(output/'manifest.json',{'schema_version':1,'study_id':'music-library-pilot-v1',
         'execution_sha256':sha(execution),'sources':completed,'scores_generated':False})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('smoke','construct'))
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--execution',type=Path)
    a=p.parse_args()
    if a.mode=='smoke':smoke(a.output)
    elif a.execution is None:p.error('--execution required')
    else:construct(a.execution,a.output)


if __name__=='__main__':main()
