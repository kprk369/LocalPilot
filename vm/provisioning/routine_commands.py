"""Operator-approved fixed grammar, implemented without a shell or user code."""
import os
from pathlib import Path, PurePosixPath
import shlex
import stat
import sys
VERSION='routine-v1'
LIMIT=65536

def parse(command):
    if not isinstance(command,str) or len(command)>4096 or any(ord(c)<32 or c in ';&|><`$\\*?[]{}~' for c in command):
        raise ValueError('This command needs manual approval')
    words=shlex.split(command,posix=True)
    if not words:raise ValueError('Empty command')
    name,*args=words
    if name in ('pwd','whoami') and not args:return name,[],None
    if name=='python3' and args==['--version']:return name,args,None
    if name=='echo' and all(not a.startswith('-') for a in args):return name,args,None
    flags=[]
    allowed={'ls':{'-a','-l','-la','-al'},'cat':set(),'head':set(),'tail':set(),'wc':{'-l','-w','-c'},'mkdir':{'-p'}}
    if name not in allowed:raise ValueError('This command needs manual approval')
    if name in ('head','tail') and len(args)>=2 and args[0]=='-n':
        if not args[1].isdigit() or not 1<=int(args[1])<=200:raise ValueError('Invalid line limit')
        flags=args[:2];args=args[2:]
    elif args and args[0].startswith('-'):
        if args[0] not in allowed[name]:raise ValueError('Unsupported option')
        flags=[args.pop(0)]
    if name=='ls' and not args:args=['.']
    if len(args)!=1 or args[0].startswith('-'):raise ValueError('One relative workspace path is required')
    relative=PurePosixPath(args[0])
    if relative.is_absolute() or '..' in relative.parts or ':' in args[0]:raise ValueError('Path must stay in the workspace')
    return name,flags,args[0]

def eligible(command):
    try:parse(command);return True
    except (ValueError,TypeError):return False

def execute(command,workspace):
    name,flags,path=parse(command)
    root=Path(workspace).resolve()
    target=(root/path).resolve() if path is not None else None
    if target is not None:target.relative_to(root)
    if name=='pwd':text=str(root)+'\n'
    elif name=='whoami':
        import pwd
        text=pwd.getpwuid(os.getuid()).pw_name+'\n'
    elif name=='python3':text='Python '+sys.version.split()[0]+'\n'
    elif name=='echo':text=' '.join(flags)+'\n'
    elif name=='mkdir':target.mkdir(parents=flags==['-p'],exist_ok=flags==['-p']);text=''
    elif name=='ls':
        if not target.is_dir():raise ValueError('List a workspace directory')
        # Bound listing memory as well as output. Sort the sampled entries.
        entries=[];limited=False
        with os.scandir(target) as iterator:
            for entry in iterator:
                if not entry.name.startswith('.') or flags in (['-a'],['-la'],['-al']):
                    if len(entries)==200:limited=True;break
                    info=entry.stat(follow_symlinks=False)
                    entries.append((entry.name,info))
        lines=[]
        for entry,info in sorted(entries):
            lines.append((stat.filemode(info.st_mode)+' '+str(info.st_size)+' ' if flags in (['-l'],['-la'],['-al']) else '')+entry)
        text='\n'.join(lines)+ ('\n' if lines else '')
        if limited:text+='[Listing limited to 200 entries]\n'
    else:
        fd=os.open(target,os.O_RDONLY|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(fd,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Read regular workspace files only')
            data=stream.read(LIMIT+1)
        if len(data)>LIMIT:raise ValueError('File exceeds routine read limit')
        if name=='cat':text=data.decode('utf-8',errors='replace')
        elif name in ('head','tail'):
            count=int(flags[1]) if flags else 10;lines=data.decode('utf-8',errors='replace').splitlines(keepends=True)
            text=''.join(lines[:count] if name=='head' else lines[-count:])
        else:
            values={'-l':data.count(b'\n'),'-w':len(data.split()),'-c':len(data)}
            text=(' '.join(str(values[f]) for f in ('-l','-w','-c')) if not flags else str(values[flags[0]]))+' '+path+'\n'
    encoded=text.encode('utf-8')
    return {'ok':True,'exit_code':0,'output':encoded[:LIMIT].decode('utf-8',errors='replace'),'truncated':len(encoded)>LIMIT,'timed_out':False,'execution_mode':VERSION}
