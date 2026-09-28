import json
t=open('/tmp/claude-0/-home-claude/bc7375d9-8385-5523-8bb6-2b2f061d324b/scratchpad/template.html',encoding='utf-8').read()
vis=open('/tmp/claude-0/-home-claude/bc7375d9-8385-5523-8bb6-2b2f061d324b/scratchpad/vis/node_modules/vis-network/standalone/umd/vis-network.min.js',encoding='utf-8').read().replace('</script','<\\/script')
d=json.load(open('/tmp/claude-0/-home-claude/bc7375d9-8385-5523-8bb6-2b2f061d324b/scratchpad/out/graph_nlp.json',encoding='utf-8'))
data=json.dumps(d,ensure_ascii=False).replace('</','<\\/')
open('/mnt/user-data/outputs/grafo_lecciones_transporte.html','w',encoding='utf-8').write(t.replace('__VIS__',vis).replace('__DATA__',data))
