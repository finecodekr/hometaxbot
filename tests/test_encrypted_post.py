import base64
import textwrap
import unittest
from pathlib import Path
from urllib.parse import unquote

import quickjs

from hometaxbot.scraper.servicecheck import deobfuscate_js, extract_vars


class TestPostBodyEncryption(unittest.TestCase):
    def test_post_body_encryption(self):
        with open(Path(__file__).parent / 'serviceCheck.do.20250515.js', 'r') as f:
            js = f.read()

        with open(Path(__file__).parent / 'serviceCheck.decoded.20250515.js', 'w') as f:
            vars = extract_vars(js)
            crypto_keys, _, encoded_consts, _, uuid_load, uuid, decoder_function = vars.values()
            print(vars.keys())
            print(encoded_consts)
            consts = [unquote(base64.b64decode(const)) for const in encoded_consts]
            print(consts)
            deobfuscated = deobfuscate_js(js, 
                                          consts_key=list(vars.keys())[2], 
                                          consts=consts, 
                                          decoder_function=decoder_function)
            f.write(deobfuscated)

        context = quickjs.Context()
        context.eval(polyfill)
        context.eval(deobfuscated)
            # crypto_keys, _, encoded_consts, _, uuid_load, uuid = vars.values()

        body_source = '"{"befCallYn":"","dprtUserId":"","itrfCd":"22","mdfRtnPyppApplcCtl":"100202 410202 330202 100203 410203 310203 450202 220202 220203 320202 240202 240203 470202","ntplInfpYn":"Y","pubcUserNo":"100000000017404995","rtnDtEnd":"20250515","rtnDtSrt":"20250415","sbmsMatePubcPrslBrkdYn":"N","scrnId":"UTERNAAZ91","startBsno":"","stmnWrtMthdCd":"99","tin":"","txprRgtNo":"","rtnCvaId":"","endBsno":"","gubun":"","resultCnt":"0","pageSize":"0","pageNum":"0","pageInfoVO":{"pageNum":"1","pageSize":"10","totalCount":"10034"}}<nts<nts>nts>42Mct9RUg0bv7qTuyhefPDoXFmbtdWD5ph6mZeFE4cU31"'
        body_encrypted = 'G4fmU6=VUr3xDOC09IfIuc50ndJdNaOvQtjS10Bve0Md5OTF9xA7hxUC9xlt9xUvurO0bCTLNo0L9xUv9xAtpxUv9xUv9xUtUxUvu7jin7ci5cUpDtOvZIOvQeOvZIOvZIOvbvOvZrEd1rut5tOvZIOvQeOvZIUv9xUv9xUtUxUvu4b0OrQLO6Bi166i16gaQCQLhxUv9xAtpxUvZejvKIjv9xUvKtovKIjv9xUvKvAvKIjv9xUvKejvKIjvUxUvKtovKIjvUxUvKvovKIjvUxUvKt4vKIjv9xUvKIUvKIjv9xUvKIUvKIjvUxUvKvUvKIjv9xUvKIQvKIjv9xUvKIQvKIjvUxUvKtlvKIjv9xUv9xUtUxUvuBQiNorLu0jDDXOvZIOvQeOvZr0rqIUrqrKrqIUi1c9a4cA0HrSLUxUv9xAtpxUvZejvKmjvKmjvKmoCAtjCKbBCpxUv9xUtUxUvnrQLb7Q7DBbrqIUrqC6rqIUvZmUCqm4vqxOvZIOvbvOvZrUdNBedMCUdhxUv9xAtpxUvZIjvZxjCKe4rqIUrqrKrqIUi5rsiQ4TdNctdDrZx1rALerUF570L9xUv9xAtpxUvbXOvZIOvbvOvZrAalrzpDtOvZIOvQeOvZrccecpqbM6DZborqIUrqrKrqIUil7Tin7hi5B3rqIUrqC6rqIUrqIUrqrKrqIUil7sLOdUde4QFN7K0hxUv9xAtpxUvZbBrqIUrqrKrqIUdNOzrqIUrqC6rqIUrqIUrqrKrqIUd1TjiOrndeB3rqIUrqC6rqIUrqIUrqrKrqIUin7ztl0TpDtOvZIOvQeOvZIOvZIOvbvOvZrOLu7hi5B3rqIUrqC6rqIUrqIUrqrKrqIU0lc9dDXOvZIOvQeOvZIOvZIOvbvOvZrU0HC4L17KLntOvZIOvQeOvZIjrqIUrqrKrqIUiNMn0cCEVuxOvZIOvQeOvZIjrqIUrqrKrqIUiNMn0xB4LpxUv9xAtpxUvZmOvZIOvbvOvZrjaDdOpDBuL40PrqIUrqC6rqdhrqIUiNMn0xB4LpxUv9xAtpxUvZeOvZIOvbvOvZrjaDdOx5Of0pxUv9xAtpxUvZejrqIUrqrKrqIUdNWQaDoKLlczdhxUv9xAtpxUvZejvKvQrqIUrqderqderqCKLn7ArqCKLn7ArqCMLn7ArqCMCKrCaltBxOcnvNr5ClMxdHOw0D0t7NWa7u49dN7H7KcjFK0sDucN7q7ZcqvoI9j9qccwpDb9SOsyInt9S9I9RhrwIZw9I9j9aHv9SOsdJcQgIb4RSDIXihIfIurpCQTQixCeqxoYCDr5ietlSMtlDnTha4rH0uoqF9rW&Rfb86Os1z=p8pcaEYQpT40LieCaAJoLJdyr137gkS9gk6qgka2gk6bZcdcxq3It3FDgk6bgkSugk6bgk6bgkgigk6bpWuba3d0p8ggp24bwT40xB4bwT4bwT4bxb4bwcFQscpip24bwT40xB4bwf6bgk6bgkgigk6bt1Lc4ALD4WFos93osUPfxyLIgk6bgkSugk6bwkeowfebgk6oSi9owfebgk6ow0wowfebgk6owkeowfe0gk6oSi9owfe0gk6ow09owfe0gk6oSi4owfebgk6owf6owfebgk6owf6owfe0gk6ow06owfebgk6owfxowfebgk6owfxowfe0gk6oSisowfebgk6bgkgigk6btALot9FDpAuptT4bwT40xB4bwFJFwf6FwJwFwfgoa1gfd8SFsJjzgk6bgkSugk6bwkeowieowieowi9ySieQVkJEgk6bgkgigk6bsALDLWL3tcxFwf6FwQ9Fwf6bwi6Ewi4PSB4bwT4bxb4bwAgQtJLQ4ygQgk6bgkSugk6bwfebSkeQwk4Fwf6FwJwFwfg0ZcE0k13QpduEZcSxsASIxAgKp3FDgk6bgkSugk6bkT4bwT4bxb4bwASfscjgp24bwT40xB4bwFd4LdgVx43rVk9Fwf6FwJwFwfg0aU3ba9g0tc5Fwf6FwQ9Fwf6Fwf6FwJwFwfg0aUEDdygQk8LMp9SJgk6bgkSugk6bVkJFwf6FwJwFwfgQr1CFwf6FwQ9Fwf6Fwf6FwJwFwfgQnWub4caQkc5Fwf6FwQ9Fwf6Fwf6FwJwFwfgbaUjiac3gp24bwT40xB4bwT4bwT4bxb4bwcdDp9g0tc5Fwf6FwQ9Fwf6Fwf6FwJwFwfgAa1gEtT4bwT40xB4bwT4bwT4bxb4bwAgFsydIa9SDa24bwT40xB4bwfeFwf6FwJwFwfgoZ1aF4qFXpB4bwT40xB4bwfeFwf6FwJwFwfgoZ1aFkAdGgk6bgkSugk6bw24bwT4bxb4bwAuhpqdgtcpzdJ5Fwf6FwQ9FSQ6FwfgoZ1aFkAdGgk6bgkSugk6bwB4bwT4bxb4bwAuhpqdkr8OFgk6bgkSugk6bwkeFwf6FwJwFwfgQtyLht9Sza1jQgk6bgkSugk6bwkeow0xFwf6FSQxFSQxFwQSDaWwFwQSDaWwFwQdDaWwFwQ4QwJEfaiFBd1soZAZysdLEn1hFpFu9tEhUt1gQp3a9S8uMScErp4p3SUSdw09%253D'



polyfill = textwrap.dedent("""
    /* ---------- Window / Document 스텁 ---------- */
    var window   = this;
    var document = {};        window.document = document;
    var navigator = { userAgent: "QuickJS" };

    /* ---------- location / localStorage ---------- */
    window.location = { href: "https://example.com/" };
    window.lGM2M0Ry2t0rage = [];

    /* ---------- console ---------- */
    var console = { log: function(){}, error: function(){} };

    /* ---------- atob / btoa ---------- */
    (function(){
      var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
      function InvalidCharacterError(){ throw new Error('InvalidCharacterError'); }
      window.btoa = window.btoa || function(input){
        var str = String(input), output = '';
        for(var block, charCode, i=0, map=chars;
            str.charAt(i|0) || (map='=', i%1);
            output += map.charAt(63 & block >> 8 - i%1*8)){
          charCode = str.charCodeAt(i += 3/4);
          if(charCode > 255) InvalidCharacterError();
          block = block << 8 | charCode;
        }
        return output;
      };
      window.atob = window.atob || function(input){
        var str = String(input).replace(/=+$/, '');
        if (str.length % 4 == 1) InvalidCharacterError();
        for (var bc=0, bs, buffer, i=0, output='';
             buffer = str.charAt(i++);
             ~buffer && (bs = bc % 4 ? bs * 64 + buffer : buffer,
             bc++ % 4) ? output += String.fromCharCode(255 & bs >> (-2 * bc & 6)) : 0){
          buffer = chars.indexOf(buffer);
        }
        return output;
      };
    })();

    /* ---------- FormData / File / HTMLFormElement ---------- */
    function File() {}
    function FormData(){
      this._d = [];
      this.append = function(k,v){ this._d.push([k,v]); };
      this.entries = function(){
        var i = 0, d = this._d;
        return { next: function(){ return i < d.length ?
          { value: d[i++], done: false } : { done: true }; } };
      };
    }
    function HTMLFormElement(){}
    window.File = File;
    window.FormData = FormData;
    window.HTMLFormElement = HTMLFormElement;

    /* ---------- 빈 함수 스텁 (로그·타이머) ---------- */
    window.Utx4o        = function(){};
    window.u6UFZF3EtH   = function(){};
    window.Jd5BmGUvVW   = function(x){ return x; };

    /* ---------- CryptoJS (SHA-384/AES) ---------- */
    
    /* ---------- 추가 스텁 & alias ---------- */
    
    // 1) navigator 보강
    navigator.hardwareConcurrency = navigator.hardwareConcurrency || 4;
    navigator.languages           = navigator.languages || ["en-US"];
    
    // 2) URL / URLSearchParams (아주 단순 버전)
    function URL(u){
      var m = u.match(/^(https?:)\/\/([^\/?#]+)([^?#]*)(\?[^#]*|)/);
      this.protocol = m ? m[1] : "";
      this.host     = m ? m[2] : "";
      this.hostname = this.host.split(":")[0];
      this.port     = (this.host.split(":")[1]||"");
      this.pathname = m ? m[3] : "";
      this.search   = m ? m[4] : "";
      this.href     = u;
    }
    function URLSearchParams(q){
      this.q = q.replace(/^\?/, "");
      this.get = function(k){
        return decodeURIComponent(
          (this.q.match(new RegExp("[?&]"+k+"=([^&]*)"))||[])[1]||""
        );
      };
    }
    window.URL = URL;
    window.URLSearchParams = URLSearchParams;
    
    // 3) XMLHttpRequest (매서드만 기록하고 즉시 완료 이벤트 발화)
    function XMLHttpRequest(){
      this._headers = {};
      this.readyState = 4;      // DONE
      this.status     = 200;
      this.responseText = "";
      this.onreadystatechange = null;
    }
    XMLHttpRequest.prototype.open = function(method,url,async){
      this._method = method; this._url = url;
    };
    XMLHttpRequest.prototype.setRequestHeader = function(k,v){
      this._headers[k] = v;
    };
    XMLHttpRequest.prototype.send = function(body){
      if(this.onreadystatechange) this.onreadystatechange();
    };
    XMLHttpRequest.prototype.abort = function(){};
    XMLHttpRequest.DONE = 4;
    window.XMLHttpRequest = XMLHttpRequest;
    
    // IE‑전용 코드가 ActiveXObject 로 XHR을 생성하려 할 때 대비
    window.ActiveXObject = function(name){
      if(/XMLHTTP/.test(name)) return new XMLHttpRequest();
      throw new Error("ActiveXObject "+name+" not supported");
    };
    
    // 4) DOM 유틸 (querySelectorAll, getElementById, …)
    document._nodes = {};
    document.createElement = function(tag){
      const el = { tagName: tag.toUpperCase(),
                   attributes:{}, style:{},
                   children:[], parentNode:null,
                   appendChild:function(c){c.parentNode=this; this.children.push(c);},
                   cloneNode:function(){ return JSON.parse(JSON.stringify(this)); },
                   setAttribute:function(k,v){ this.attributes[k]=v; },
                   getAttribute:function(k){ return this.attributes[k]; }
                 };
      return el;
    };
    document.getElementById = function(id){ return document._nodes[id]||null; };
    document.querySelectorAll =
    document.getElementsByName =
    document.getElementsByTagName = function(){ return []; };
    
    // HTMLFormElement.submit 더미
    HTMLFormElement.prototype.submit = function(){};
    
    // 5) 매우 자주 쓰이는 helper alias
    window.evfw_atob        = window.atob;      // 코드 안에서 별칭 사용
    window.evfw_log         = function(){};     // console 대체
    window.evRc             = function(){};     // Response‑checker 더미
    window.u6UFZF3EtH       = function(){};     // 에러 로거
    window.u6UFZF3          = {};               // 속성 접근만 하는 객체
    
    // 6) Reflect / Proxy 는 QuickJS 기본 탑재 → 추가 조치 불필요
    // 7) CryptoJS가 외부에 없다면 별도 로드 필요 (이미 포함돼 있으면 PASS)    
""")


polyfill = '''
function __makeStub(depth=0){
  const fn = function(){ return undefined; };
  return new Proxy(fn,{
    apply() { return undefined; },
    get(t,p){
      if(p===Symbol.toPrimitive) return ()=>"stub";
      if(!(p in t)) t[p] = depth<4 ? __makeStub(depth+1) : undefined;
      return t[p];
    },
    set(t,p,v){ t[p]=v; return true; }
  });
}
var window   = __makeStub();
var document = window.document;          // 최소 DOM
window.atob  = s => Buffer.from(s,'base64').toString('binary');
window.btoa  = s => Buffer.from(s,'binary').toString('base64');
'''