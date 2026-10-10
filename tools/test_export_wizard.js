const assert = require('node:assert/strict');
const {buildScript} = require('../web/portal/static/portal/export-wizard.js');
const sample = {player:'00000000-0000-4000-8000-000000000001',label:'Learner 01',timezone:'America/New_York',start:'2026-10-09T09:00',end:'2026-10-09T12:00',config:'local-config.json',catalog:'catalog.json',output:'session.json'};
function args(script) { return JSON.parse(script.split("$exportArgumentsJson = @'\r\n")[1].split("\r\n'@\r\n")[0]); }
assert(args(buildScript(sample)).includes('--start=2026-10-09T09:00:00'));
for(const change of [{player:'MCSfox'},{timezone:'EST'},{start:'2026-02-30T09:00'},{end:'2026-10-09T08:00'},{end:'2026-10-17T12:00'},{output:'script.ps1'},{config:''},{label:'bad\ninput'}]) assert.throws(()=>buildScript({...sample,...change}));
const malicious = `O'Brien "quoted"; $(Write-Output PWNED) \u2019 \u00e9 \ud83d\udc22`;
const script = buildScript({...sample,label:malicious,study:"'@; $(whoami)",journal:'D:\\folder with spaces\\journal',roster:'roster.json'});
assert(args(script).includes('--label='+malicious));
assert(args(script).includes("--study='@; $(whoami)"));
assert(args(script).includes('--journal=D:\\folder with spaces\\journal'));
assert.equal(script.split("\r\n'@\r\n").length,2);
assert(!/[^\x00-\x7f]/.test(script));
assert(!args(buildScript(sample)).some(a=>a.startsWith('--journal') || a==='--npc-complete'));
assert(script.includes('subprocess.call([sys.executable, sys.argv[1], *json.load(sys.stdin)])'));
console.log('Export wizard: validation, literal argument roundtrip and shell-boundary checks passed.');
