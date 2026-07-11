/* Le Tartarughe · privacy-friendly analytics (GoatCounter, no cookies)
   ------------------------------------------------------------------
   1) Create a free account at https://www.goatcounter.com (site code, e.g. "tartarughe")
   2) Replace GC_SITE below with your site code
   3) Tip for the host: open the site once with #toggle-goatcounter appended to the
      URL to stop counting your own visits on that browser (built into GoatCounter).
   Events sent (all cookie-less, no personal data):
   - pageviews (automatic)
   - nav-<from>-to-<dest>   internal navigation (cards, hamburger menu, back links)
   - video-play-<title>     first play of each embedded YouTube video
   - click-whatsapp / click-maps / click-youtube-<page> / click-out-<host>
   - lang-<code>            language switch
   - subscribe-email / subscribe-push   (stay.html alert box, click = attempt)
   - stay-dates-set         guest entered stay dates on stay.html
*/
(function(){
'use strict';
var GC_SITE='tartarughe';                       // ← replace with your GoatCounter code
if(GC_SITE.indexOf('__')===0) return;            // not configured yet → do nothing
var GC='https://'+GC_SITE+'.goatcounter.com/count';

/* inject the official GoatCounter loader */
var s=document.createElement('script');
s.async=true;
s.src='https://gc.zgo.at/count.js';
s.setAttribute('data-goatcounter',GC);
document.head.appendChild(s);

/* event helper with a small queue while count.js loads */
var q=[];
function ev(name){
  name=String(name).slice(0,120);
  if(window.goatcounter&&window.goatcounter.count){
    window.goatcounter.count({path:name,event:true});
  }else{
    q.push(name);
  }
}
var tries=0,iv=setInterval(function(){
  if(window.goatcounter&&window.goatcounter.count){
    q.forEach(function(n){window.goatcounter.count({path:n,event:true});});
    q=[];clearInterval(iv);
  }else if(++tries>30){clearInterval(iv);}
},500);

var page=(location.pathname.split('/').pop()||'index.html').replace(/\.html$/,'')||'index';

/* generic click tracking: internal nav, external links, language, subscribe */
document.addEventListener('click',function(e){
  var t=e.target;
  var a=t.closest?t.closest('a'):null;
  if(a){
    var href=a.getAttribute('href')||'';
    if(/^https?:\/\//i.test(href)){
      var h=(a.hostname||'').replace(/^www\./,'');
      if(h==='wa.me'||h.indexOf('whatsapp')>-1)      ev('click-whatsapp');
      else if(h==='youtu.be'||h.indexOf('youtube')>-1) ev('click-youtube-'+page);
      else if(h.indexOf('google')>-1&&/map/i.test(href)) ev('click-maps');
      else                                            ev('click-out-'+h);
    }else if(/\.html/i.test(href)){
      var dest=href.split('#')[0].split('?')[0].replace(/\.html$/,'');
      if(dest&&dest!==page) ev('nav-'+page+'-to-'+dest);
    }
    return;
  }
  var b=t.closest?t.closest('button'):null;
  if(b){
    if(b.dataset&&b.dataset.l) ev('lang-'+b.dataset.l);
    else if(b.id==='sub_btn')  ev('subscribe-email');
    else if(b.id==='push_btn') ev('subscribe-push');
  }
},true);

/* stay dates entered (stay.html) — dates themselves are NOT sent */
['sd_from','sd_to'].forEach(function(id){
  var el=document.getElementById(id);
  if(el)el.addEventListener('change',function(){if(el.value)ev('stay-dates-set');});
});

/* YouTube embeds: count the first play of each video */
var yts=[].slice.call(document.querySelectorAll('iframe[src*="youtube.com/embed"]'));
if(yts.length){
  yts.forEach(function(f,i){
    if(!f.id)f.id='ltyt'+i;
    if(f.src.indexOf('enablejsapi')<0)
      f.src+=(f.src.indexOf('?')>-1?'&':'?')+'enablejsapi=1&origin='+encodeURIComponent(location.origin);
  });
  var tag=document.createElement('script');
  tag.src='https://www.youtube.com/iframe_api';
  document.head.appendChild(tag);
  var played={};
  window.onYouTubeIframeAPIReady=function(){
    yts.forEach(function(f){
      try{
        new YT.Player(f.id,{events:{onStateChange:function(s2){
          if(s2.data===YT.PlayerState.PLAYING&&!played[f.id]){
            played[f.id]=1;
            var t=(f.getAttribute('title')||f.id).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
            ev('video-play-'+t);
          }
        }}});
      }catch(err){}
    });
  };
}
})();
