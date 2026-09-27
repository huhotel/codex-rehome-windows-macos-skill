"""Require native raw-chain/standalone equivalence and bind the sanitized ledger."""
import argparse,json
from pathlib import Path
from history_runtime import require,dump,digest
from native_verify import PROFILE_VERSION

def prove(raw_report,flat_report,private_flat,sanitized_flat,out):
 raw=json.loads(Path(raw_report).read_text(encoding='utf-8'));flat=json.loads(Path(flat_report).read_text(encoding='utf-8'))
 private=Path(private_flat);sanitized=Path(sanitized_flat)
 p=json.loads((private/'export-ledger.json').read_text(encoding='utf-8'));s=json.loads((sanitized/'export-ledger.json').read_text(encoding='utf-8'))
 require(p['sanitized'] is False and s['sanitized'] is True,'Need distinct private and sanitized exports')
 require(all(r.get('native_full_history_pass') and r['cli_version']==PROFILE_VERSION for r in [raw,flat]),'Both native probes must pass')
 require(raw['raw_dependency_probe'] and not flat['raw_dependency_probe'],'Compare source dependency probe with standalone probe')
 require(raw['normalization_map']==flat['normalization_map'],'Identical normalization required')
 require(raw.get('source_audit_sha256') and raw['source_audit_sha256']==flat.get('source_audit_sha256'),'Both probes must bind the same source audit')
 fields=['turns','items','turns_sha256','items_sha256']
 def content(r):return {x['id']:{k:x[k] for k in fields} for x in r['threads']}
 require(content(raw)==content(flat),'Native history content/order differs after conversion')
 pi={x['id']:x for x in p['threads']};si={x['id']:x for x in s['threads']}
 require(set(pi)==set(si)==set(content(raw)),'Selections must match')
 require(flat['source_export_sha256']=={k:v['sha256'] for k,v in pi.items()},'Standalone native probe must bind private candidate bytes')
 for tid in pi:
  require(pi[tid]['source_ordered_sha256']==pi[tid]['sanitized_ordered_sha256']==si[tid]['source_ordered_sha256'],'Ordered source records differ: '+tid)
  require(pi[tid]['records']==si[tid]['records'],'Sanitization changed record count')
  for base,entries in [(private,pi),(sanitized,si)]:require(digest(base/entries[tid]['file'])==entries[tid]['sha256'],'Candidate changed')
 result={'conversion_equivalent':True,'cli_version':PROFILE_VERSION,'source_audit_sha256':raw['source_audit_sha256'],'sanitized_ledger_sha256':digest(sanitized/'export-ledger.json'),'selected_ids':sorted(si),'redaction_review':'Review intended replacements separately; private probes must not be transferred.'}
 require(not Path(out).exists(),'Preserve existing proof');dump(out,result);return result

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 for key in ['raw-report','flat-report','private-flat','sanitized-flat','output']:ap.add_argument('--'+key,required=True)
 a=ap.parse_args();prove(a.raw_report,a.flat_report,a.private_flat,a.sanitized_flat,a.output)
