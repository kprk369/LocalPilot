"""Local operator client. The token never enters the model's context."""
import argparse,json
import httpx
from .config import Settings

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='action',required=True)
    new=sub.add_parser('new');new.add_argument('request')
    show=sub.add_parser('show');show.add_argument('id')
    events=sub.add_parser('events');events.add_argument('id')
    for action in ['approve','reject']:
        command=sub.add_parser(action);command.add_argument('id');command.add_argument('approval_id')
    cancel=sub.add_parser('cancel');cancel.add_argument('id')
    sub.add_parser('models')
    args=parser.parse_args()
    with httpx.Client(base_url='http://127.0.0.1:8765',headers={'Authorization':'Bearer '+Settings.load().token},trust_env=False,timeout=30) as client:
        if args.action=='new':response=client.post('/tasks',json={'request':args.request})
        elif args.action=='show':response=client.get('/tasks/'+args.id)
        elif args.action=='events':response=client.get('/tasks/'+args.id+'/events')
        elif args.action in ['approve','reject']:response=client.post('/tasks/'+args.id+'/approval',json={'approval_id':args.approval_id,'allow':args.action=='approve'})
        elif args.action=='cancel':response=client.post('/tasks/'+args.id+'/cancel')
        else:response=client.get('/models')
        response.raise_for_status()
        print(json.dumps(response.json(),indent=2,ensure_ascii=False))

if __name__=='__main__':main()
