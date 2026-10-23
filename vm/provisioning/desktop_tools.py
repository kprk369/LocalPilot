"""Short, serialized X11 actions in the existing pilot desktop, never a new session."""
import base64
import fcntl
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid
from PIL import Image

STATE = Path.home()/'.local/state/localpilot'
WORKSPACE = Path.home()/'Workspace'
INPUTS = {'desktop_browser_open','desktop_open_application','desktop_click','desktop_type','desktop_keypress','desktop_scroll','desktop_focus_window'}
KEYS = {'Return','Escape','Tab','BackSpace','Delete','Up','Down','Left','Right','Home','End','Page_Up','Page_Down','ctrl+l','ctrl+a','alt+F4','alt+F2'}

def require(data, allowed, required=()):
    if not isinstance(data,dict) or set(data)-set(allowed) or set(required)-set(data):
        raise ValueError('Invalid desktop tool arguments')

def command(args,env,check=True):
    result=subprocess.run(args,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5)
    if check and result.returncode:
        raise RuntimeError('Desktop operation failed: '+result.stderr.strip()[:250])
    return result.stdout.strip()

def desktop():
    candidates={}
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():continue
        try:
            if item.stat().st_uid!=os.getuid() or (item/'comm').read_text().strip()!='xfce4-session':continue
            fields=dict(part.split('=',1) for part in (item/'environ').read_bytes().decode(errors='replace').split('\0') if '=' in part)
            display=fields.get('DISPLAY','')
            if not re.fullmatch(r':\d+(?:\.\d+)?',display):continue
            env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(Path.home()),'USER':'pilot','LANG':'C.UTF-8','DISPLAY':display,'XAUTHORITY':fields.get('XAUTHORITY',str(Path.home()/'.Xauthority'))}
            for key in ('DBUS_SESSION_BUS_ADDRESS','XDG_RUNTIME_DIR'):
                if key in fields:env[key]=fields[key]
            geometry=command(['xdotool','getdisplaygeometry'],env)
            width,height=map(int,geometry.split())
            if width<=0 or height<=0 or width*height>16000000:continue
            candidates[display]=(env,width,height)
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):continue
    if len(candidates)!=1:
        raise RuntimeError('Exactly one usable pilot XFCE desktop must be running. Connect the phone desktop first; close extra desktop sessions if needed.')
    return next(iter(candidates.values()))

def window_state(env):
    current=command(['xdotool','getactivewindow'],env,False)
    active=command(['xdotool','getwindowname',current],env,False) if current.isdigit() else ''
    stacking=command(['xprop','-root','_NET_CLIENT_LIST_STACKING'],env,False)
    ids=[str(int(value,16))for value in reversed(re.findall(r'0x[0-9a-fA-F]+',stacking))]
    if not ids:ids=command(['xdotool','search','--onlyvisible','--name','.'],env,False).splitlines()[-40:]
    windows=[]
    for value in ids[:40]:
        if value.isdigit():
            visibility=command(['xprop','-id',value,'_NET_WM_STATE'],env,False)
            if '_NET_WM_STATE_HIDDEN'in visibility:continue
            title=command(['xdotool','getwindowname',value],env,False)
            if title:
                info={'id':int(value),'title':title[:240]}
                geometry=command(['xdotool','getwindowgeometry','--shell',value],env,False)
                fields=dict(line.split('=',1) for line in geometry.splitlines() if '=' in line)
                for field in ('X','Y','WIDTH','HEIGHT'):
                    try:info[field.lower()]=int(fields[field])
                    except (KeyError,ValueError):pass
                windows.append(info)
    return {'active_window':active[:240],'active_window_id':int(current)if current.isdigit()else None,'windows':windows}

def dispatch(tool,data):
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    statefile=STATE/'desktop-control.json'
    with (STATE/'desktop.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state=json.loads(statefile.read_text()) if statefile.exists() else {'owner':'agent','revision':0,'observation':None}
        def save():
            temporary=statefile.with_suffix('.tmp')
            temporary.write_text(json.dumps(state))
            os.replace(temporary,statefile)
        if tool=='desktop_state':
            require(data,[])
            return {'ok':True,'owner':state['owner'],'revision':state['revision']}
        if tool=='desktop_control':
            require(data,['owner'],['owner'])
            if data['owner'] not in ('agent','human'):raise ValueError('Invalid desktop owner')
            if data['owner']!=state['owner']:
                state.update(owner=data['owner'],revision=state['revision']+1,observation=None)
                save()
            return {'ok':True,'owner':state['owner'],'revision':state['revision']}
        env,width,height=desktop()
        if tool=='desktop_observe':
            require(data,[])
            with tempfile.TemporaryDirectory(prefix='localpilot-screen-') as directory:
                capture=Path(directory)/'screen.png'
                command(['scrot','-o',str(capture)],env)
                with Image.open(capture) as image:
                    if image.size!=(width,height):raise RuntimeError('Desktop geometry changed; observe again')
                    image=image.convert('RGB')
                    image.thumbnail((1280,1280),Image.Resampling.LANCZOS)
                    output=io.BytesIO();image.save(output,format='JPEG',quality=80)
                    encoded=base64.b64encode(output.getvalue()).decode()
                    image_width,image_height=image.size
            observation={'id':str(uuid.uuid4()),'display':env['DISPLAY'],'width':width,'height':height,'image_width':image_width,'image_height':image_height,'revision':state['revision'],'time':time.monotonic()}
            state['observation']=observation;save()
            return {'ok':True,'observation_id':observation['id'],'display':env['DISPLAY'],'width':width,'height':height,'image_width':image_width,'image_height':image_height,'owner':state['owner'],'revision':state['revision'],'image_jpeg':encoded,**window_state(env)}
        if tool not in INPUTS:raise ValueError('Unknown desktop tool')
        if state['owner']!='agent':raise PermissionError('Human controls the desktop. Resume AI before desktop input.')
        observation=state.get('observation')
        if not observation or data.get('observation_id')!=observation['id']:
            raise ValueError('A fresh desktop_observe result is required before every input action')
        age=time.monotonic()-observation['time']
        if not 0<=age<=120 or observation['revision']!=state['revision'] or observation['display']!=env['DISPLAY'] or (observation['width'],observation['height'])!=(width,height):
            raise ValueError('Desktop observation is stale; capture a new screenshot')
        base=['observation_id']
        operation=None
        if tool=='desktop_click':
            require(data,base+['x','y','button','count'],base+['x','y'])
            x,y=data['x'],data['y'];button=data.get('button','left');count=data.get('count',1)
            if type(x)is not int or type(y)is not int or not 0<=x<observation['image_width'] or not 0<=y<observation['image_height']:raise ValueError('Coordinates are outside the observed image')
            if button not in ('left','right') or type(count)is not int or count not in (1,2):raise ValueError('Invalid click')
            x=min(width-1,round(x*width/observation['image_width']));y=min(height-1,round(y*height/observation['image_height']))
            operation=['xdotool','mousemove','--sync',str(x),str(y),'click','--clearmodifiers','--repeat',str(count),'--delay','100','1' if button=='left' else '3']
        elif tool=='desktop_type':
            require(data,base+['text'],base+['text'])
            text=data['text']
            if not isinstance(text,str) or not 1<=len(text)<=1000 or '\0'in text:raise ValueError('Invalid desktop text')
            operation=['xdotool','type','--clearmodifiers','--delay','1','--',text]
        elif tool=='desktop_keypress':
            require(data,base+['key'],base+['key'])
            if data['key'] not in KEYS:raise ValueError('Key is not permitted')
            operation=['xdotool','key','--clearmodifiers',data['key']]
        elif tool=='desktop_scroll':
            require(data,base+['direction','amount'],base+['direction'])
            amount=data.get('amount',1)
            if data['direction']not in ('up','down') or type(amount)is not int or not 1<=amount<=5:raise ValueError('Invalid scroll')
            operation=['xdotool','click','--repeat',str(amount),'--delay','100','4' if data['direction']=='up' else '5']
        elif tool=='desktop_focus_window':
            require(data,base+['window_id'],base+['window_id'])
            value=data['window_id']
            if type(value)is not int or value not in [w['id'] for w in window_state(env)['windows']]:raise ValueError('Window is not visible in this desktop')
            operation=['xdotool','windowactivate','--sync',str(value)]
        elif tool=='desktop_browser_open':
            require(data,base+['url'],base+['url'])
            from browser_tools import firefox_command
            operation=firefox_command(data['url'])
            env['MOZ_ENABLE_WAYLAND']='0'
            env['LIBGL_ALWAYS_SOFTWARE']='1'
        elif tool=='desktop_open_application':
            require(data,base+['application','path'],base+['application'])
            if data['application']=='file_manager':
                path=data.get('path','.')
                relative=Path(path)
                if relative.is_absolute()or '..'in relative.parts:raise ValueError('Invalid application path')
                target=(WORKSPACE/relative).resolve();target.relative_to(WORKSPACE.resolve())
                if not target.is_dir():raise ValueError('Requested workspace directory does not exist')
                operation=['thunar',str(target)]
            elif data['application']=='terminal':operation=['xterm','-T','LocalPilot','-xrm','XTerm*allowTitleOps:false']
            else:raise ValueError('Application is not available')
        # Consume before input so retries cannot reuse a reviewed screenshot.
        state['observation']=None;save()
        if tool in ('desktop_open_application','desktop_browser_open'):
            previous_windows={window['id'] for window in window_state(env)['windows']} if tool=='desktop_browser_open' else set()
            with tempfile.TemporaryFile()as errors:
                process=subprocess.Popen(operation,env=env,cwd=WORKSPACE,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=errors,start_new_session=True)
                time.sleep(.5)
                if process.poll()not in (None,0):
                    errors.seek(0)
                    raise RuntimeError('Application launch failed: '+errors.read(250).decode(errors='replace'))
                if tool=='desktop_browser_open':
                    deadline=time.monotonic()+8
                    while time.monotonic()<deadline:
                        windows=window_state(env)['windows']
                        if any(w['id']not in previous_windows and 'firefox'in w['title'].lower() for w in windows):break
                        time.sleep(.25)
        else:command(operation,env)
        return {'ok':True,'action':tool,'display':env['DISPLAY'],'revision':state['revision'],**window_state(env)}
