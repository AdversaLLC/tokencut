"""ArchRouter: prompt framing + parser + round-trip + fail-safe (stub endpoint)."""
import sys, os, json, http.server, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tokencut.archrouter import build_prompt, parse_route, ArchRouter

def test_pure():
    routes=[{"name":"a","description":"x"},{"name":"b","description":"y"}]
    p=build_prompt(routes,[{"role":"user","content":"hi"}])
    assert "<routes>" in p and '"a"' in p and "<conversation>" in p
    cases=[('{"route": "a"}','a'),('junk {"route":"b"} more','b'),('nope','other'),('{"route":"zzz"}','other')]
    return all(parse_route(t,{"a","b","other"})==e for t,e in cases)

def test_roundtrip():
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self,*a): pass
        def do_POST(self):
            n=int(self.headers.get("Content-Length",0)); b=json.loads(self.rfile.read(n))
            conv=json.loads(b["messages"][0]["content"].split("<conversation>")[1].split("</conversation>")[0].strip())
            u=conv[-1]["content"].lower()
            r="bug_fixing" if ("fix" in u or "error" in u) else "code_generation" if "write" in u else "other"
            self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
            self.wfile.write(json.dumps({"choices":[{"message":{"content":json.dumps({"route":r})}}]}).encode())
    srv=http.server.HTTPServer(("127.0.0.1",8091),H); threading.Thread(target=srv.serve_forever,daemon=True).start(); time.sleep(0.2)
    routes=[{"name":"code_generation","description":"write"},{"name":"bug_fixing","description":"fix"}]
    ar=ArchRouter(endpoint="http://127.0.0.1:8091/v1/chat/completions")
    ok=(ar.route(routes,[{"role":"user","content":"fix this error"}])["route"]=="bug_fixing"
        and ar.route(routes,[{"role":"user","content":"write a parser"}])["route"]=="code_generation")
    srv.shutdown()
    return ok

def test_failsafe():
    r=ArchRouter(endpoint="http://127.0.0.1:9998/v1/chat/completions",timeout=1.0).route(
        [{"name":"a","description":"x"}],[{"role":"user","content":"hi"}])
    return r["route"]=="other" and r["raw"] is None

if __name__=="__main__":
    results={"pure":test_pure(),"roundtrip":test_roundtrip(),"failsafe":test_failsafe()}
    ok=sum(results.values())
    print(f"archrouter suite: {ok}/{len(results)} pass", results)
    sys.exit(0 if ok==len(results) else 1)
