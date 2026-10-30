"""Assemble the existing tested hooks with station-local transport."""
import json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1]
java=pathlib.Path(sys.argv[1]).read_text()
out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
# Token is supplied on station at deployment, never a token committed in source.
token=sys.argv[3]
for role,source in [('sdk','agent.js'),('player','player-agent.js')]:
 code=(root/'bridge'/source).read_text().replace('send({','emit({')
 prefix='const LOCAL_ROLE='+json.dumps(role)+'; const LOCAL_TOKEN='+json.dumps(token)+';\n'
 core=(root/'bridge/music-core.js').read_text() if role=='sdk' else ''
 (out/(role+'.js')).write_text(java+'\nvar Java=bridge;\n'+prefix+(root/'native/transport.js').read_text()+'\n'+core+'\n'+code)
